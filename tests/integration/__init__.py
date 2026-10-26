"""Integration tests against real PostgreSQL and S3-compatible storage (#32).

They are skipped unless ``DATAFORGE_INTEGRATION=1``. They reset the database
schema, so they refuse to run unless ``DATAFORGE_ENV=test``.

Locally (throwaway containers, see docs/operations/runbook.md)::

    DATAFORGE_ENV_FILE=config/environments/test.env DATAFORGE_INTEGRATION=1 \
        python -m unittest discover -s tests/integration -t .
"""

import os
import unittest

from src.common.clients import connect_postgres, create_s3_client
from src.common.settings import Settings, get_settings


INTEGRATION_ENABLED = os.environ.get("DATAFORGE_INTEGRATION") == "1"

requires_integration = unittest.skipUnless(
    INTEGRATION_ENABLED,
    "set DATAFORGE_INTEGRATION=1 to run integration tests",
)


def integration_settings() -> Settings:
    settings = get_settings()
    if settings.environment != "test":
        raise RuntimeError(
            "Integration tests reset the control-plane schema; refusing to run "
            f"with DATAFORGE_ENV='{settings.environment}' (expected 'test')."
        )
    return settings


def reset_database(settings: Settings) -> None:
    with connect_postgres(settings, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE")
            cur.execute("CREATE SCHEMA public")


def reset_buckets(settings: Settings, prefix: str) -> None:
    s3 = create_s3_client(settings)
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    for bucket in settings.storage.buckets.values():
        if bucket not in existing:
            s3.create_bucket(Bucket=bucket)
        listing = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        for item in listing.get("Contents", []):
            s3.delete_object(Bucket=bucket, Key=item["Key"])


def fetch_all(settings: Settings, query: str, params: tuple = ()) -> list[tuple]:
    with connect_postgres(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

