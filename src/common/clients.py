"""Shared clients for the object-storage data plane and PostgreSQL control plane."""

from __future__ import annotations

import boto3
import psycopg
from botocore.config import Config

from src.common.settings import Settings, get_settings


def create_s3_client(settings: Settings | None = None):
    """Create an S3 client for MinIO (local/test) or Amazon S3 (aws).

    When no endpoint or static keys are configured, boto3 falls back to its
    default credential chain (IAM role, AWS profile, environment).
    """

    storage = (settings or get_settings()).storage

    kwargs: dict[str, object] = {
        "region_name": storage.region,
        "config": Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=60,
        ),
    }
    if storage.endpoint_url:
        kwargs["endpoint_url"] = storage.endpoint_url
    if storage.access_key_id and storage.secret_access_key:
        kwargs["aws_access_key_id"] = storage.access_key_id
        kwargs["aws_secret_access_key"] = storage.secret_access_key

    return boto3.client("s3", **kwargs)


def connect_postgres(settings: Settings | None = None, **overrides) -> psycopg.Connection:
    """Open a connection to the DataForge control-plane database."""

    kwargs = (settings or get_settings()).postgres.connection_kwargs()
    kwargs.update(overrides)
    return psycopg.connect(**kwargs)
