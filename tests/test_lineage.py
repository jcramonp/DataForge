import unittest
from unittest.mock import MagicMock

from src.governance.lineage import (
    LineageConfigurationError,
    get_direct_children,
    get_direct_parents,
    get_downstream_lineage,
    get_upstream_lineage,
    register_lineage,
    register_lineage_edges,
)


class LineageRegistrationTests(
    unittest.TestCase
):
    def connection_with_cursor(self):
        connection = MagicMock()
        cursor = MagicMock()

        connection.cursor.return_value.__enter__.return_value = (
            cursor
        )

        return connection, cursor

    def test_self_lineage_is_rejected(self):
        connection, _ = (
            self.connection_with_cursor()
        )

        with self.assertRaises(
            LineageConfigurationError
        ):
            register_lineage(
                connection,
                parent_asset_id=7,
                child_asset_id=7,
            )

    def test_unknown_relation_type_is_rejected(
        self,
    ):
        connection, _ = (
            self.connection_with_cursor()
        )

        with self.assertRaises(
            LineageConfigurationError
        ):
            register_lineage(
                connection,
                parent_asset_id=1,
                child_asset_id=2,
                relation_type="magic_relation",
            )

    def test_register_lineage_returns_id(self):
        connection, cursor = (
            self.connection_with_cursor()
        )

        cursor.fetchone.return_value = (41,)

        lineage_id = register_lineage(
            connection,
            parent_asset_id=10,
            child_asset_id=20,
            relation_type="transformed_from",
            created_by_run_id=99,
            metadata={
                "operation": "silver",
            },
        )

        self.assertEqual(
            lineage_id,
            41,
        )

        cursor.execute.assert_called_once()

        parameters = (
            cursor.execute.call_args.args[1]
        )

        self.assertEqual(
            parameters[0],
            10,
        )

        self.assertEqual(
            parameters[1],
            20,
        )

        self.assertEqual(
            parameters[2],
            "transformed_from",
        )

        self.assertEqual(
            parameters[3],
            99,
        )

    def test_register_multiple_edges(self):
        connection, cursor = (
            self.connection_with_cursor()
        )

        cursor.fetchone.side_effect = [
            (1,),
            (2,),
        ]

        lineage_ids = register_lineage_edges(
            connection,
            [
                {
                    "parent_asset_id": 10,
                    "child_asset_id": 30,
                    "relation_type": "joined_from",
                },
                {
                    "parent_asset_id": 20,
                    "child_asset_id": 30,
                    "relation_type": "joined_from",
                },
            ],
        )

        self.assertEqual(
            lineage_ids,
            [1, 2],
        )

        self.assertEqual(
            cursor.execute.call_count,
            2,
        )


class LineageQueryTests(
    unittest.TestCase
):
    def connection_with_cursor(self):
        connection = MagicMock()
        cursor = MagicMock()

        connection.cursor.return_value.__enter__.return_value = (
            cursor
        )

        return connection, cursor

    @staticmethod
    def sample_lineage_row(
        asset_id: int,
        depth: int,
    ):
        return (
            asset_id,
            "silver",
            f"asset_{asset_id}",
            (
                "s3://bucket/"
                f"asset_{asset_id}.parquet"
            ),
            "parquet",
            100,
            "checksum",
            12,
            "silver_quality_gate",
            "success",
            5,
            "version-1",
            "orders",
            "source",
            "project",
            "client",
            "validated_from",
            depth,
        )

    def test_upstream_lineage_returns_api_ready_dicts(
        self,
    ):
        connection, cursor = (
            self.connection_with_cursor()
        )

        cursor.fetchall.return_value = [
            self.sample_lineage_row(
                8,
                1,
            ),
            self.sample_lineage_row(
                3,
                2,
            ),
        ]

        result = get_upstream_lineage(
            connection,
            asset_id=10,
        )

        self.assertEqual(
            len(result),
            2,
        )

        self.assertEqual(
            result[0]["asset_id"],
            8,
        )

        self.assertEqual(
            result[0]["depth"],
            1,
        )

        self.assertEqual(
            result[1]["asset_id"],
            3,
        )

        self.assertEqual(
            result[1]["depth"],
            2,
        )

        sql = cursor.execute.call_args.args[0]

        self.assertIn(
            "WITH RECURSIVE",
            sql,
        )

    def test_downstream_lineage_returns_api_ready_dicts(
        self,
    ):
        connection, cursor = (
            self.connection_with_cursor()
        )

        cursor.fetchall.return_value = [
            self.sample_lineage_row(
                20,
                1,
            )
        ]

        result = get_downstream_lineage(
            connection,
            asset_id=10,
        )

        self.assertEqual(
            result[0]["asset_id"],
            20,
        )

        self.assertEqual(
            result[0]["depth"],
            1,
        )

        sql = cursor.execute.call_args.args[0]

        self.assertIn(
            "WITH RECURSIVE",
            sql,
        )

    def test_direct_parents(self):
        connection, cursor = (
            self.connection_with_cursor()
        )

        cursor.fetchall.return_value = [
            (1,),
            (2,),
            (3,),
        ]

        result = get_direct_parents(
            connection,
            10,
        )

        self.assertEqual(
            result,
            [1, 2, 3],
        )

    def test_direct_children(self):
        connection, cursor = (
            self.connection_with_cursor()
        )

        cursor.fetchall.return_value = [
            (11,),
            (12,),
        ]

        result = get_direct_children(
            connection,
            10,
        )

        self.assertEqual(
            result,
            [11, 12],
        )


if __name__ == "__main__":
    unittest.main()