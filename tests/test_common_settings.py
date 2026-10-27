"""Unit tests for environment-specific runtime configuration (#32)."""

import unittest
from unittest.mock import patch

from src.common.clients import create_s3_client
from src.common.settings import SettingsError, get_settings


LOCAL_ENV = {
    "DATAFORGE_ENV": "local",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "dataforge",
    "POSTGRES_USER": "dataforge",
    "POSTGRES_PASSWORD": "secret",
    "MINIO_ENDPOINT": "http://localhost:9000",
    "MINIO_ROOT_USER": "dataforge",
    "MINIO_ROOT_PASSWORD": "minio-secret",
}

AWS_ENV = {
    "DATAFORGE_ENV": "aws",
    "POSTGRES_HOST": "dataforge.abc123.us-east-1.rds.amazonaws.com",
    "POSTGRES_DB": "dataforge",
    "POSTGRES_USER": "dataforge_app",
    "POSTGRES_PASSWORD": "from-secrets-manager",
    "POSTGRES_SSLMODE": "require",
    "AWS_REGION": "us-east-1",
    "MINIO_BUCKET_BRONZE": "acme-dataforge-bronze",
}


class SettingsTests(unittest.TestCase):
    def test_local_settings_are_valid(self):
        settings = get_settings(LOCAL_ENV)
        self.assertEqual(settings.environment, "local")
        self.assertEqual(settings.problems(), [])
        self.assertEqual(settings.log_format, "text")
        self.assertEqual(settings.storage.bucket("bronze"), "dataforge-bronze")

    def test_aws_settings_need_no_storage_endpoint_or_keys(self):
        settings = get_settings(AWS_ENV)
        self.assertEqual(settings.problems(), [])
        self.assertIsNone(settings.storage.endpoint_url)
        self.assertIsNone(settings.storage.access_key_id)
        self.assertEqual(settings.log_format, "json")
        self.assertEqual(settings.storage.bucket("bronze"), "acme-dataforge-bronze")
        self.assertEqual(settings.postgres.connection_kwargs()["sslmode"], "require")

    def test_aws_rejects_placeholder_credentials_and_localhost(self):
        env = {
            **AWS_ENV,
            "POSTGRES_PASSWORD": "change_me_postgres",
            "MINIO_ENDPOINT": "http://localhost:9000",
        }
        problems = get_settings(env).problems()
        self.assertTrue(any("change_me" in p for p in problems))
        self.assertTrue(any("localhost" in p for p in problems))

    def test_missing_values_are_reported(self):
        settings = get_settings({"DATAFORGE_ENV": "test"})
        problems = settings.problems()
        self.assertIn("POSTGRES_HOST is not set", problems)
        self.assertTrue(any("MINIO_ENDPOINT" in p for p in problems))
        with self.assertRaises(SettingsError):
            settings.postgres.connection_kwargs()

    def test_unknown_environment_and_log_format_are_reported(self):
        problems = get_settings(
            {**LOCAL_ENV, "DATAFORGE_ENV": "prod", "DATAFORGE_LOG_FORMAT": "xml"}
        ).problems()
        self.assertTrue(any("DATAFORGE_ENV" in p for p in problems))
        self.assertTrue(any("DATAFORGE_LOG_FORMAT" in p for p in problems))

    def test_storage_endpoint_override_takes_precedence(self):
        settings = get_settings(
            {**LOCAL_ENV, "DATAFORGE_STORAGE_ENDPOINT": "http://minio:9000"}
        )
        self.assertEqual(settings.storage.endpoint_url, "http://minio:9000")

    def test_unknown_layer_raises(self):
        with self.assertRaises(SettingsError):
            get_settings(LOCAL_ENV).storage.bucket("platinum")


class S3ClientTests(unittest.TestCase):
    @patch("src.common.clients.boto3.client")
    def test_local_client_uses_minio_endpoint_and_keys(self, mocked_client):
        create_s3_client(get_settings(LOCAL_ENV))
        kwargs = mocked_client.call_args.kwargs
        self.assertEqual(kwargs["endpoint_url"], "http://localhost:9000")
        self.assertEqual(kwargs["aws_access_key_id"], "dataforge")

    @patch("src.common.clients.boto3.client")
    def test_aws_client_uses_default_credential_chain(self, mocked_client):
        create_s3_client(get_settings(AWS_ENV))
        kwargs = mocked_client.call_args.kwargs
        self.assertNotIn("endpoint_url", kwargs)
        self.assertNotIn("aws_access_key_id", kwargs)
        self.assertEqual(kwargs["region_name"], "us-east-1")


if __name__ == "__main__":
    unittest.main()
