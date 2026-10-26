# Control-plane database migrations

The PostgreSQL control-plane schema is versioned in `database/migrations/` and applied by `python -m src.ops.migrate` (`src/ops/migrate.py`).

| Version | File | Content |
|---|---|---|
| 0001 | `0001_control_plane_schema.sql` | Sprint 1 tables and indexes (formerly `database/schema.sql`) |
| 0002 | `0002_lineage_certification.sql` | Asset lineage, dataset certification and transition history, plus the Draft-on-new-version trigger (#23; formerly `database/migrations/002_lineage_certification.sql`) |
| 0003 | `0003_governance_views.sql` | Lineage, quality, lineage-edge and certification summary views (formerly `database/governance_views.sql`) |
| 0004 | `0004_operational_views.sql` | Run status, failure and latest-run views for operations (#32) |

## Commands

```bash
python -m src.ops.migrate            # apply pending migrations
python -m src.ops.migrate --status   # list applied/pending (exit 1 if anything is pending)
python -m src.ops.migrate --dry-run  # show what would be applied
docker compose run --rm migrate      # same, inside the Compose network
```

## How it works

- Files named `NNNN_lowercase_description.sql` are applied in version order.
- Each migration runs in its own transaction and is recorded in `schema_migrations` (`version`, `name`, `checksum`, `applied_at`, `execution_ms`).
- A PostgreSQL advisory lock serializes concurrent runs (e.g. two deploy tasks starting at once).
- The SHA-256 checksum, computed with normalized line endings, is compared on every run. If an **already-applied file was edited**, the run stops. History is never rewritten.
- A version recorded in the database but missing from the checkout (code older than the schema, e.g. after a rollback) is reported as a warning.
- Readiness (`/api/ready`, `python -m src.ops.health`) fails while migrations are pending.

## Bootstrap paths

1. **Fresh local volume:** the `postgres` container mounts `database/migrations/` as `docker-entrypoint-initdb.d`, so a new volume gets the full schema on first boot.
2. **Every deployment and existing databases:** the `migrate` service (or the CLI) applies anything pending and records it. On a database bootstrapped by path 1 it re-applies the idempotent files once and records them.

Because both paths may run the same file, **migrations must be idempotent**:

- `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `CREATE OR REPLACE VIEW`;
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`;
- `DROP TRIGGER IF EXISTS` before `CREATE TRIGGER`, `CREATE OR REPLACE FUNCTION`;
- guarded `DO $$ ... $$` blocks for constraints;
- `INSERT ... ON CONFLICT DO NOTHING` for backfills.

Do not put `BEGIN`/`COMMIT` in a migration: the runner wraps each file in its own transaction.

A unit test rejects non-idempotent `CREATE` statements. CI applies every migration twice on an empty database and adopts a database bootstrapped from raw SQL.

## Adding a migration

1. Create `database/migrations/0005_short_description.sql` (next number, lowercase, underscores).
2. Write idempotent SQL. Prefer additive changes (new nullable columns, new tables/views) so the previous application version keeps working. This is what makes rollback safe.
3. Run `python -m src.ops.migrate` locally and `python -m unittest tests.test_ops_migrate`.
4. Commit the migration together with the code that uses it.

Never edit or renumber a migration that has been merged to `develop`; fix forward with a new file.

## Rolling back schema changes

Migrations are **forward-only**. To undo a change, write a new migration that reverts it (e.g. `DROP VIEW IF EXISTS ...`). Because migrations are additive, rolling back the *application* (previous image) normally needs no schema change; see [`runbook.md`](runbook.md#rollback). For destructive changes, take a snapshot first (`pg_dump` locally, RDS snapshot on AWS).
