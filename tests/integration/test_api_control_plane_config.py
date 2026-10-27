"""Integration tests for persisted API configuration contracts (#25).

These tests use the disposable PostgreSQL integration database. They prove
that API onboarding metadata and executable DataForge contracts are persisted
atomically, versioned, idempotent and ownership-safe.
"""

from __future__ import annotations

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from src.api.control_plane import (
    ControlPlaneConflictError,
    canonical_contract_payload,
    get_active_contract,
    get_contract_by_id,
    list_clients,
    list_datasets,
    list_projects,
    list_sources,
    register_contract,
)
from src.common.clients import connect_postgres
from src.contracts.loader import load_contract
from src.contracts.models import DataForgeContract
from src.ops.migrate import run_migrations
from tests.integration import (
    fetch_all,
    integration_settings,
    requires_integration,
    reset_database,
)


CONTRACT_PATH = "tests/fixtures/e2e/retail_contract.yaml"


def modified_contract(
    contract: DataForgeContract,
    *,
    description: str,
) -> DataForgeContract:
    payload = canonical_contract_payload(contract)
    payload["datasets"][0]["description"] = description
    return DataForgeContract.model_validate(payload)


def conflicting_client_contract(
    contract: DataForgeContract,
) -> DataForgeContract:
    payload = canonical_contract_payload(contract)

    payload["client"] = {
        "code": "other-client",
        "name": "Other Client",
        "description": None,
    }

    # Keep the same globally unique project_code intentionally.
    return DataForgeContract.model_validate(payload)


