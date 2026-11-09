#!/usr/bin/env bash
# Deploy only web/API; the existing Compose file, secrets, DB and Airflow stay on host.
set -euo pipefail
umask 077
revision=${1:?commit SHA required}
digest=${2:?archive SHA256 required}
bucket=${3:?bucket required}
key=${4:?key required}
[[ $revision =~ ^[0-9a-f]{40}$ && $digest =~ ^[0-9a-f]{64}$ ]]
[[ $bucket == dataforge-academy-919774751018-input ]]
[[ $key == deployment/cicd/$revision/* ]]
exec 9>/var/lock/dataforge-deploy.lock
flock -w 900 9
cd /opt/dataforge
base=(docker compose --project-name dataforge --env-file .env.compose -f compose.aws.yml)
curl -fsS --max-time 20 http://127.0.0.1:8081/api/ready >/dev/null
old_api=$(docker inspect --format '{{.Image}}' dataforge-api-1)
old_web=$(docker inspect --format '{{.Image}}' dataforge-web-1)
install -d -m 0700 /opt/dataforge-releases
release=$(mktemp -d "/opt/dataforge-releases/${revision}.XXXXXX")
aws s3 cp "s3://$bucket/$key" "$release/source.tar.gz" --region us-east-1 --only-show-errors
printf '%s  %s\n' "$digest" "$release/source.tar.gz" | sha256sum --check
python3 - "$release" <<'PY'
import json
import sys
import tarfile
from pathlib import Path, PurePosixPath
root = Path(sys.argv[1])
with tarfile.open(root / 'source.tar.gz') as archive:
    for entry in archive.getmembers():
        path = PurePosixPath(entry.name)
        if path.is_absolute() or '..' in path.parts or not (entry.isfile() or entry.isdir()):
            raise SystemExit('Unsafe release archive member')
        if any(part.startswith('.env') and part != '.env.example' for part in path.parts):
            raise SystemExit('Environment file is forbidden in release')
    archive.extractall(root / 'source')
metadata = json.loads((root / 'source/frontend/public/release.json').read_text())
(root / 'revision').write_text(metadata['revision'])
PY
test "$(cat "$release/revision")" = "$revision"
docker build --label "org.opencontainers.image.revision=$revision" \
  -t "dataforge-api:$revision" "$release/source"
docker build --label "org.opencontainers.image.revision=$revision" \
  --build-arg "VITE_APP_REVISION=$revision" \
  -f "$release/source/frontend/Dockerfile.aws" \
  -t "dataforge-web:$revision" "$release/source/frontend"
active=/opt/dataforge/compose.cicd.yml
had_override=false
if [[ -f $active ]]; then
  cp "$active" "$release/previous-override.yml"
  had_override=true
fi
cat > "$release/rollback.yml" <<YAML
services:
  api:
    image: "$old_api"
  web:
    image: "$old_web"
YAML
rollback() {
  result=$?
  trap - EXIT
  if (( result != 0 )); then
    echo 'Deployment failed; restoring previous web/API images.'
    "${base[@]}" -f "$release/rollback.yml" up -d --no-deps --no-build api web || true
    if $had_override; then
      cp "$release/previous-override.yml" "$active"
    else
      rm -f "$active"
    fi
    curl -fsS --retry 12 --retry-delay 5 --retry-all-errors --max-time 10 \
      http://127.0.0.1:8081/api/ready >/dev/null || true
  fi
  exit "$result"
}
trap rollback EXIT
cat > "$release/next-override.yml" <<YAML
services:
  api:
    image: "dataforge-api:$revision"
  web:
    image: "dataforge-web:$revision"
YAML
"${base[@]}" -f "$release/next-override.yml" config --quiet
cp "$release/next-override.yml" "$active"
"${base[@]}" -f "$active" up -d --no-deps --no-build api web
ready=false
for attempt in $(seq 1 36); do
  if curl -fsS --max-time 5 http://127.0.0.1:8081/api/ready > "$release/readiness.json"; then
    ready=true
    break
  fi
  sleep 5
done
$ready
curl -fsS --max-time 10 http://127.0.0.1:8081/release.json > "$release/live-release.json"
python3 - "$release" "$revision" <<'PY'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
assert json.loads((root / 'readiness.json').read_text())['status'] == 'ready'
assert json.loads((root / 'live-release.json').read_text())['revision'] == sys.argv[2]
PY
for container in dataforge-api-1 dataforge-web-1; do
  test "$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$container")" = "$revision"
done
printf '%s\n' "$revision" > /opt/dataforge-releases/current-app-revision
trap - EXIT
echo "DATAFORGE_APP_DEPLOYED revision=$revision readiness=ready"
