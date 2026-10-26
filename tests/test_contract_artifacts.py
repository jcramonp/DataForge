"""Regression guard for committed contract artifacts (#32).

CI fails if an example contract stops validating or if the published JSON
Schema drifts from the Pydantic models.
"""

import json
import unittest
from pathlib import Path

from src.contracts import DataForgeContract, load_contract


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((PROJECT_ROOT / "config" / "examples").glob("*.yaml"))
SCHEMA_PATH = PROJECT_ROOT / "config" / "schemas" / "dataforge-contract-v1.json"


class ContractArtifactTests(unittest.TestCase):
    def test_every_example_contract_validates(self):
        self.assertGreaterEqual(len(EXAMPLES), 2)
        for path in EXAMPLES:
            with self.subTest(contract=path.name):
                contract = load_contract(path)
                self.assertGreater(len(contract.datasets), 0)

    def test_examples_cover_more_than_one_source_type(self):
        source_types = {load_contract(path).source.type for path in EXAMPLES}
        self.assertGreaterEqual(len(source_types), 2)

    def test_published_json_schema_matches_models(self):
        committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        generated = DataForgeContract.model_json_schema(by_alias=True)
        self.assertEqual(
            committed,
            generated,
            "config/schemas/dataforge-contract-v1.json is stale; regenerate it with "
            "python -c \"from src.contracts import export_json_schema; "
            "export_json_schema('config/schemas/dataforge-contract-v1.json')\"",
        )


if __name__ == "__main__":
    unittest.main()
