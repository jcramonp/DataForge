"""Comprehensive unit tests for generic Silver transformations and Quality Gate."""

import unittest
import pandas as pd

from src.contracts.models import (
    DataType,
    QualityRuleConfig,
    QualityRuleType,
    Severity,
    TransformationConfig,
    TransformationOperation,
)
from src.quality.quality_generic import (
    compute_invalid_mask,
    evaluate_quality_rules,
)
from src.transformations.silver_generic import (
    apply_cast,
    apply_lower,
    apply_transformations,
    apply_trim,
    apply_upper,
)


class GenericSilverTransformationTests(unittest.TestCase):
    def test_apply_trim(self):
        s = pd.Series(["  hello ", "world   ", None])
        res = apply_trim(s)
        self.assertEqual(res.tolist()[:2], ["hello", "world"])
        self.assertTrue(pd.isna(res.iloc[2]))

    def test_apply_lower_and_upper(self):
        s = pd.Series(["Hello", "WORLD", None])
        lower_res = apply_lower(s)
        self.assertEqual(lower_res.tolist()[:2], ["hello", "world"])

        upper_res = apply_upper(s)
        self.assertEqual(upper_res.tolist()[:2], ["HELLO", "WORLD"])

    def test_apply_cast_integer(self):
        s = pd.Series(["100", 250.0, None, "bad"])
        res = apply_cast(s, DataType.INTEGER)
        self.assertEqual(res.iloc[0], 100)
        self.assertEqual(res.iloc[1], 250)
        self.assertTrue(pd.isna(res.iloc[2]))
        self.assertTrue(pd.isna(res.iloc[3]))

    def test_apply_cast_float(self):
        s = pd.Series(["19.99", 50, None])
        res = apply_cast(s, DataType.FLOAT)
        self.assertAlmostEqual(res.iloc[0], 19.99)
        self.assertAlmostEqual(res.iloc[1], 50.0)
        self.assertTrue(pd.isna(res.iloc[2]))

    def test_apply_cast_boolean(self):
        s = pd.Series(["true", "False", "1", "0", True, None])
        res = apply_cast(s, DataType.BOOLEAN)
        self.assertTrue(res.iloc[0])
        self.assertFalse(res.iloc[1])
        self.assertTrue(res.iloc[2])
        self.assertFalse(res.iloc[3])
        self.assertTrue(res.iloc[4])
        self.assertTrue(pd.isna(res.iloc[5]))

    def test_apply_cast_datetime(self):
        s = pd.Series(["2026-01-01 10:00:00", "2026-05-10T12:00:00Z", None])
        res = apply_cast(s, DataType.DATETIME)
        self.assertEqual(res.iloc[0].year, 2026)
        self.assertEqual(res.iloc[0].month, 1)
        self.assertTrue(pd.isna(res.iloc[2]))

    def test_sequential_transformations_and_rename(self):
        df = pd.DataFrame(
            {
                "old_name": ["  ALPHA ", " BETA  "],
                "price_str": ["10.5", "20.0"],
                "status": ["PENDING", "ACTIVE"],
            }
        )
        transformations = [
            TransformationConfig(
                operation=TransformationOperation.RENAME,
                from_column="old_name",
                to_column="clean_name",
            ),
            TransformationConfig(
                operation=TransformationOperation.TRIM,
                column="clean_name",
            ),
            TransformationConfig(
                operation=TransformationOperation.LOWER,
                column="clean_name",
            ),
            TransformationConfig(
                operation=TransformationOperation.CAST,
                column="price_str",
                target_type=DataType.FLOAT,
            ),
            TransformationConfig(
                operation=TransformationOperation.LOWER,
                column="status",
            ),
        ]
        result = apply_transformations(df, transformations)

        self.assertIn("clean_name", result.columns)
        self.assertNotIn("old_name", result.columns)
        self.assertEqual(result["clean_name"].tolist(), ["alpha", "beta"])
        self.assertAlmostEqual(result["price_str"].iloc[0], 10.5)
        self.assertEqual(result["status"].tolist(), ["pending", "active"])


