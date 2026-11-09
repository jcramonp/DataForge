#!/bin/bash
# Restore the operator's two dumps into an isolated, disposable PostgreSQL.
set -euo pipefail
test "$(id -u)" = 0
base=/opt/dataforge-backups/db-20261109T080836Z
test -f "$base/dataforge-rds.dump"
test -f "$base/airflow.dump"
cd "$base"
sha256sum -c SHA256SUMS
available=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
if test "$available" -lt 786432; then
  echo 'Restore check needs at least 768 MiB available RAM; no container was started.' >&2
  exit 1
fi
probe="dataforge-restore-check-$(date +%s)"
created=0
trap 'if test "$created" = 1; then docker rm -fv "$probe" >/dev/null 2>&1 || true; fi' EXIT
docker run --pull=never -d --name "$probe" --network none \
  --memory=512m --cpus=1 \
  --tmpfs /var/lib/postgresql/data:rw,nosuid,nodev,size=512m \
  -e POSTGRES_USER=restore -e POSTGRES_DB=restore_dataforge \
  -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine >/dev/null
created=1
for attempt in $(seq 1 30); do
  if docker exec "$probe" pg_isready -h 127.0.0.1 -U restore -d restore_dataforge >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$probe" pg_isready -h 127.0.0.1 -U restore -d restore_dataforge
docker exec -i "$probe" pg_restore --exit-on-error --no-owner --no-acl \
  -U restore -d restore_dataforge < dataforge-rds.dump
docker exec "$probe" createdb -U restore restore_airflow
docker exec -i "$probe" pg_restore --exit-on-error --no-owner --no-acl \
  -U restore -d restore_airflow < airflow.dump
echo '=== RDS restored into temporary database ==='
docker exec "$probe" psql -X -v ON_ERROR_STOP=1 -U restore -d restore_dataforge -c \
  "SELECT 'contracts' AS item, count(*) FROM configuration_contract UNION ALL SELECT 'orchestrations', count(*) FROM orchestration_run UNION ALL SELECT 'assets', count(*) FROM data_asset;"
echo '=== Airflow restored into temporary database ==='
docker exec "$probe" psql -X -v ON_ERROR_STOP=1 -U restore -d restore_airflow -c \
  "SELECT 'dag_runs' AS item, count(*) FROM dag_run UNION ALL SELECT 'task_instances', count(*) FROM task_instance;"
echo RESTORE_CHECK_PASSED
