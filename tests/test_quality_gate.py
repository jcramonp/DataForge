import unittest

import pandas as pd

from src.quality.validate_olist import RULES, between_mask, in_set_mask, regex_mask


class QualityGateTests(unittest.TestCase):
    def test_between_mask_flags_invalid_and_can_allow_null(self):
        frame = pd.DataFrame({"value": [1, 0, -1, None]})
        mask = between_mask("value", 1, allow_null=True)(frame)
        self.assertEqual(mask.tolist(), [False, True, True, False])

    def test_between_mask_can_reject_null(self):
        frame = pd.DataFrame({"value": [1, None]})
        mask = between_mask("value", 1, allow_null=False)(frame)
        self.assertEqual(mask.tolist(), [False, True])

    def test_in_set_mask_flags_unknown_non_null_values(self):
        frame = pd.DataFrame({"status": ["delivered", "mystery", None]})
        mask = in_set_mask("status", {"delivered", "canceled"})(frame)
        self.assertEqual(mask.tolist(), [False, True, False])

    def test_regex_mask_flags_invalid_state_format(self):
        frame = pd.DataFrame({"state": ["SP", "sp", "SPO", None]})
        mask = regex_mask("state", r"^[A-Z]{2}$")(frame)
        self.assertEqual(mask.tolist(), [False, True, True, False])

    def test_product_category_rule_is_warning_only(self):
        rule = next(rule for rule in RULES["products"] if rule.name == "product_category_present")
        self.assertEqual(rule.severity, "warning")

    def test_zero_product_weight_is_critical(self):
        rule = next(rule for rule in RULES["products"] if rule.name == "product_weight_positive_when_present")
        frame = pd.DataFrame({"product_weight_g": [100, 0, None]})
        self.assertEqual(rule.invalid_mask(frame).tolist(), [False, True, False])
        self.assertEqual(rule.severity, "critical")


if __name__ == "__main__":
    unittest.main()
