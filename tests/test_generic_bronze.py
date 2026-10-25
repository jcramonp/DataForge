import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from src.contracts.models import (
    DataForgeContract,
)
from src.ingestion.bronze_generic import (
    dataframe_checksum,
    extract_dataset,
    ingest_dataset,
)


class GenericBronzeTests(unittest.TestCase):

    def test_dataframe_checksum_is_deterministic(self):
        frame = pd.DataFrame(
            {
                "id": [1, 2],
                "name": ["A", "B"],
            }
        )

        first = dataframe_checksum(frame)
        second = dataframe_checksum(frame)

        self.assertEqual(
            first,
            second,
        )

    def test_same_service_extracts_csv_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sales.csv"

            path.write_text(
                (
                    "sale_id,amount\n"
                    "S1,10.5\n"
                    "S2,20.0\n"
                ),
                encoding="utf-8",
            )

            contract = DataForgeContract(
                client={
                    "code": "demo",
                    "name": "Demo",
                },
                project={
                    "code": "demo-project",
                    "name": "Demo Project",
                },
                source={
                    "code": "demo-file",
                    "name": "Demo File",
                    "type": "file",
                },
                datasets=[
                    {
                        "code": "sales",
                        "name": "Sales",
                        "source_object": {
                            "path": str(path),
                            "format": "csv",
                        },
                        "schema": [
                            {
                                "name": "sale_id",
                                "type": "string",
                            },
                            {
                                "name": "amount",
                                "type": "float",
                            },
                        ],
                    }
                ],
            )

            frame = extract_dataset(
                contract,
                "sales",
            )

            self.assertEqual(
                len(frame),
                2,
            )

            self.assertEqual(
                list(frame.columns),
                [
                    "sale_id",
                    "amount",
                ],
            )

    @patch(
        "src.connectors.rest_connector."
        "requests.get"
    )
    def test_same_service_extracts_rest_source(
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
                    "sale_id": "R1",
                    "amount": 30.0,
                },
                {
                    "sale_id": "R2",
                    "amount": 40.0,
                },
            ]
        }

        mocked_get.return_value = response

        contract = DataForgeContract(
            client={
                "code": "demo",
                "name": "Demo",
            },
            project={
                "code": "rest-project",
                "name": "REST Project",
            },
            source={
                "code": "sales-api",
                "name": "Sales API",
                "type": "rest",
            },
            datasets=[
                {
                    "code": "sales",
                    "name": "Sales",
                    "source_object": {
                        "endpoint": (
                            "https://example.com/sales"
                        ),
                    },
                    "schema": [
                        {
                            "name": "sale_id",
                            "type": "string",
                        },
                        {
                            "name": "amount",
                            "type": "float",
                        },
                    ],
                }
            ],
        )

        frame = extract_dataset(
            contract,
            "sales",
        )

        self.assertEqual(
            len(frame),
            2,
        )

        self.assertEqual(
            frame.iloc[1]["sale_id"],
            "R2",
        )

    def test_csv_completes_generic_bronze_ingestion(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "sales.csv"

            source_path.write_text(
                (
                    "sale_id,amount\n"
                    "S1,10.5\n"
                    "S2,20.0\n"
                ),
                encoding="utf-8",
            )

            contract = DataForgeContract(
                client={
                    "code": "demo",
                    "name": "Demo",
                },
                project={
                    "code": "csv-project",
                    "name": "CSV Project",
                },
                source={
                    "code": "csv-source",
                    "name": "CSV Source",
                    "type": "file",
                },
                datasets=[
                    {
                        "code": "sales",
                        "name": "Sales",
                        "source_object": {
                            "path": str(source_path),
                            "format": "csv",
                        },
                        "schema": [
                            {
                                "name": "sale_id",
                                "type": "string",
                            },
                            {
                                "name": "amount",
                                "type": "float",
                            },
                        ],
                    }
                ],
            )

            connection = Mock()
            s3 = Mock()

            with (
                patch(
                    "src.ingestion.bronze_generic."
                    "ensure_control_plane_records",
                    return_value=1,
                ),
                patch(
                    "src.ingestion.bronze_generic."
                    "register_dataset_version",
                    return_value=2,
                ),
                patch(
                    "src.ingestion.bronze_generic."
                    "start_pipeline_run",
                    return_value=3,
                ),
                patch(
                    "src.ingestion.bronze_generic."
                    "register_bronze_asset"
                ) as register_asset,
                patch(
                    "src.ingestion.bronze_generic."
                    "finish_pipeline_run"
                ) as finish_run,
            ):
                result = ingest_dataset(
                    contract=contract,
                    dataset_code="sales",
                    s3=s3,
                    conn=connection,
                    bucket="bronze-test",
                )

            self.assertEqual(
                result["source_type"],
                "file",
            )

            self.assertEqual(
                result["rows"],
                2,
            )

            self.assertEqual(
                result["run_id"],
                3,
            )

            self.assertTrue(
                result["storage_uri"].startswith(
                    "s3://bronze-test/"
                )
            )

            s3.upload_file.assert_called_once()
            register_asset.assert_called_once()

            finish_run.assert_called_once_with(
                connection,
                3,
                "success",
                accepted_rows=2,
            )

    @patch(
        "src.connectors.rest_connector."
        "requests.get"
    )
    def test_rest_completes_generic_bronze_ingestion(
            self,
            mocked_get,
    ):
        response = Mock()

        response.raise_for_status.return_value = None

        response.json.return_value = {
            "items": [
                {
                    "sale_id": "R1",
                    "amount": 30.0,
                },
                {
                    "sale_id": "R2",
                    "amount": 40.0,
                },
            ]
        }

        mocked_get.return_value = response

        contract = DataForgeContract(
            client={
                "code": "demo",
                "name": "Demo",
            },
            project={
                "code": "rest-project",
                "name": "REST Project",
            },
            source={
                "code": "rest-source",
                "name": "REST Source",
                "type": "rest",
            },
            datasets=[
                {
                    "code": "sales",
                    "name": "Sales",
                    "source_object": {
                        "endpoint": (
                            "https://example.com/sales"
                        ),
                    },
                    "schema": [
                        {
                            "name": "sale_id",
                            "type": "string",
                        },
                        {
                            "name": "amount",
                            "type": "float",
                        },
                    ],
                }
            ],
        )

        connection = Mock()
        s3 = Mock()

        with (
            patch(
                "src.ingestion.bronze_generic."
                "ensure_control_plane_records",
                return_value=10,
            ),
            patch(
                "src.ingestion.bronze_generic."
                "register_dataset_version",
                return_value=20,
            ),
            patch(
                "src.ingestion.bronze_generic."
                "start_pipeline_run",
                return_value=30,
            ),
            patch(
                "src.ingestion.bronze_generic."
                "register_bronze_asset"
            ) as register_asset,
            patch(
                "src.ingestion.bronze_generic."
                "finish_pipeline_run"
            ) as finish_run,
        ):
            result = ingest_dataset(
                contract=contract,
                dataset_code="sales",
                s3=s3,
                conn=connection,
                bucket="bronze-test",
            )

        self.assertEqual(
            result["source_type"],
            "rest",
        )

        self.assertEqual(
            result["rows"],
            2,
        )

        self.assertEqual(
            result["run_id"],
            30,
        )

        s3.upload_file.assert_called_once()
        register_asset.assert_called_once()

        finish_run.assert_called_once_with(
            connection,
            30,
            "success",
            accepted_rows=2,
        )


if __name__ == "__main__":
    unittest.main()