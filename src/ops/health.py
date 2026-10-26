"""Readiness checks for the DataForge API and core services.

Liveness (``GET /api/health``) only says the process is up. Readiness
(``GET /api/ready`` and ``python -m src.ops.health``) verifies that the
service can actually do work: configuration is valid, the control-plane
database is reachable with every migration applied, each storage bucket is
accessible, and the shipped example contracts still validate.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from src.common.clients import connect_postgres, create_s3_client
from src.common.settings import PROJECT_ROOT, Settings, get_settings
from src.contracts.loader import load_contract
from src.ops.migrate import migration_status


CONTRACTS_DIR = PROJECT_ROOT / "config" / "examples"


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    latency_ms: float


def _timed(name: str, check: Callable[[], str]) -> CheckResult:
    started = time.perf_counter()
    try:
        detail = check()
        ok = True
    except Exception as exc:  # readiness must report, never raise
        detail = f"{type(exc).__name__}: {exc}"
        ok = False
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    return CheckResult(name=name, ok=ok, detail=detail, latency_ms=latency_ms)


def check_configuration(settings: Settings) -> CheckResult:
    def check() -> str:
        problems = settings.problems()
        if problems:
            raise ValueError("; ".join(problems))
        return f"environment={settings.environment}"

    return _timed("configuration", check)


def check_postgres(settings: Settings) -> CheckResult:
    def check() -> str:
        with connect_postgres(settings, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            plan = migration_status(conn)
        if plan.pending:
            names = ", ".join(f"{m.version}_{m.name}" for m in plan.pending)
            raise RuntimeError(f"pending migrations: {names}")
        latest = plan.applied[-1].version if plan.applied else "none"
        return f"connected; schema version {latest}"

    return _timed("postgres", check)


def check_storage(settings: Settings, client_factory=create_s3_client) -> CheckResult:
    def check() -> str:
        s3 = client_factory(settings)
        for bucket in settings.storage.buckets.values():
            s3.head_bucket(Bucket=bucket)
        return f"{len(settings.storage.buckets)} buckets reachable"

    return _timed("object_storage", check)


def check_contracts(directory: Path = CONTRACTS_DIR) -> CheckResult:
    def check() -> str:
        paths = sorted(
            p for p in directory.glob("*") if p.suffix in {".yaml", ".yml", ".json"}
        )
        if not paths:
            raise FileNotFoundError(f"no contracts found in {directory}")
        for path in paths:
            load_contract(path)
        return f"{len(paths)} contracts valid"

    return _timed("contracts", check)


def run_readiness_checks(settings: Settings | None = None) -> list[CheckResult]:
    settings = settings or get_settings()
    return [
        check_configuration(settings),
        check_postgres(settings),
        check_storage(settings),
        check_contracts(),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check DataForge readiness")
    parser.add_argument("--json", action="store_true", help="Print results as JSON")
    args = parser.parse_args(argv)

    results = run_readiness_checks()
    ready = all(r.ok for r in results)

    if args.json:
        print(json.dumps({"ready": ready, "checks": [asdict(r) for r in results]}, indent=2))
    else:
        for r in results:
            print(f"{'OK  ' if r.ok else 'FAIL'} {r.name:<15} {r.latency_ms:>8.1f} ms  {r.detail}")
        print("READY" if ready else "NOT READY")

    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
