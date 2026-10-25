"""CLI and contract runner for DataForge generic schema discovery and profiling."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from src.connectors.registry import get_dataset_connector
from src.contracts.loader import load_contract
from src.contracts.models import DataForgeContract
from src.discovery.engine import profile_dataframe
from src.discovery.reporter import save_profile_reports


def profile_contract_dataset(
    contract: DataForgeContract,
    dataset_code: str,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Profile a single dataset defined within a DataForge contract."""
    connector = get_dataset_connector(contract, dataset_code)
    df = connector.extract()
    profile = profile_dataframe(df, dataset_name=dataset_code)
    if output_dir:
        save_profile_reports(profile, output_dir, base_name=dataset_code)
    return profile


def profile_contract(
    contract_path: Path | str,
    output_dir: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    """Profile all datasets declared in a DataForge contract."""
    contract = load_contract(contract_path)
    results: dict[str, dict[str, Any]] = {}
    for dataset in contract.datasets:
        results[dataset.code] = profile_contract_dataset(
            contract, dataset.code, output_dir=output_dir
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DataForge Generic Schema Discovery & Profiling"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        help="Path to DataForge YAML/JSON contract",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to raw file (CSV, Parquet, JSON) for ad-hoc discovery",
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
        help="Directory to save JSON and Markdown reports",
    )
    args = parser.parse_args()

    if args.contract:
        results = profile_contract(args.contract, output_dir=args.output_dir)
        print(f"Profiled {len(results)} dataset(s) from contract {args.contract}")
        return 0
    elif args.file:
        file_path = args.file
        if not file_path.exists():
            print(f"File not found: {file_path}")
            return 1
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(file_path)
        elif suffix == ".parquet":
            df = pd.read_parquet(file_path)
        elif suffix == ".json":
            df = pd.read_json(file_path)
        else:
            print(f"Unsupported file format: {suffix}")
            return 1
        profile = profile_dataframe(df, dataset_name=args.dataset_name)
        json_path, md_path = save_profile_reports(
            profile, args.output_dir, base_name=args.dataset_name
        )
        print(f"Ad-hoc profile written to {json_path} and {md_path}")
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
