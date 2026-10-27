"""Unit tests for persisted control-plane configuration services (#25)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.api.control_plane import (
    InlineSecretError,
    canonical_contract_json,
    canonical_contract_payload,
    contract_hash,
    ensure_no_inline_secrets,
)
from src.contracts.loader import load_contract
from src.contracts.models import DataForgeContract


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OLIST_CONTRACT = PROJECT_ROOT / "config" / "examples" / "olist.yaml"


def contract_from_payload(payload: dict) -> DataForgeContract:
    return DataForgeContract.model_validate(payload)


class ControlPlaneConfigurationUnitTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_contract(OLIST_CONTRACT)

    def test_canonical_payload_uses_contract_aliases(self):
        payload = canonical_contract_payload(self.contract)

        self.assertEqual(payload["contract_version"], "1.0")
        self.assertIn("schema", payload["datasets"][0])
        self.assertNotIn("schema_", payload["datasets"][0])

    def test_canonical_json_is_valid_and_deterministic(self):
        first = canonical_contract_json(self.contract)
        second = canonical_contract_json(load_contract(OLIST_CONTRACT))

        self.assertEqual(first, second)
        self.assertEqual(
            json.loads(first),
            canonical_contract_payload(self.contract),
        )

    def test_contract_hash_is_stable_sha256(self):
        first = contract_hash(self.contract)
        second = contract_hash(load_contract(OLIST_CONTRACT))

        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertTrue(
            all(character in "0123456789abcdef" for character in first)
        )

    def test_contract_change_changes_hash(self):
        payload = canonical_contract_payload(self.contract)
        payload["datasets"][0]["description"] = (
            "Configuration revision used by API test"
        )

        changed = contract_from_payload(payload)

        self.assertNotEqual(
            contract_hash(self.contract),
            contract_hash(changed),
        )

    def test_normal_contract_contains_no_inline_secrets(self):
        ensure_no_inline_secrets(self.contract)

    def test_authorization_header_is_rejected(self):
        payload = canonical_contract_payload(self.contract)

        secret_value = "Bearer do-not-persist-this-value"

        payload["datasets"][0]["source_object"]["headers"][
            "Authorization"
        ] = secret_value

        contract = contract_from_payload(payload)

        with self.assertRaises(InlineSecretError) as context:
            ensure_no_inline_secrets(contract)

        message = str(context.exception)

        self.assertIn(
            "source.connection_reference",
            message,
        )
        self.assertIn(
            "Authorization",
            message,
        )

        # Secret values must never be copied to logs/error messages.
        self.assertNotIn(
            secret_value,
            message,
        )

    def test_api_key_parameter_is_rejected(self):
        payload = canonical_contract_payload(self.contract)

        secret_value = "top-secret-api-key"

        payload["datasets"][0]["source_object"]["params"][
            "api-key"
        ] = secret_value

        contract = contract_from_payload(payload)

        with self.assertRaises(InlineSecretError) as context:
            ensure_no_inline_secrets(contract)

        message = str(context.exception)

        self.assertIn(
            "api-key",
            message,
        )
        self.assertNotIn(
            secret_value,
            message,
        )

    def test_non_secret_headers_and_parameters_are_allowed(self):
        payload = canonical_contract_payload(self.contract)

        payload["datasets"][0]["source_object"]["headers"][
            "Accept"
        ] = "application/json"

        payload["datasets"][0]["source_object"]["params"][
            "page_size"
        ] = 100

        contract = contract_from_payload(payload)

        ensure_no_inline_secrets(contract)


if __name__ == "__main__":
    unittest.main()