class GenericQualityEngineTests(unittest.TestCase):
    def test_not_null_rule(self):
        rule = QualityRuleConfig(
            name="check_not_null",
            rule=QualityRuleType.NOT_NULL,
            column="val",
            severity=Severity.CRITICAL,
        )
        s = pd.Series([1, 2, None, 4])
        mask = compute_invalid_mask(s, rule)
        self.assertEqual(mask.tolist(), [False, False, True, False])

    def test_unique_rule(self):
        rule = QualityRuleConfig(
            name="check_unique",
            rule=QualityRuleType.UNIQUE,
            column="id",
            severity=Severity.CRITICAL,
            allow_null=True,
        )
        s = pd.Series(["a", "b", "a", "c", None])
        mask = compute_invalid_mask(s, rule)
        # "a" appears twice -> both flagged; None is allowed
        self.assertEqual(mask.tolist(), [True, False, True, False, False])

    def test_numeric_comparison_rules(self):
        s = pd.Series([5, 10, 15, None])

        # greater_than 5 (allow_null=True) -> 5 is invalid
        rule_gt = QualityRuleConfig(
            name="gt_5",
            rule=QualityRuleType.GREATER_THAN,
            column="num",
            value=5,
            allow_null=True,
        )
        self.assertEqual(compute_invalid_mask(s, rule_gt).tolist(), [True, False, False, False])

        # greater_than_or_equal 5 -> 5 is valid
        rule_ge = QualityRuleConfig(
            name="ge_5",
            rule=QualityRuleType.GREATER_THAN_OR_EQUAL,
            column="num",
            value=5,
            allow_null=True,
        )
        self.assertEqual(compute_invalid_mask(s, rule_ge).tolist(), [False, False, False, False])

        # less_than 15 -> 15 is invalid
        rule_lt = QualityRuleConfig(
            name="lt_15",
            rule=QualityRuleType.LESS_THAN,
            column="num",
            value=15,
            allow_null=True,
        )
        self.assertEqual(compute_invalid_mask(s, rule_lt).tolist(), [False, False, True, False])

        # between 6 and 14 -> 5 and 15 are invalid
        rule_between = QualityRuleConfig(
            name="between_6_14",
            rule=QualityRuleType.BETWEEN,
            column="num",
            min_value=6,
            max_value=14,
            allow_null=True,
        )
        self.assertEqual(compute_invalid_mask(s, rule_between).tolist(), [True, False, True, False])

    def test_allowed_values_and_regex_rules(self):
        # Allowed values
        rule_allowed = QualityRuleConfig(
            name="status_valid",
            rule=QualityRuleType.ALLOWED_VALUES,
            column="status",
            values=["active", "inactive"],
            allow_null=True,
        )
        s_status = pd.Series(["active", "unknown", "inactive", None])
        self.assertEqual(
            compute_invalid_mask(s_status, rule_allowed).tolist(),
            [False, True, False, False],
        )

        # Regex rule
        rule_regex = QualityRuleConfig(
            name="state_code_regex",
            rule=QualityRuleType.REGEX,
            column="state",
            pattern="^[A-Z]{2}$",
            allow_null=True,
        )
        s_state = pd.Series(["SP", "RJ", "invalid", None])
        self.assertEqual(
            compute_invalid_mask(s_state, rule_regex).tolist(),
            [False, False, True, False],
        )

    def test_routing_critical_vs_warning(self):
        df = pd.DataFrame(
            {
                "customer_id": ["c1", "c2", "c3", "c4"],
                "score": [100, 200, -5, 50],
                "category": ["A", "B", None, "D"],
            }
        )

        rules = [
            # Critical rule: score must be positive. Row 2 (score=-5) fails!
            QualityRuleConfig(
                name="score_positive_critical",
                rule=QualityRuleType.GREATER_THAN_OR_EQUAL,
                column="score",
                value=0,
                severity=Severity.CRITICAL,
            ),
            # Warning rule: category should not be null. Row 2 has null category.
            QualityRuleConfig(
                name="category_not_null_warning",
                rule=QualityRuleType.NOT_NULL,
                column="category",
                severity=Severity.WARNING,
            ),
        ]

        valid_df, quarantine_df, results = evaluate_quality_rules(
            df, rules, dataset_code="customers_test"
        )

        # Only row 2 failed critical rule -> quarantine has 1 row
        self.assertEqual(len(quarantine_df), 1)
        self.assertEqual(quarantine_df.iloc[0]["customer_id"], "c3")

        # Validated has 3 rows (c1, c2, c4)
        self.assertEqual(len(valid_df), 3)
        self.assertEqual(valid_df["customer_id"].tolist(), ["c1", "c2", "c4"])

        # Check results
        self.assertEqual(len(results), 2)
        r_crit = next(r for r in results if r["rule_name"] == "score_positive_critical")
        self.assertEqual(r_crit["severity"], "critical")
        self.assertEqual(r_crit["failed_rows"], 1)

        r_warn = next(r for r in results if r["rule_name"] == "category_not_null_warning")
        self.assertEqual(r_warn["severity"], "warning")
        self.assertEqual(r_warn["failed_rows"], 1)

    def test_warning_rule_alone_does_not_quarantine(self):
        df = pd.DataFrame({"cat": ["A", None, "B"]})
        rules = [
            QualityRuleConfig(
                name="cat_warning",
                rule=QualityRuleType.NOT_NULL,
                column="cat",
                severity=Severity.WARNING,
            )
        ]
        valid_df, quarantine_df, results = evaluate_quality_rules(df, rules)
        # Zero rows quarantined even though 1 row failed warning rule
        self.assertEqual(len(quarantine_df), 0)
        self.assertEqual(len(valid_df), 3)
        self.assertEqual(results[0]["failed_rows"], 1)
        self.assertEqual(results[0]["severity"], "warning")


if __name__ == "__main__":
    unittest.main()
