import unittest

import pandas as pd

from src.governance.metadata import (
    dataframe_schema_hash,
)


class GovernanceMetadataTests(
    unittest.TestCase
):
    def test_schema_hash_is_deterministic(
        self,
    ):
        frame = pd.DataFrame(
            {
                "id": pd.Series(
                    [1, 2],
                    dtype="Int64",
                ),
                "name": pd.Series(
                    ["a", "b"],
                    dtype="string",
                ),
            }
        )

        first = dataframe_schema_hash(
            frame
        )

        second = dataframe_schema_hash(
            frame.copy()
        )

        self.assertEqual(
            first,
            second,
        )

    def test_schema_hash_changes_when_schema_changes(
        self,
    ):
        first = pd.DataFrame(
            {
                "id": pd.Series(
                    [1],
                    dtype="Int64",
                ),
            }
        )

        second = pd.DataFrame(
            {
                "id": pd.Series(
                    [1],
                    dtype="Int64",
                ),
                "name": pd.Series(
                    ["x"],
                    dtype="string",
                ),
            }
        )

        self.assertNotEqual(
            dataframe_schema_hash(
                first
            ),
            dataframe_schema_hash(
                second
            ),
        )


if __name__ == "__main__":
    unittest.main()