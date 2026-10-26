"""Versioned control-plane database migrations.

Migrations are plain SQL files in ``database/migrations`` named
``NNNN_description.sql``. They are applied in version order, each in its own
transaction, and recorded in ``schema_migrations`` with a SHA-256 checksum.

Rules (see docs/operations/migrations.md):

- Migrations are forward-only and must be idempotent (``IF NOT EXISTS``,
  ``CREATE OR REPLACE``), because PostgreSQL's first-boot init in Docker
  Compose also runs them. CI applies every migration twice to enforce this.
- An applied migration must never be edited; add a new file instead. A
  checksum mismatch stops the run.
- Files must not contain ``BEGIN``/``COMMIT``: the runner owns the transaction.

Usage::

    python -m src.ops.migrate            # apply pending migrations
    python -m src.ops.migrate --status   # show applied/pending migrations
    python -m src.ops.migrate --dry-run  # list what would be applied
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg

from src.common.clients import connect_postgres
from src.common.log import configure_logging
from src.common.settings import PROJECT_ROOT


logger = logging.getLogger("src.ops.migrate")

MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"

_FILENAME = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")

# Arbitrary constant key so concurrent deployers serialize on the same lock.
_ADVISORY_LOCK_KEY = 32_032_032

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(4) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    checksum CHAR(64) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    execution_ms INTEGER NOT NULL
)
"""


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path
    checksum: str

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class MigrationPlan:
    pending: list[Migration]
    applied: list[Migration]
    unknown_versions: list[str]


def file_checksum(path: Path) -> str:
    # Normalize line endings so Windows and Linux checkouts agree.
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = _FILENAME.match(path.name)
        if match is None:
            raise MigrationError(
                f"Invalid migration filename '{path.name}'; "
                "expected NNNN_lowercase_description.sql"
            )
        migrations.append(
            Migration(
                version=match["version"],
                name=match["name"],
                path=path,
                checksum=file_checksum(path),
            )
        )

    versions = [m.version for m in migrations]
    duplicates = sorted({v for v in versions if versions.count(v) > 1})
    if duplicates:
        raise MigrationError(f"Duplicate migration versions: {', '.join(duplicates)}")

    return migrations


def plan_migrations(
    available: list[Migration],
    applied_checksums: dict[str, str],
) -> MigrationPlan:
    """Compare files with recorded migrations; fail on edited history."""

    pending: list[Migration] = []
    applied: list[Migration] = []

    for migration in available:
        recorded = applied_checksums.get(migration.version)
        if recorded is None:
            pending.append(migration)
        elif recorded.strip() != migration.checksum:
            raise MigrationError(
                f"Migration {migration.version}_{migration.name} was modified "
                "after being applied (checksum mismatch). Create a new "
                "migration instead of editing an applied one."
            )
        else:
            applied.append(migration)

    known = {m.version for m in available}
    unknown = sorted(v for v in applied_checksums if v not in known)

    return MigrationPlan(pending=pending, applied=applied, unknown_versions=unknown)


def _applied_checksums(conn: psycopg.Connection) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version, checksum FROM schema_migrations")
        return {row[0]: row[1] for row in cur.fetchall()}


def _apply(conn: psycopg.Connection, migration: Migration) -> int:
    started = time.perf_counter()
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(migration.sql)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            cur.execute(
                """
                INSERT INTO schema_migrations (version, name, checksum, execution_ms)
                VALUES (%s, %s, %s, %s)
                """,
                (migration.version, migration.name, migration.checksum, elapsed_ms),
            )
    return elapsed_ms


def run_migrations(
    conn: psycopg.Connection,
    directory: Path = MIGRATIONS_DIR,
    *,
    dry_run: bool = False,
) -> MigrationPlan:
    """Apply pending migrations on an autocommit connection."""

    available = discover_migrations(directory)

    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(%s)", (_ADVISORY_LOCK_KEY,))
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(_CREATE_TABLE)

        plan = plan_migrations(available, _applied_checksums(conn))

        for version in plan.unknown_versions:
            logger.warning(
                "Database has migration %s that is not present in this checkout "
                "(code is older than the database schema)",
                version,
                extra={"migration_version": version},
            )

        for migration in plan.pending:
            if dry_run:
                logger.info("Would apply migration %s_%s", migration.version, migration.name)
                continue
            elapsed_ms = _apply(conn, migration)
            logger.info(
                "Applied migration %s_%s",
                migration.version,
                migration.name,
                extra={"migration_version": migration.version, "execution_ms": elapsed_ms},
            )

        return plan
    finally:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_KEY,))


def migration_status(conn: psycopg.Connection, directory: Path = MIGRATIONS_DIR) -> MigrationPlan:
    available = discover_migrations(directory)
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('schema_migrations') IS NOT NULL")
        has_table = cur.fetchone()[0]
    applied = _applied_checksums(conn) if has_table else {}
    return plan_migrations(available, applied)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply DataForge control-plane migrations")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show applied and pending migrations")
    mode.add_argument("--dry-run", action="store_true", help="List pending migrations without applying")
    parser.add_argument("--directory", type=Path, default=MIGRATIONS_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    configure_logging()

    try:
        with connect_postgres(autocommit=True) as conn:
            if args.status:
                plan = migration_status(conn, args.directory)
                for m in plan.applied:
                    print(f"applied  {m.version}_{m.name}")
                for m in plan.pending:
                    print(f"pending  {m.version}_{m.name}")
                for version in plan.unknown_versions:
                    print(f"unknown  {version} (present in database only)")
                return 1 if plan.pending else 0

            plan = run_migrations(conn, args.directory, dry_run=args.dry_run)
            verb = "Would apply" if args.dry_run else "Applied"
            print(f"{verb} {len(plan.pending)} migration(s); {len(plan.applied)} already applied.")
            return 0
    except (MigrationError, psycopg.Error) as exc:
        logger.error("Migration failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
