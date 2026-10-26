"""Unit tests for the versioned migration workflow (#32)."""

import tempfile
import unittest
from pathlib import Path

from src.ops.migrate import (
    MIGRATIONS_DIR,
    MigrationError,
    discover_migrations,
    file_checksum,
    plan_migrations,
)


class DiscoverMigrationsTests(unittest.TestCase):
    def _write(self, directory: Path, name: str, sql: str = "SELECT 1;") -> None:
        (directory / name).write_text(sql, encoding="utf-8")

    def test_migrations_are_sorted_by_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self._write(directory, "0002_second.sql")
            self._write(directory, "0001_first.sql")
            versions = [m.version for m in discover_migrations(directory)]
            self.assertEqual(versions, ["0001", "0002"])

    def test_invalid_filename_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(Path(tmp), "1_Bad-Name.sql")
            with self.assertRaises(MigrationError):
                discover_migrations(Path(tmp))

    def test_duplicate_versions_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(Path(tmp), "0001_first.sql")
            self._write(Path(tmp), "0001_other.sql")
            with self.assertRaises(MigrationError):
                discover_migrations(Path(tmp))

    def test_checksum_ignores_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp:
            unix = Path(tmp) / "a.sql"
            windows = Path(tmp) / "b.sql"
            unix.write_bytes(b"SELECT 1;\nSELECT 2;\n")
            windows.write_bytes(b"SELECT 1;\r\nSELECT 2;\r\n")
            self.assertEqual(file_checksum(unix), file_checksum(windows))

    def test_repository_migrations_are_valid_and_contiguous(self):
        migrations = discover_migrations(MIGRATIONS_DIR)
        versions = [int(m.version) for m in migrations]
        self.assertGreaterEqual(len(versions), 3)
        self.assertEqual(versions, list(range(1, len(versions) + 1)))
        for migration in migrations:
            sql = migration.sql.upper()
            # Idempotency rule: Docker init and the runner may both apply them.
            self.assertNotRegex(sql, r"CREATE TABLE (?!IF NOT EXISTS)")
            self.assertNotRegex(sql, r"CREATE INDEX (?!IF NOT EXISTS)")
            self.assertNotRegex(sql, r"CREATE VIEW")
            # The runner owns the transaction; explicit control would break it.
            self.assertNotRegex(sql, r"(?m)^\s*(BEGIN|COMMIT)\s*;")


class PlanMigrationsTests(unittest.TestCase):
    def setUp(self):
        self.available = discover_migrations(MIGRATIONS_DIR)

    def test_fresh_database_has_everything_pending(self):
        plan = plan_migrations(self.available, {})
        self.assertEqual(len(plan.pending), len(self.available))
        self.assertEqual(plan.applied, [])

    def test_applied_migrations_are_skipped(self):
        first = self.available[0]
        plan = plan_migrations(self.available, {first.version: first.checksum})
        self.assertEqual(plan.applied, [first])
        self.assertNotIn(first, plan.pending)

    def test_modified_applied_migration_is_rejected(self):
        first = self.available[0]
        with self.assertRaises(MigrationError):
            plan_migrations(self.available, {first.version: "0" * 64})

    def test_database_ahead_of_code_is_reported(self):
        applied = {m.version: m.checksum for m in self.available}
        applied["9999"] = "f" * 64
        plan = plan_migrations(self.available, applied)
        self.assertEqual(plan.pending, [])
        self.assertEqual(plan.unknown_versions, ["9999"])


if __name__ == "__main__":
    unittest.main()
