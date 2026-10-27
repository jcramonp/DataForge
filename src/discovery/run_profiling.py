"""CLI and utilities for DataForge generic schema discovery and profiling."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.log import configure_logging
from src.connectors.registry import get_dataset_connector
from src.contracts.loader import load_contract
from src.contracts.models import DataForgeContract
from src.discovery.engine import profile_dataframe
from src.discovery.reporter import save_profile_reports
from src.discovery.service import run_profiling_pipeline


def profile_contract_dataset(
    contract: DataForgeContract,
    dataset_code: str,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Profile a contract source directly without persistence.

    This helper is intentionally retained for discovery, tests and callers
    that need source inspection before Bronze ingestion. Production contract
    profiling through the CLI uses the persistent Bronze-backed service.
    """
    connector = get_dataset_connector(contract, dataset_code)
    frame = connector.extract()

    profile = profile_dataframe(
        frame,
        dataset_name=dataset_code,
    )

    if output_dir:
        save_profile_reports(
            profile,
            output_dir,
            base_name=dataset_code,
        )

    return profile


def profile_contract(
    contract_path: Path | str,
    output_dir: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    """Profile contract sources directly without control-plane persistence."""
    contract = load_contract(contract_path)

    results: dict[str, dict[str, Any]] = {}

    for dataset in contract.datasets:
        results[dataset.code] = profile_contract_dataset(
            contract=contract,
            dataset_code=dataset.code,
            output_dir=output_dir,
        )

    return results


def profile_ad_hoc_file(
    file_path: Path,
    dataset_name: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Profile a local ad-hoc file without modifying the control plane."""
    suffix = file_path.suffix.lower()

    if suffix == ".csv":
        frame = pd.read_csv(file_path)
    elif suffix == ".parquet":
        frame = pd.read_parquet(
            file_path,
            engine="pyarrow",
        )
    elif suffix == ".json":
        frame = pd.read_json(file_path)
    else:
        raise ValueError(
            f"Unsupported file format: {suffix}"
        )

    profile = profile_dataframe(
        frame,
        dataset_name=dataset_name,
    )

    json_path, markdown_path = save_profile_reports(
        profile,
        output_dir,
        base_name=dataset_name,
    )

    return Path(json_path), Path(markdown_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DataForge Generic Schema Discovery & Profiling"
    )

    source_group = parser.add_mutually_exclusive_group(
        required=True
    )

    source_group.add_argument(
        "--contract",
        type=Path,
        help=(
            "Path to a DataForge YAML/JSON contract. "
            "Profiles the latest successful Bronze assets and persists "
            "the results in the control plane."
        ),
    )

    source_group.add_argument(
        "--file",
        type=Path,
        help=(
            "Raw CSV, Parquet or JSON file for ad-hoc profiling. "
            "Ad-hoc profiling does not persist to the control plane."
        ),
    )

    parser.add_argument(
        "--dataset-name",
        type=str,
        default="dataset",
        help="Dataset name for ad-hoc file profiling",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/profiling"),
        help="Directory for JSON and Markdown profile reports",
    )

    args = parser.parse_args()

    configure_logging()

    if args.contract:
        results = run_profiling_pipeline(
            args.contract
        )

        for result in results:
            profile = result["profile"]

            save_profile_reports(
                profile,
                args.output_dir,
                base_name=result["dataset"],
            )

        print(
            f"Persistent profiling completed for "
            f"{len(results)} dataset(s):"
        )

        for result in results:
            print(
                f"- {result['dataset']}: "
                f"{result['row_count']} rows, "
                f"{result['column_count']} columns "
                f"(profile_id={result['profile_id']}, "
                f"run_id={result['run_id']}, "
                f"source_asset_id={result['source_asset_id']})"
            )

        return 0

    if not args.file.exists():
        print(f"File not found: {args.file}")
        return 1

    try:
        json_path, markdown_path = profile_ad_hoc_file(
            file_path=args.file,
            dataset_name=args.dataset_name,
            output_dir=args.output_dir,
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    print(
        f"Ad-hoc profile written to "
        f"{json_path} and {markdown_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
