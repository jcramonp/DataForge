import unittest

from pydantic import ValidationError

from src.contracts.models import (
    DataForgeContract,
    DatasetConfig,
    GoldStepConfig,
    QualityRuleConfig,
    TransformationConfig,
)


class ContractModelTests(unittest.TestCase):

    def test_valid_dataset(self):
        dataset = DatasetConfig(
            code="sales",
            name="Sales",
            source_object={
                "schema": "public",
                "table": "sales",
            },
            schema=[
                {
                    "name": "sale_id",
                    "type": "string",
                    "nullable": False,
                },
                {
                    "name": "amount",
                    "type": "float",
                    "nullable": False,
                },
            ],
            keys={
                "primary": ["sale_id"],
            },
            quality={
                "rules": [
                    {
                        "name": "amount_positive",
                        "rule": "greater_than_or_equal",
                        "column": "amount",
                        "value": 0,
                    }
                ]
            },
        )

        self.assertEqual(dataset.code, "sales")
        self.assertEqual(len(dataset.schema_), 2)

    def test_unknown_primary_key_is_rejected(self):
        with self.assertRaises(ValidationError):
            DatasetConfig(
                code="sales",
                name="Sales",
                source_object={
                    "schema": "public",
                    "table": "sales",
                },
                schema=[
                    {
                        "name": "sale_id",
                        "type": "string",
                    }
                ],
                keys={
                    "primary": ["missing_id"],
                },
            )

    def test_cast_without_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            TransformationConfig(
                operation="cast",
                column="amount",
            )

    def test_comparison_rule_without_value_is_rejected(self):
        with self.assertRaises(ValidationError):
            QualityRuleConfig(
                name="amount_positive",
                rule="greater_than",
                column="amount",
            )

    def test_incomplete_join_is_rejected(self):
        with self.assertRaises(ValidationError):
            GoldStepConfig(
                operation="join",
                right_dataset="customers",
            )

    def test_unknown_foreign_dataset_is_rejected(self):
        with self.assertRaises(ValidationError):
            DataForgeContract(
                client={
                    "code": "demo",
                    "name": "Demo",
                },
                project={
                    "code": "demo-project",
                    "name": "Demo Project",
                },
                source={
                    "code": "demo-db",
                    "name": "Demo DB",
                    "type": "postgresql",
                },
                datasets=[
                    {
                        "code": "orders",
                        "name": "Orders",
                        "source_object": {
                            "schema": "public",
                            "table": "orders",
                        },
                        "schema": [
                            {
                                "name": "order_id",
                                "type": "string",
                            },
                            {
                                "name": "customer_id",
                                "type": "string",
                            },
                        ],
                        "keys": {
                            "primary": ["order_id"],
                            "foreign": [
                                {
                                    "columns": ["customer_id"],
                                    "references": {
                                        "dataset": "customers",
                                        "columns": ["customer_id"],
                                    },
                                }
                            ],
                        },
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()