@requires_integration
class ControlPlaneConfigurationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.settings = integration_settings()

        reset_database(self.settings)

        with connect_postgres(
            self.settings,
            autocommit=True,
        ) as conn:
            run_migrations(conn)

        self.contract = load_contract(CONTRACT_PATH)

    def test_initial_registration_persists_metadata_and_contract(self):
        with connect_postgres(self.settings) as conn:
            result = register_contract(
                conn,
                self.contract,
                created_by="integration-test",
            )

        self.assertTrue(result["created"])
        self.assertFalse(result["reactivated"])
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["status"], "active")
        self.assertEqual(
            [item["dataset_code"] for item in result["datasets"]],
            ["orders"],
        )

        clients = fetch_all(
            self.settings,
            """
            SELECT client_code, client_name
            FROM client
            """,
        )
        self.assertEqual(
            clients,
            [("ci-retail", "CI Retail")],
        )

        projects = fetch_all(
            self.settings,
            """
            SELECT project_code, project_name
            FROM project
            """,
        )
        self.assertEqual(
            projects,
            [
                (
                    "ci-retail-e2e",
                    "CI Retail End-to-End",
                )
            ],
        )

        sources = fetch_all(
            self.settings,
            """
            SELECT
                source_code,
                source_type,
                source_name
            FROM data_source
            """,
        )
        self.assertEqual(
            sources,
            [
                (
                    "ci-retail-csv",
                    "file",
                    "CI Retail CSV",
                )
            ],
        )

        contracts = fetch_all(
            self.settings,
            """
            SELECT
                revision,
                contract_version,
                status,
                created_by
            FROM configuration_contract
            """,
        )
        self.assertEqual(
            contracts,
            [
                (
                    1,
                    "1.0",
                    "active",
                    "integration-test",
                )
            ],
        )

    def test_registered_metadata_is_queryable_from_control_plane(self):
        with connect_postgres(self.settings) as conn:
            register_contract(
                conn,
                self.contract,
            )

            clients = list_clients(conn)

            projects = list_projects(
                conn,
                client_code="ci-retail",
            )

            sources = list_sources(
                conn,
                client_code="ci-retail",
                project_code="ci-retail-e2e",
            )

            datasets = list_datasets(
                conn,
                client_code="ci-retail",
                project_code="ci-retail-e2e",
                source_code="ci-retail-csv",
            )

        self.assertEqual(
            len(clients),
            1,
        )

        self.assertEqual(
            clients[0]["code"],
            "ci-retail",
        )
        self.assertEqual(
            clients[0]["projects_count"],
            1,
        )
        self.assertEqual(
            clients[0]["sources_count"],
            1,
        )
        self.assertEqual(
            clients[0]["datasets_count"],
            1,
        )

        self.assertEqual(
            len(projects),
            1,
        )
        self.assertEqual(
            projects[0]["code"],
            "ci-retail-e2e",
        )

        self.assertEqual(
            len(sources),
            1,
        )

        source = sources[0]

        self.assertEqual(
            source["code"],
            "ci-retail-csv",
        )
        self.assertEqual(
            source["type"],
            "file",
        )
        self.assertEqual(
            source["contract_revision"],
            1,
        )
        self.assertEqual(
            source["datasets"][0]["code"],
            "orders",
        )
        self.assertEqual(
            source["datasets"][0]["columns_count"],
            5,
        )

        self.assertEqual(
            len(datasets),
            1,
        )

        dataset = datasets[0]

        self.assertEqual(
            dataset["code"],
            "orders",
        )
        self.assertEqual(
            dataset["source_code"],
            "ci-retail-csv",
        )
        self.assertEqual(
            dataset["columns_count"],
            5,
        )
        self.assertEqual(
            dataset["primary_keys"],
            ["order_id"],
        )
        self.assertEqual(
            dataset["rules_count"],
            5,
        )
        self.assertEqual(
            dataset["transformations_count"],
            4,
        )
        self.assertTrue(
            dataset["gold_configured"],
        )

        # Onboarding creates configuration metadata, not physical data.
        self.assertEqual(
            dataset["layers"],
            {
                "bronze": False,
                "silver": False,
                "quarantine": False,
                "gold": False,
            },
        )

        self.assertEqual(
            dataset["certification_status"],
            "draft",
        )

        # Negative filtering is verified with a fresh valid connection.
        # The previous context manager has intentionally closed its connection.
        with connect_postgres(self.settings) as conn:
            self.assertEqual(
                list_projects(
                    conn,
                    client_code="missing-client",
                ),
                [],
            )

            self.assertEqual(
                list_sources(
                    conn,
                    project_code="missing-project",
                ),
                [],
            )

            self.assertEqual(
                list_datasets(
                    conn,
                    source_code="missing-source",
                ),
                [],
            )


    def test_same_contract_is_idempotent(self):
        with connect_postgres(self.settings) as conn:
            first = register_contract(
                conn,
                self.contract,
            )

            second = register_contract(
                conn,
                self.contract,
            )

        self.assertEqual(
            second["contract_id"],
            first["contract_id"],
        )
        self.assertEqual(second["revision"], 1)
        self.assertFalse(second["created"])
        self.assertFalse(second["reactivated"])

        rows = fetch_all(
            self.settings,
            """
            SELECT COUNT(*)
            FROM configuration_contract
            """,
        )

        self.assertEqual(rows[0][0], 1)

    def test_changed_contract_creates_new_revision_and_archives_previous(self):
        revision_two = modified_contract(
            self.contract,
            description="Revision two",
        )

        with connect_postgres(self.settings) as conn:
            first = register_contract(
                conn,
                self.contract,
            )

            second = register_contract(
                conn,
                revision_two,
            )

        self.assertEqual(first["revision"], 1)
        self.assertEqual(second["revision"], 2)
        self.assertTrue(second["created"])

        rows = fetch_all(
            self.settings,
            """
            SELECT revision, status
            FROM configuration_contract
            ORDER BY revision
            """,
        )

        self.assertEqual(
            rows,
            [
                (1, "archived"),
                (2, "active"),
            ],
        )

    def test_old_revision_can_be_reactivated_without_duplication(self):
        revision_two = modified_contract(
            self.contract,
            description="Revision two",
        )

        with connect_postgres(self.settings) as conn:
            first = register_contract(
                conn,
                self.contract,
            )

            second = register_contract(
                conn,
                revision_two,
            )

            reactivated = register_contract(
                conn,
                self.contract,
            )

        self.assertEqual(
            reactivated["contract_id"],
            first["contract_id"],
        )
        self.assertEqual(
            reactivated["revision"],
            1,
        )
        self.assertFalse(
            reactivated["created"],
        )
        self.assertTrue(
            reactivated["reactivated"],
        )
        self.assertNotEqual(
            second["contract_id"],
            reactivated["contract_id"],
        )

        rows = fetch_all(
            self.settings,
            """
            SELECT revision, status
            FROM configuration_contract
            ORDER BY revision
            """,
        )

        self.assertEqual(
            rows,
            [
                (1, "active"),
                (2, "archived"),
            ],
        )

        active_count = fetch_all(
            self.settings,
            """
            SELECT COUNT(*)
            FROM configuration_contract
            WHERE status = 'active'
            """,
        )[0][0]

        self.assertEqual(active_count, 1)

    def test_active_contract_can_be_reconstructed_as_valid_model(self):
        with connect_postgres(self.settings) as conn:
            created = register_contract(
                conn,
                self.contract,
            )

            active = get_active_contract(
                conn,
                client_code="ci-retail",
                project_code="ci-retail-e2e",
                source_code="ci-retail-csv",
            )

            by_id = get_contract_by_id(
                conn,
                created["contract_id"],
            )

        self.assertIsNotNone(active)
        self.assertIsNotNone(by_id)

        self.assertIsInstance(
            active["contract"],
            DataForgeContract,
        )

        self.assertIsInstance(
            by_id["contract"],
            DataForgeContract,
        )

        self.assertEqual(
            active["contract"].source.code,
            "ci-retail-csv",
        )
        self.assertEqual(
            active["contract"].datasets[0].code,
            "orders",
        )
        self.assertEqual(
            active["contract_hash"],
            created["contract_hash"],
        )
        self.assertEqual(
            by_id["contract_hash"],
            created["contract_hash"],
        )

    def test_project_cannot_be_reassigned_to_another_client_and_rolls_back(self):
        conflict = conflicting_client_contract(
            self.contract
        )

        with connect_postgres(self.settings) as conn:
            register_contract(
                conn,
                self.contract,
            )

        with self.assertRaises(
            ControlPlaneConflictError
        ):
            with connect_postgres(
                self.settings
            ) as conn:
                register_contract(
                    conn,
                    conflict,
                )

        # The second client was inserted before the project conflict inside
        # register_contract(), so its absence proves transactional rollback.
        other_client_count = fetch_all(
            self.settings,
            """
            SELECT COUNT(*)
            FROM client
            WHERE client_code = 'other-client'
            """,
        )[0][0]

        self.assertEqual(
            other_client_count,
            0,
        )

        original_project = fetch_all(
            self.settings,
            """
            SELECT
                c.client_code,
                p.project_code
            FROM project p
            JOIN client c
              ON c.client_id = p.client_id
            WHERE p.project_code = 'ci-retail-e2e'
            """,
        )

        self.assertEqual(
            original_project,
            [
                (
                    "ci-retail",
                    "ci-retail-e2e",
                )
            ],
        )

        contract_count = fetch_all(
            self.settings,
            """
            SELECT COUNT(*)
            FROM configuration_contract
            """,
        )[0][0]

        self.assertEqual(
            contract_count,
            1,
        )


    def test_concurrent_contract_updates_are_serialized_per_source(self):
        """Concurrent API requests must receive distinct revisions."""

        revision_a = modified_contract(
            self.contract,
            description="Concurrent revision A",
        )

        revision_b = modified_contract(
            self.contract,
            description="Concurrent revision B",
        )

        # Establish revision 1 before the concurrent updates.
        with connect_postgres(self.settings) as conn:
            initial = register_contract(
                conn,
                self.contract,
            )

        self.assertEqual(
            initial["revision"],
            1,
        )

        barrier = threading.Barrier(2)

        def register_concurrently(
            contract: DataForgeContract,
        ):
            barrier.wait(timeout=5)

            with connect_postgres(
                self.settings
            ) as conn:
                return register_contract(
                    conn,
                    contract,
                    created_by="concurrency-test",
                )

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            futures = [
                executor.submit(
                    register_concurrently,
                    revision_a,
                ),
                executor.submit(
                    register_concurrently,
                    revision_b,
                ),
            ]

            results = [
                future.result(timeout=15)
                for future in futures
            ]

        self.assertEqual(
            sorted(
                result["revision"]
                for result in results
            ),
            [2, 3],
        )

        self.assertTrue(
            all(
                result["created"]
                for result in results
            )
        )

        self.assertEqual(
            len(
                {
                    result["contract_id"]
                    for result in results
                }
            ),
            2,
        )

        revisions = fetch_all(
            self.settings,
            """
            SELECT
                revision,
                status
            FROM configuration_contract
            ORDER BY revision
            """,
        )

        self.assertEqual(
            revisions,
            [
                (1, "archived"),
                (2, "archived"),
                (3, "active"),
            ],
        )

        active_count = fetch_all(
            self.settings,
            """
            SELECT COUNT(*)
            FROM configuration_contract
            WHERE status = 'active'
            """,
        )[0][0]

        self.assertEqual(
            active_count,
            1,
        )


if __name__ == "__main__":
    unittest.main()
