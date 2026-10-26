"""A failed pipeline must be traceable through logs to its run and dataset (#32)."""

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.common.log import ContextFilter
from src.contracts.models import DataForgeContract
from src.ingestion.bronze_generic import ingest_dataset
from src.transformations.silver_runner import execute_silver_pipeline_for_dataset


class CapturingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []
        self.addFilter(ContextFilter())

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def build_contract(source_path: Path) -> DataForgeContract:
    return DataForgeContract(
        client={"code": "demo", "name": "Demo"},
        project={"code": "obs-project", "name": "Observability Project"},
        source={"code": "csv-source", "name": "CSV Source", "type": "file"},
        datasets=[
            {
                "code": "sales",
                "name": "Sales",
                "source_object": {"path": str(source_path), "format": "csv"},
                "schema": [
                    {"name": "sale_id", "type": "string"},
                    {"name": "amount", "type": "float"},
                ],
            }
        ],
    )


class PipelineTraceabilityTests(unittest.TestCase):
    def capture(self, logger_name: str) -> CapturingHandler:
        handler = CapturingHandler()
        logger = logging.getLogger(logger_name)
        previous_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        self.addCleanup(logger.removeHandler, handler)
        self.addCleanup(logger.setLevel, previous_level)
        return handler

    def assert_failure_traceable(self, handler: CapturingHandler, run_id: int, stage: str) -> None:
        failures = [r for r in handler.records if r.levelno == logging.ERROR]
        self.assertEqual(len(failures), 1)
        context = failures[0].context
        self.assertEqual(context["run_id"], run_id)
        self.assertEqual(context["dataset"], "sales")
        self.assertEqual(context["client"], "demo")
        self.assertEqual(context["stage"], stage)
        self.assertIsNotNone(failures[0].exc_info)

    def test_failed_bronze_ingestion_logs_run_and_dataset(self):
        handler = self.capture("src.ingestion.bronze_generic")

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sales.csv"
            source.write_text("sale_id,amount\nS1,10.5\n", encoding="utf-8")
            contract = build_contract(source)

            s3 = Mock()
            s3.upload_file.side_effect = RuntimeError("object storage unavailable")

            with (
                patch("src.ingestion.bronze_generic.ensure_control_plane_records", return_value=1),
                patch("src.ingestion.bronze_generic.register_dataset_version", return_value=2),
                patch("src.ingestion.bronze_generic.start_pipeline_run", return_value=11),
                patch("src.ingestion.bronze_generic.finish_pipeline_run") as finish_run,
            ):
                with self.assertRaises(RuntimeError):
                    ingest_dataset(contract, "sales", s3=s3, conn=Mock(), bucket="bronze")

        self.assertEqual(finish_run.call_args.args[1:3], (11, "failed"))
        self.assertIn("object storage unavailable", finish_run.call_args.kwargs["error_message"])
        self.assert_failure_traceable(handler, run_id=11, stage="source_to_bronze")

    def test_successful_bronze_ingestion_logs_completion(self):
        handler = self.capture("src.ingestion.bronze_generic")

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sales.csv"
            source.write_text("sale_id,amount\nS1,10.5\n", encoding="utf-8")
            contract = build_contract(source)

            with (
                patch("src.ingestion.bronze_generic.ensure_control_plane_records", return_value=1),
                patch("src.ingestion.bronze_generic.register_dataset_version", return_value=2),
                patch("src.ingestion.bronze_generic.start_pipeline_run", return_value=12),
                patch("src.ingestion.bronze_generic.register_bronze_asset"),
                patch("src.ingestion.bronze_generic.finish_pipeline_run"),
            ):
                ingest_dataset(contract, "sales", s3=Mock(), conn=Mock(), bucket="bronze")

        finished = [r for r in handler.records if r.getMessage() == "Bronze ingestion finished"]
        self.assertEqual(len(finished), 1)
        self.assertEqual(finished[0].context["run_id"], 12)
        self.assertEqual(finished[0].rows, 1)

    def test_failed_silver_run_logs_run_and_dataset(self):
        handler = self.capture("src.transformations.silver_runner")
        contract = build_contract(Path("unused.csv"))

        s3 = Mock()
        s3.download_file.side_effect = RuntimeError("bronze object missing")
        bronze = {
            "dataset_version_id": 2,
            "source_checksum": "a" * 64,
            "storage_uri": "s3://bronze/demo/obs-project/sales/sales.parquet",
            "row_count": 1,
        }

        with (
            patch("src.transformations.silver_runner.latest_bronze_asset", return_value=bronze),
            patch("src.transformations.silver_runner.start_pipeline_run", return_value=21),
            patch("src.transformations.silver_runner.finish_pipeline_run") as finish_run,
        ):
            with self.assertRaises(RuntimeError):
                execute_silver_pipeline_for_dataset(
                    contract, "sales", s3, Mock(), "silver", "quarantine"
                )

        self.assertEqual(finish_run.call_args.kwargs["status"], "failed")
        self.assert_failure_traceable(handler, run_id=21, stage="silver_quality_gate")


if __name__ == "__main__":
    unittest.main()
