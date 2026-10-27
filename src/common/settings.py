"""Environment-specific runtime configuration for DataForge.

The same application code runs in every environment. Differences between
local Docker Compose, automated tests and the AWS reference deployment are
expressed only through environment variables:

- ``local``: MinIO + PostgreSQL containers, credentials from ``.env``.
- ``test``: CI/integration runs, usually throwaway service containers.
- ``aws``: Amazon S3 + RDS PostgreSQL. No storage endpoint and no static
  storage keys are needed; boto3 resolves credentials from the IAM role.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SUPPORTED_ENVIRONMENTS = ("local", "test", "aws")

PLACEHOLDER_MARKER = "change_me"


class SettingsError(RuntimeError):
    """Raised when required runtime configuration is missing or invalid."""


@dataclass(frozen=True)
class PostgresSettings:
    host: str | None
    port: int
    dbname: str | None
    user: str | None
    password: str | None
    sslmode: str | None = None
    connect_timeout: int = 5

    def missing(self) -> list[str]:
        required = {
            "POSTGRES_HOST": self.host,
            "POSTGRES_DB": self.dbname,
            "POSTGRES_USER": self.user,
            "POSTGRES_PASSWORD": self.password,
        }
        return [name for name, value in required.items() if not value]

    def connection_kwargs(self) -> dict[str, object]:
        missing = self.missing()
        if missing:
            raise SettingsError(
                "Missing PostgreSQL configuration: " + ", ".join(missing)
            )

        kwargs: dict[str, object] = {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
            "connect_timeout": self.connect_timeout,
        }
        if self.sslmode:
            kwargs["sslmode"] = self.sslmode
        return kwargs


@dataclass(frozen=True)
class StorageSettings:
    endpoint_url: str | None
    access_key_id: str | None
    secret_access_key: str | None
    region: str
    buckets: dict[str, str] = field(default_factory=dict)

    def bucket(self, layer: str) -> str:
        try:
            return self.buckets[layer]
        except KeyError as exc:
            raise SettingsError(f"Unknown storage layer '{layer}'") from exc


@dataclass(frozen=True)
class Settings:
    environment: str
    postgres: PostgresSettings
    storage: StorageSettings
    log_level: str
    log_format: str

    def problems(self) -> list[str]:
        """Return configuration problems without raising.

        Used by readiness checks and the health CLI so that a misconfigured
        deployment reports every issue at once.
        """

        issues: list[str] = []

        if self.environment not in SUPPORTED_ENVIRONMENTS:
            issues.append(
                f"DATAFORGE_ENV='{self.environment}' is not one of "
                f"{', '.join(SUPPORTED_ENVIRONMENTS)}"
            )

        issues.extend(
            f"{name} is not set" for name in self.postgres.missing()
        )

        if self.environment == "aws":
            if self.storage.endpoint_url and "localhost" in self.storage.endpoint_url:
                issues.append(
                    "Storage endpoint points to localhost in the aws environment"
                )
            secrets = (
                self.postgres.password or "",
                self.storage.secret_access_key or "",
            )
            if any(PLACEHOLDER_MARKER in value for value in secrets):
                issues.append(
                    "Placeholder 'change_me' credentials are not allowed in aws"
                )
        elif not self.storage.endpoint_url:
            issues.append(
                "MINIO_ENDPOINT (or DATAFORGE_STORAGE_ENDPOINT) is required "
                f"outside aws (environment '{self.environment}')"
            )

        if self.log_format not in {"json", "text"}:
            issues.append(
                f"DATAFORGE_LOG_FORMAT='{self.log_format}' must be 'json' or 'text'"
            )

        return issues


def load_environment_file(environ: Mapping[str, str] | None = None) -> None:
    """Load ``DATAFORGE_ENV_FILE`` (or the repository ``.env``) once.

    Variables already present in the process environment always win, so
    container/orchestrator configuration overrides local files.
    """

    source = environ if environ is not None else os.environ
    env_file = source.get("DATAFORGE_ENV_FILE")
    path = Path(env_file) if env_file else PROJECT_ROOT / ".env"
    if path.is_file():
        load_dotenv(path, override=False)


def _optional(environ: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = environ.get(name)
        if value:
            return value
    return None


def get_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build settings from the environment.

    Pass ``environ`` explicitly in tests; otherwise ``os.environ`` is used
    after loading the configured dotenv file.
    """

    if environ is None:
        load_environment_file()
        environ = os.environ

    environment = environ.get("DATAFORGE_ENV", "local").strip().lower()

    postgres = PostgresSettings(
        host=_optional(environ, "POSTGRES_HOST"),
        port=int(environ.get("POSTGRES_PORT", "5432")),
        dbname=_optional(environ, "POSTGRES_DB"),
        user=_optional(environ, "POSTGRES_USER"),
        password=_optional(environ, "POSTGRES_PASSWORD"),
        sslmode=_optional(environ, "POSTGRES_SSLMODE"),
        connect_timeout=int(environ.get("POSTGRES_CONNECT_TIMEOUT", "5")),
    )

    storage = StorageSettings(
        endpoint_url=_optional(
            environ, "DATAFORGE_STORAGE_ENDPOINT", "MINIO_ENDPOINT"
        ),
        access_key_id=_optional(
            environ, "DATAFORGE_STORAGE_ACCESS_KEY_ID", "MINIO_ROOT_USER"
        ),
        secret_access_key=_optional(
            environ, "DATAFORGE_STORAGE_SECRET_ACCESS_KEY", "MINIO_ROOT_PASSWORD"
        ),
        region=_optional(environ, "AWS_REGION", "AWS_DEFAULT_REGION") or "us-east-1",
        buckets={
            "bronze": environ.get("MINIO_BUCKET_BRONZE", "dataforge-bronze"),
            "silver": environ.get("MINIO_BUCKET_SILVER", "dataforge-silver"),
            "quarantine": environ.get(
                "MINIO_BUCKET_QUARANTINE", "dataforge-quarantine"
            ),
            "gold": environ.get("MINIO_BUCKET_GOLD", "dataforge-gold"),
        },
    )

    default_format = "text" if environment == "local" else "json"

    return Settings(
        environment=environment,
        postgres=postgres,
        storage=storage,
        log_level=environ.get("DATAFORGE_LOG_LEVEL", "INFO").upper(),
        log_format=environ.get("DATAFORGE_LOG_FORMAT", default_format).lower(),
    )
