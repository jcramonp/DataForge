import unittest
from unittest.mock import MagicMock, patch

from src.governance.certification import (
    CertificationCriteriaError,
    CertificationNotFoundError,
    CertificationTransitionError,
    evaluate_certification,
    get_certification,
    get_certification_history,
    transition_certification,
)


class CertificationEvaluationTests(
    unittest.TestCase
):
    def connection_with_cursor(
        self,
        fetchone_results,
    ):
        connection = MagicMock()
        cursors = []

        for result in fetchone_results:
            cursor = MagicMock()
            cursor.fetchone.return_value = result
            cursors.append(cursor)

        connection.cursor.return_value.__enter__.side_effect = (
            cursors
        )

        connection.test_cursors = cursors

        return connection

    def test_all_criteria_can_pass(self):
        connection = (
            self.connection_with_cursor(
                [
                    (
                        "version-1",
                        "schema-hash",
                        "source-checksum",
                        "Data Team",
                    ),
                    (
                        6,
                        0,
                        1,
                    ),
                    (
                        1,
                        1,
                    ),
                ]
            )
        )

        result = evaluate_certification(
            connection,
            7,
        )

        self.assertTrue(
            result["validation_ready"]
        )

        self.assertTrue(
            result["certification_ready"]
        )

        self.assertEqual(
            result["criteria"],
            {
                "schema": True,
                "ownership": True,
                "version": True,
                "quality": True,
                "lineage": True,
            },
        )

    def test_missing_schema_blocks_readiness(
        self,
    ):
        connection = (
            self.connection_with_cursor(
                [
                    (
                        "version-1",
                        None,
                        "checksum",
                        "Owner",
                    ),
                    (
                        2,
                        0,
                        1,
                    ),
                    (
                        1,
                        1,
                    ),
                ]
            )
        )

        result = evaluate_certification(
            connection,
            7,
        )

        self.assertFalse(
            result["criteria"]["schema"]
        )

        self.assertFalse(
            result["validation_ready"]
        )

        self.assertFalse(
            result["certification_ready"]
        )

    def test_missing_successful_quality_gate_blocks_certification(
        self,
    ):
        connection = (
            self.connection_with_cursor(
                [
                    (
                        "version-1",
                        "schema",
                        "checksum",
                        "Owner",
                    ),
                    (
                        5,
                        1,
                        0,
                    ),
                    (
                        1,
                        1,
                    ),
                ]
            )
        )

        result = evaluate_certification(
            connection,
            7,
        )

        self.assertTrue(
            result["validation_ready"]
        )

        self.assertFalse(
            result["criteria"]["quality"]
        )

        self.assertFalse(
            result["certification_ready"]
        )

    def test_missing_lineage_blocks_certification(
        self,
    ):
        connection = (
            self.connection_with_cursor(
                [
                    (
                        "version-1",
                        "schema",
                        "checksum",
                        "Owner",
                    ),
                    (
                        5,
                        0,
                        1,
                    ),
                    (
                        1,
                        0,
                    ),
                ]
            )
        )

        result = evaluate_certification(
            connection,
            7,
        )

        self.assertTrue(
            result["validation_ready"]
        )

        self.assertTrue(
            result["criteria"]["quality"]
        )

        self.assertFalse(
            result["criteria"]["lineage"]
        )

        self.assertFalse(
            result["certification_ready"]
        )

    def test_unknown_dataset_version_is_rejected(
        self,
    ):
        connection = (
            self.connection_with_cursor(
                [None]
            )
        )

        with self.assertRaises(
            CertificationNotFoundError
        ):
            evaluate_certification(
                connection,
                999,
            )

    def test_quality_query_uses_upstream_lineage(
        self,
    ):
        connection = (
            self.connection_with_cursor(
                [
                    (
                        "gold-version",
                        "gold-schema",
                        "gold-checksum",
                        "DataForge",
                    ),
                    (
                        20,
                        1,
                        4,
                    ),
                    (
                        1,
                        1,
                    ),
                ]
            )
        )

        result = evaluate_certification(
            connection,
            50,
        )

        self.assertTrue(
            result["criteria"]["quality"]
        )

        self.assertTrue(
            result["certification_ready"]
        )

        second_cursor = (
            connection.test_cursors[1]
        )

        sql = second_cursor.execute.call_args.args[0]

        self.assertIn(
            "upstream_assets",
            sql,
        )

        self.assertIn(
            "quality_runs",
            sql,
        )

        self.assertIn(
            "WITH RECURSIVE",
            sql,
        )


