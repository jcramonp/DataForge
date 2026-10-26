"""Structure of the generic dataforge_pipeline DAG (#24).

Airflow is not a project dependency, so these tests skip locally unless
Airflow is installed. CI runs them inside the Airflow image (job "Airflow DAG").
"""

import importlib.util
import unittest
from pathlib import Path


def _airflow_installed() -> bool:
    # The repository's own airflow/ folder (Dockerfile, dags/) makes a bare
    # "airflow" importable as a namespace package, so probe the real SDK.
    try:
        return importlib.util.find_spec("airflow.sdk") is not None
    except ModuleNotFoundError:
        return False


AIRFLOW_INSTALLED = _airflow_installed()

DAGS_FOLDER = Path(__file__).resolve().parents[1] / "airflow" / "dags"


@unittest.skipUnless(AIRFLOW_INSTALLED, "Apache Airflow is not installed")
class DataforgePipelineDagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from airflow.dag_processing.dagbag import DagBag

        cls.bag = DagBag(str(DAGS_FOLDER))
        cls.dag = cls.bag.dags.get("dataforge_pipeline")

    def test_dags_import_without_errors(self):
        self.assertEqual(self.bag.import_errors, {})
        self.assertIsNotNone(self.dag)

    def test_single_generic_dag_is_parameterized_by_contract(self):
        self.assertEqual(
            set(self.dag.params.keys()),
            {"contract", "datasets", "gold", "stages", "certification"},
        )
        self.assertIsNone(self.dag.schedule)
        self.assertFalse(self.dag.catchup)

    def test_task_graph(self):
        upstream = {t.task_id: set(t.upstream_task_ids) for t in self.dag.tasks}
        self.assertIn("dataset.bronze", upstream["dataset.profiling"])
        self.assertIn("dataset.profiling", upstream["dataset.silver"])
        self.assertIn("dataset.silver", upstream["gold"])
        self.assertTrue({"gold", "dataset.silver"} <= upstream["certification"])
        self.assertIn("certification", upstream["finalize"])
        self.assertIn("start_run", upstream["dataset.bronze"])

    def test_retry_and_trigger_policy(self):
        tasks = {t.task_id: t for t in self.dag.tasks}
        for task_id in ("dataset.bronze", "dataset.profiling", "dataset.silver", "gold", "certification"):
            self.assertEqual(tasks[task_id].retries, 2, task_id)
            self.assertEqual(tasks[task_id].trigger_rule, "none_failed", task_id)
        self.assertEqual(tasks["finalize"].trigger_rule, "all_done")
        self.assertEqual(tasks["finalize"].retries, 0)
        self.assertEqual(tasks["resolve_plan"].retries, 0)


if __name__ == "__main__":
    unittest.main()
