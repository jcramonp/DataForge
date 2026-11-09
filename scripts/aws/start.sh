#!/bin/bash
set -euo pipefail
umask 077
exec 9>/var/lock/dataforge-deploy.lock
flock -n 9
cd /opt/dataforge

python3 - <<'PY'
import json
import os
import secrets
import subprocess
from pathlib import Path

os.umask(0o077)

def aws_json(*args):
    return json.loads(subprocess.check_output(
        ["aws", *args, "--region", "us-east-1", "--output", "json"],
        text=True,
    ))

db = aws_json(
    "rds", "describe-db-instances",
    "--db-instance-identifier", "dataforge-academy",
)["DBInstances"][0]

secret = aws_json(
    "secretsmanager", "get-secret-value",
    "--secret-id", db["MasterUserSecret"]["SecretArn"],
)
credentials = json.loads(secret["SecretString"])

internal_path = Path(".internal-secrets.json")
if internal_path.exists():
    internal = json.loads(internal_path.read_text())
else:
    internal = {
        "airflow_db": secrets.token_hex(24),
        "airflow_admin": secrets.token_hex(24),
        "airflow_jwt": secrets.token_hex(32),
        "copilot_signing": secrets.token_hex(32),
    }
    internal_path.write_text(json.dumps(internal))
internal_path.chmod(0o600)

values = {
    "DATAFORGE_ENV": "aws",
    "DATAFORGE_LOG_FORMAT": "json",
    "AWS_REGION": "us-east-1",
    "AWS_DEFAULT_REGION": "us-east-1",
    "POSTGRES_HOST": db["Endpoint"]["Address"],
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "dataforge",
    "POSTGRES_USER": credentials["username"],
    "POSTGRES_PASSWORD": credentials["password"],
    "POSTGRES_SSLMODE": "require",
    "AIRFLOW_API_URL": "http://airflow-api-server:8080",
    "AIRFLOW_ADMIN_USERNAME": "admin",
    "AIRFLOW_ADMIN_PASSWORD": internal["airflow_admin"],
    "AIRFLOW__API_AUTH__JWT_SECRET": internal["airflow_jwt"],
    "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN":
        "postgresql+psycopg2://airflow:"
        + internal["airflow_db"]
        + "@airflow-db:5432/airflow",
    "DATAFORGE_COPILOT_SIGNING_KEY": internal["copilot_signing"],
}
for layer in ("bronze", "silver", "gold", "quarantine"):
    values["MINIO_BUCKET_" + layer.upper()] = (
        "dataforge-academy-919774751018-" + layer
    )

for value in values.values():
    if "\n" in value or "\r" in value:
        raise SystemExit("Unexpected newline in runtime configuration.")

Path(".env.aws").write_text(
    "".join(f"{key}={value}\n" for key, value in values.items())
)
Path(".env.aws").chmod(0o600)

Path(".env.compose").write_text(
    "AIRFLOW_DB_PASSWORD=" + internal["airflow_db"] + "\n"
)
Path(".env.compose").chmod(0o600)

compose = Path("compose.aws.yml")
content = compose.read_text()
content = content.replace(
    "  env_file: .env.aws",
    "  env_file:\n    - path: .env.aws\n      format: raw",
)
compose.write_text(content)

print("Runtime configuration prepared.")
PY

export COMPOSE_PARALLEL_LIMIT=1
docker compose --env-file .env.compose -f compose.aws.yml config --quiet
docker compose --env-file .env.compose -f compose.aws.yml up -d --build
docker compose --env-file .env.compose -f compose.aws.yml ps

echo DATAFORGE_CONTAINERS_STARTED

