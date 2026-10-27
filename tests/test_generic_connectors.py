import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd

from src.connectors import (
    ConnectorConfigurationError,
    ConnectorConnectionError,
    FileConnector,
    PostgresConnector,
    RestConnector,
    get_connector,
    get_dataset_connector,
)
from src.connectors.credentials import (
    connection_env_name,
    resolve_connection_reference,
)
from src.contracts import load_contract
from src.contracts.models import (
    SourceConfig,
    SourceObjectConfig,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FileConnectorTests(unittest.TestCase):

    def _source(self):
        return SourceConfig(
            code="demo-file",
            name="Demo File",
            type="file",
        )

    def test_csv_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.csv"

            path.write_text(
                "id,name\n1,Ana\n2,Beto\n",
                encoding="utf-8",
            )

            connector = FileConnector(
                source=self._source(),
                source_object=SourceObjectConfig(
                    path=str(path),
                    format="csv",
                ),
            )

            frame = connector.extract()

            self.assertEqual(len(frame), 2)

            self.assertEqual(
                list(frame.columns),
                ["id", "name"],
            )

            self.assertEqual(
                frame.iloc[0]["name"],
                "Ana",
            )

    def test_json_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"

            path.write_text(
                json.dumps(
                    [
                        {
                            "id": 1,
                            "name": "Ana",
                        },
                        {
                            "id": 2,
                            "name": "Beto",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            connector = FileConnector(
                source=self._source(),
                source_object=SourceObjectConfig(
                    path=str(path),
                    format="json",
                ),
            )

            frame = connector.extract()

            self.assertEqual(len(frame), 2)

    def test_parquet_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.parquet"

            expected = pd.DataFrame(
                {
                    "id": [1, 2],
                    "amount": [10.5, 20.0],
                }
            )

            expected.to_parquet(
                path,
                index=False,
                engine="pyarrow",
            )

            connector = FileConnector(
                source=self._source(),
                source_object=SourceObjectConfig(
                    path=str(path),
                    format="parquet",
                ),
            )

            actual = connector.extract()

            self.assertEqual(
                len(actual),
                2,
            )

            self.assertEqual(
                list(actual.columns),
                ["id", "amount"],
            )

    def test_missing_file_returns_traceable_error(self):
        connector = FileConnector(
            source=self._source(),
            source_object=SourceObjectConfig(
                path="missing-file.csv",
                format="csv",
            ),
        )

        with self.assertRaises(
            ConnectorConnectionError
        ):
            connector.extract()

    def test_connection_succeeds_for_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.csv"

            path.write_text(
                "id,name\n1,Ana\n",
                encoding="utf-8",
            )

            connector = FileConnector(
                source=self._source(),
                source_object=SourceObjectConfig(
                    path=str(path),
                    format="csv",
                ),
            )

            self.assertTrue(
                connector.test_connection()
            )


class CredentialTests(unittest.TestCase):

    def test_connection_reference_env_name(self):
        self.assertEqual(
            connection_env_name(
                "demo-postgres"
            ),
            (
                "DATAFORGE_CONNECTION_"
                "DEMO_POSTGRES"
            ),
        )

    def test_connection_reference_resolves_json(self):
        environment = {
            (
                "DATAFORGE_CONNECTION_"
                "DEMO_POSTGRES"
            ): json.dumps(
                {
                    "host": "localhost",
                    "database": "sales",
                }
            )
        }

        connection = (
            resolve_connection_reference(
                "demo-postgres",
                environ=environment,
            )
        )

        self.assertEqual(
            connection["database"],
            "sales",
        )


class RegistryTests(unittest.TestCase):

    def test_registry_uses_contract_source_type(self):
        source = SourceConfig(
            code="file",
            name="File",
            type="file",
        )

        source_object = SourceObjectConfig(
            path="demo.csv",
            format="csv",
        )

        connector = get_connector(
            source,
            source_object,
        )

        self.assertIsInstance(
            connector,
            FileConnector,
        )

    def test_postgres_contract_selects_postgres_connector(self):
        contract = load_contract(
            PROJECT_ROOT
            / "config"
            / "examples"
            / "postgres_sales.yaml"
        )

        environment = {
            (
                "DATAFORGE_CONNECTION_"
                "DEMO_POSTGRES"
            ): json.dumps(
                {
                    "host": "localhost",
                    "port": 5432,
                    "database": "sales",
                    "user": "demo",
                    "password": "secret",
                }
            )
        }

        connector = get_dataset_connector(
            contract,
            "sales",
            environ=environment,
        )

        self.assertIsInstance(
            connector,
            PostgresConnector,
        )


class PostgresConnectorTests(unittest.TestCase):

    def test_select_query_is_accepted(self):
        query = (
            PostgresConnector
            ._validate_read_query(
                "SELECT * FROM sales"
            )
        )

        self.assertEqual(
            query,
            "SELECT * FROM sales",
        )

    def test_non_select_query_is_rejected(self):
        with self.assertRaises(
            ConnectorConfigurationError
        ):
            (
                PostgresConnector
                ._validate_read_query(
                    "DELETE FROM sales"
                )
            )

    def test_multiple_statements_are_rejected(self):
        with self.assertRaises(
            ConnectorConfigurationError
        ):
            (
                PostgresConnector
                ._validate_read_query(
                    (
                        "SELECT * FROM sales; "
                        "DELETE FROM sales"
                    )
                )
            )

    @patch(
        "src.connectors.postgres_connector."
        "psycopg.connect"
    )
    def test_postgres_connection_test(
            self,
            mocked_connect,
    ):
        connection = MagicMock()
        cursor = MagicMock()

        mocked_connect.return_value.__enter__.return_value = (
            connection
        )

        connection.cursor.return_value.__enter__.return_value = (
            cursor
        )

        cursor.fetchone.return_value = (1,)

        connector = PostgresConnector(
            source=SourceConfig(
                code="demo-postgres",
                name="Demo PostgreSQL",
                type="postgresql",
            ),
            source_object=SourceObjectConfig(
                schema="public",
                table="sales",
            ),
            connection={
                "host": "localhost",
                "port": 5432,
                "database": "sales",
                "user": "demo",
                "password": "secret",
            },
        )

        self.assertTrue(
            connector.test_connection()
        )


class RestConnectorTests(unittest.TestCase):

    def _source(self):
        return SourceConfig(
            code="demo-api",
            name="Demo API",
            type="rest",
        )

    @patch(
        "src.connectors.rest_connector."
        "requests.get"
    )
    def test_rest_extracts_items(
        self,
        mocked_get,
    ):
        response = Mock()

        response.raise_for_status.return_value = (
            None
        )

        response.json.return_value = {
            "items": [
                {
                    "id": 1,
                    "name": "Alpha",
                },
                {
                    "id": 2,
                    "name": "Beta",
                },
            ]
        }

        mocked_get.return_value = response

        connector = RestConnector(
            source=self._source(),
            source_object=SourceObjectConfig(
                endpoint=(
                    "https://example.com/items"
                ),
            ),
        )

        frame = connector.extract()

        self.assertEqual(
            len(frame),
            2,
        )

        self.assertEqual(
            frame.iloc[0]["name"],
            "Alpha",
        )

    @patch(
        "src.connectors.rest_connector."
        "requests.get"
    )
    def test_page_pagination(
        self,
        mocked_get,
    ):
        first_response = Mock()

        first_response.raise_for_status.return_value = (
            None
        )

        first_response.json.return_value = {
            "items": [
                {"id": 1},
                {"id": 2},
            ]
        }

        second_response = Mock()

        second_response.raise_for_status.return_value = (
            None
        )

        second_response.json.return_value = {
            "items": [
                {"id": 3},
            ]
        }

        mocked_get.side_effect = [
            first_response,
            second_response,
        ]

        connector = RestConnector(
            source=self._source(),
            source_object=SourceObjectConfig(
                endpoint=(
                    "https://example.com/items"
                ),
                pagination={
                    "strategy": "page",
                    "page_size": 2,
                    "max_pages": 5,
                },
            ),
        )

        frame = connector.extract()

        self.assertEqual(
            list(frame["id"]),
            [1, 2, 3],
        )

        self.assertEqual(
            mocked_get.call_count,
            2,
        )

    @patch(
        "src.connectors.rest_connector."
        "requests.get"
    )
    def test_rest_connection_test(
            self,
            mocked_get,
    ):
        response = Mock()

        response.raise_for_status.return_value = None
        response.json.return_value = {
            "items": []
        }

        mocked_get.return_value = response

        connector = RestConnector(
            source=self._source(),
            source_object=SourceObjectConfig(
                endpoint=(
                    "https://example.com/items"
                ),
            ),
        )

        self.assertTrue(
            connector.test_connection()
        )


if __name__ == "__main__":
    unittest.main()