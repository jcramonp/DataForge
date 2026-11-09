#!/bin/bash
set -euo pipefail
umask 077
exec 9>/var/lock/dataforge-deploy.lock
flock -n 9
release=$(cd -- "$(dirname -- "$0")" && pwd)
test -f /opt/dataforge/.env.aws
test -f /opt/dataforge/.env.compose
python3 "$release/install.py"
cd /opt/dataforge
export COMPOSE_PARALLEL_LIMIT=1
docker compose --env-file .env.compose -f compose.aws.yml config --quiet
docker compose --env-file .env.compose -f compose.aws.yml up -d --build --no-deps api web
for attempt in $(seq 1 45); do
  if curl -fsS --max-time 5 http://127.0.0.1:8081/api/health >/dev/null; then
    echo DATAFORGE_GROQ_CODE_READY
    exit 0
  fi
  sleep 2
done
echo 'Health did not become ready; inspect service status.' >&2
exit 1