class CertificationQueryTests(
    unittest.TestCase
):
    def test_get_certification_returns_api_ready_dict(
        self,
    ):
        connection = MagicMock()
        cursor = MagicMock()

        connection.cursor.return_value.__enter__.return_value = (
            cursor
        )

        cursor.fetchone.return_value = (
            10,
            5,
            "validated",
            {
                "criteria": {
                    "schema": True,
                }
            },
            None,
            "validated-at",
            None,
            "created-at",
            "updated-at",
        )

        result = get_certification(
            connection,
            5,
        )

        self.assertEqual(
            result["certification_id"],
            10,
        )

        self.assertEqual(
            result["state"],
            "validated",
        )

    def test_certification_history_is_ordered_and_serializable(
        self,
    ):
        connection = MagicMock()
        cursor = MagicMock()

        connection.cursor.return_value.__enter__.return_value = (
            cursor
        )

        cursor.fetchall.return_value = [
            (
                1,
                None,
                "draft",
                "Initial",
                {},
                "system",
                "time-1",
            ),
            (
                2,
                "draft",
                "validated",
                "Ready",
                {},
                "system",
                "time-2",
            ),
        ]

        history = (
            get_certification_history(
                connection,
                5,
            )
        )

        self.assertEqual(
            len(history),
            2,
        )

        self.assertEqual(
            history[1]["to_state"],
            "validated",
        )


class CertificationTransitionTests(
    unittest.TestCase
):
    @patch(
        "src.governance.certification."
        "evaluate_certification"
    )
    @patch(
        "src.governance.certification."
        "get_certification"
    )
    def test_draft_can_become_validated(
        self,
        mocked_get,
        mocked_evaluate,
    ):
        mocked_get.side_effect = [
            {
                "certification_id": 1,
                "dataset_version_id": 5,
                "state": "draft",
            },
            {
                "certification_id": 1,
                "dataset_version_id": 5,
                "state": "validated",
            },
        ]

        mocked_evaluate.return_value = {
            "criteria": {
                "schema": True,
                "ownership": True,
                "version": True,
                "quality": False,
                "lineage": False,
            },
            "details": {
                "asset_available": True,
            },
            "validation_ready": True,
            "certification_ready": False,
        }

        connection = MagicMock()
        cursor = MagicMock()

        connection.cursor.return_value.__enter__.return_value = (
            cursor
        )

        cursor.fetchone.return_value = (
            1,
        )

        result = transition_certification(
            connection,
            5,
            "validated",
            reason="Metadata ready",
            changed_by="test",
        )

        self.assertEqual(
            result["state"],
            "validated",
        )

        self.assertEqual(
            cursor.execute.call_count,
            2,
        )

    @patch(
        "src.governance.certification."
        "evaluate_certification"
    )
    @patch(
        "src.governance.certification."
        "get_certification"
    )
    def test_validated_can_become_certified(
        self,
        mocked_get,
        mocked_evaluate,
    ):
        mocked_get.side_effect = [
            {
                "certification_id": 1,
                "dataset_version_id": 5,
                "state": "validated",
            },
            {
                "certification_id": 1,
                "dataset_version_id": 5,
                "state": "certified",
            },
        ]

        mocked_evaluate.return_value = {
            "criteria": {
                "schema": True,
                "ownership": True,
                "version": True,
                "quality": True,
                "lineage": True,
            },
            "details": {
                "asset_available": True,
            },
            "validation_ready": True,
            "certification_ready": True,
        }

        connection = MagicMock()
        cursor = MagicMock()

        connection.cursor.return_value.__enter__.return_value = (
            cursor
        )

        cursor.fetchone.return_value = (
            1,
        )

        result = transition_certification(
            connection,
            5,
            "certified",
        )

        self.assertEqual(
            result["state"],
            "certified",
        )

    @patch(
        "src.governance.certification."
        "evaluate_certification"
    )
    @patch(
        "src.governance.certification."
        "get_certification"
    )
    def test_certification_is_blocked_when_quality_fails(
        self,
        mocked_get,
        mocked_evaluate,
    ):
        mocked_get.return_value = {
            "certification_id": 1,
            "dataset_version_id": 5,
            "state": "validated",
        }

        mocked_evaluate.return_value = {
            "criteria": {
                "schema": True,
                "ownership": True,
                "version": True,
                "quality": False,
                "lineage": True,
            },
            "details": {
                "asset_available": True,
            },
            "validation_ready": True,
            "certification_ready": False,
        }

        connection = MagicMock()

        with self.assertRaises(
            CertificationCriteriaError
        ):
            transition_certification(
                connection,
                5,
                "certified",
            )

    @patch(
        "src.governance.certification."
        "get_certification"
    )
    def test_draft_cannot_skip_directly_to_certified(
        self,
        mocked_get,
    ):
        mocked_get.return_value = {
            "certification_id": 1,
            "dataset_version_id": 5,
            "state": "draft",
        }

        connection = MagicMock()

        with self.assertRaises(
            CertificationTransitionError
        ):
            transition_certification(
                connection,
                5,
                "certified",
            )

    @patch(
        "src.governance.certification."
        "get_certification"
    )
    def test_certified_state_cannot_move_backwards(
        self,
        mocked_get,
    ):
        mocked_get.return_value = {
            "certification_id": 1,
            "dataset_version_id": 5,
            "state": "certified",
        }

        connection = MagicMock()

        with self.assertRaises(
            CertificationTransitionError
        ):
            transition_certification(
                connection,
                5,
                "validated",
            )


if __name__ == "__main__":
    unittest.main()