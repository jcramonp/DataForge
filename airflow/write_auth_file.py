"""Write the Airflow simple-auth-manager password file from environment variables.

Runs before ``airflow api-server`` (see docker-compose.yml) so the UI/REST API
login is ``AIRFLOW_ADMIN_USERNAME`` / ``AIRFLOW_ADMIN_PASSWORD`` from ``.env``
instead of a random generated password, and no credential is committed.
"""

import json
import os
import sys
from pathlib import Path

username = os.environ.get("AIRFLOW_ADMIN_USERNAME", "").strip()
password = os.environ.get("AIRFLOW_ADMIN_PASSWORD", "")
target = os.environ.get("AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE", "")

if not username or not password or not target:
    sys.exit(
        "AIRFLOW_ADMIN_USERNAME, AIRFLOW_ADMIN_PASSWORD and "
        "AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE must be set"
    )

path = Path(target)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({username: password}), encoding="utf-8")
path.chmod(0o600)
print(f"Airflow admin user '{username}' configured")
