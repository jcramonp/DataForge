"""Unit tests for orchestration plan resolution (#24)."""

import tempfile
import unittest
from pathlib import Path

import yaml

from src.orchestration.plan import STAGES, PipelinePlan, PlanError, build_plan


OLIST = "config/examples/olist.yaml"
RETAIL = "tests/fixtures/e2e/retail_contract.yaml"
POSTGRES_SALES = "config/examples/postgres_sales.yaml"


class BuildPlanTests(unittest.TestCase):
    def test_defaults_run_every_stage_dataset_and_enabled_gold(self):
        plan = build_plan(OLIST)
        self.assertEqual(plan.stages, list(STAGES))
        self.assertEqual(plan.datasets, ["customers", "orders", "order_items", "products"])
        self.assertEqual(plan.gold, ["order_items_gold"])
        self.assertEqual(plan.contract_path, OLIST)
        self.assertEqual((plan.client_code, plan.project_code, plan.source_code), ("olist", "olist-alpha", "olist-csv"))
        self.assertEqual(plan.certification, "evaluate")

    def test_same_plan_shape_for_a_structurally_different_source(self):
        plan = build_plan(POSTGRES_SALES)
        self.assertEqual(plan.datasets, ["sales"])
        self.assertEqual(plan.gold, ["sales_gold"])
        self.assertEqual(plan.source_code, "sales-postgres")

    def test_subset_and_comma_separated_values_keep_pipeline_order(self):
        plan = build_plan(OLIST, datasets="products, orders", stages="silver,bronze")
        self.assertEqual(plan.stages, ["bronze", "silver"])
        self.assertEqual(plan.datasets, ["orders", "products"])
        self.assertEqual(plan.gold, [])

    def test_targets_and_expected_tasks(self):
        plan = build_plan(RETAIL)
        self.assertEqual(plan.targets("bronze"), ["orders"])
        self.assertEqual(plan.targets("gold"), ["orders_by_status"])
        self.assertEqual(plan.targets("certification"), ["contract"])
        self.assertEqual(
            plan.expected_tasks(),
            [
                ("bronze", "orders"),
                ("profiling", "orders"),
                ("silver", "orders"),
                ("gold", "orders_by_status"),
                ("certification", "contract"),
            ],
        )

    def test_unselected_stage_has_no_targets(self):
        plan = build_plan(RETAIL, stages=["bronze"])
        self.assertEqual(plan.targets("silver"), [])
        self.assertEqual(plan.expected_tasks(), [("bronze", "orders")])

    def test_round_trip_serialization(self):
        plan = build_plan(RETAIL, certification="validate")
        self.assertEqual(PipelinePlan.from_dict(plan.to_dict()), plan)

    def test_absolute_path_is_accepted_and_resolved(self):
        absolute = Path(RETAIL).resolve()
        plan = build_plan(str(absolute))
        self.assertEqual(plan.contract_path, RETAIL)
        self.assertEqual(plan.absolute_contract_path(), absolute)


class PlanValidationTests(unittest.TestCase):
    def assert_plan_error(self, message: str, *args, **kwargs):
        with self.assertRaises(PlanError) as ctx:
            build_plan(*args, **kwargs)
        self.assertIn(message, str(ctx.exception))

    def test_missing_contract(self):
        self.assert_plan_error("not found", "config/examples/missing.yaml")

    def test_unknown_stage(self):
        self.assert_plan_error("Unknown stage", RETAIL, stages=["bronze", "platinum"])

    def test_unknown_dataset(self):
        self.assert_plan_error("Unknown dataset", RETAIL, datasets=["invoices"])

    def test_unknown_gold(self):
        self.assert_plan_error("Unknown Gold", RETAIL, gold=["nope"])

    def test_gold_requested_without_gold_stage(self):
        self.assert_plan_error("'gold' stage is not selected", RETAIL, gold=["orders_by_status"], stages=["bronze"])

    def test_unknown_certification_mode(self):
        self.assert_plan_error("certification mode", RETAIL, certification="certify")

    def test_invalid_contract_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "broken.yaml")
            path.write_text("contract_version: '1.0'\nclient: {code: x}\n", encoding="utf-8")
            self.assert_plan_error("Invalid contract", str(path))

    def test_disabled_gold_is_not_selected_and_cannot_be_requested(self):
        raw = yaml.safe_load(Path(RETAIL).read_text(encoding="utf-8"))
        raw["gold"][0]["enabled"] = False
        raw["datasets"][0]["source_object"]["path"] = str(Path("tests/fixtures/e2e/orders.csv").resolve())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "disabled_gold.yaml")
            path.write_text(yaml.safe_dump(raw), encoding="utf-8")
            self.assertEqual(build_plan(str(path)).gold, [])
            self.assert_plan_error("disabled", str(path), gold=["orders_by_status"])


if __name__ == "__main__":
    unittest.main()
