# Tests

Tests use the standard library `unittest` and run from the repository root.

```bash
python -m unittest discover -s tests -t .          # unit + regression suite (no services needed)
python -m unittest tests.test_ops_migrate          # one module
```

- `tests/test_*.py`: unit and regression tests for Sprint 1 Olist modules, the Sprint 2 generic engine, the API and operations tooling. MinIO/PostgreSQL are mocked.
- `tests/contracts/`: contract model and loader tests.
- `tests/integration/`: tests against real PostgreSQL and MinIO, covering the migration workflow and an end-to-end generic pipeline. They are skipped unless `DATAFORGE_INTEGRATION=1` and refuse to run unless `DATAFORGE_ENV=test`, because they reset the database schema. See `docs/operations/runbook.md`.
- `tests/fixtures/e2e/`: a small non-Olist CSV source and contract with known Quality Gate outcomes (7 rows → 4 validated, 3 quarantined).

All of the above run in GitHub Actions on every pull request (`.github/workflows/ci.yml`).
