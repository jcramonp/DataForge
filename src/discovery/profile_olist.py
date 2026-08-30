"""Profile the four Olist CSV files selected for the Sprint 1 Alpha.

The script uses only Python's standard library so discovery can run before the
Alpha infrastructure exists. It never modifies source data.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() == ""


def profile_csv(path: Path, table_contract: dict[str, Any]) -> dict[str, Any]:
    required = table_contract["required_columns"]
    primary_key = table_contract["primary_key"]
    missing_by_column: Counter[str] = Counter()
    value_examples: dict[str, list[str]] = {}
    row_fingerprints: Counter[tuple[str, ...]] = Counter()
    key_counts: Counter[tuple[str, ...]] = Counter()
    row_count = 0

    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames or []
        for column in columns:
            value_examples[column] = []

        for row in reader:
            row_count += 1
            fingerprint = tuple(row.get(column, "") for column in columns)
            row_fingerprints[fingerprint] += 1

            key = tuple(row.get(column, "") for column in primary_key)
            key_counts[key] += 1

            for column in columns:
                value = row.get(column)
                if is_missing(value):
                    missing_by_column[column] += 1
                elif len(value_examples[column]) < 3 and value not in value_examples[column]:
                    value_examples[column].append(value)

    missing_required_columns = sorted(set(required) - set(columns))
    unexpected_columns = sorted(set(columns) - set(required))
    duplicate_rows = sum(count - 1 for count in row_fingerprints.values() if count > 1)
    duplicate_primary_keys = sum(count - 1 for count in key_counts.values() if count > 1)
    null_primary_keys = sum(
        count for key, count in key_counts.items() if any(is_missing(part) for part in key)
    )

    return {
        "file": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
        "missing_required_columns": missing_required_columns,
        "unexpected_columns": unexpected_columns,
        "missing_values": {
            column: {
                "count": missing_by_column[column],
                "percentage": round((missing_by_column[column] / row_count * 100), 2)
                if row_count
                else 0.0,
            }
            for column in columns
        },
        "duplicate_rows": duplicate_rows,
        "primary_key": primary_key,
        "duplicate_primary_keys": duplicate_primary_keys,
        "null_primary_keys": null_primary_keys,
        "potential_pii": table_contract.get("potential_pii", []),
        "value_examples": value_examples,
    }


def profile_dataset(contract_path: Path, raw_directory: Path | None = None) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    source_directory = raw_directory or Path(contract["raw_directory"])
    tables: dict[str, Any] = {}

    for table_name, table_contract in contract["tables"].items():
        path = source_directory / table_contract["file"]
        if path.exists():
            tables[table_name] = profile_csv(path, table_contract)
        else:
            tables[table_name] = {
                "file": str(path),
                "exists": False,
                "error": "Source CSV not found",
            }

    return {
        "dataset": contract["dataset"],
        "source_url": contract["source_url"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "alpha_tables": list(contract["tables"]),
        "tables": tables,
    }


def to_markdown(profile: dict[str, Any]) -> str:
    lines = [
        "# Olist pilot profiling report",
        "",
        f"- Generated at: {profile['generated_at_utc']}",
        f"- Source: {profile['source_url']}",
        f"- Alpha tables: {', '.join(profile['alpha_tables'])}",
        "",
        "| Table | Rows | Columns | Duplicate rows | Duplicate keys | Null keys | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]

    for name, result in profile["tables"].items():
        if not result["exists"]:
            lines.append(f"| {name} | — | — | — | — | — | missing file |")
            continue
        status = "schema mismatch" if result["missing_required_columns"] else "profiled"
        lines.append(
            f"| {name} | {result['row_count']} | {result['column_count']} | "
            f"{result['duplicate_rows']} | {result['duplicate_primary_keys']} | "
            f"{result['null_primary_keys']} | {status} |"
        )

    lines.extend(["", "## Missing values", ""])
    for name, result in profile["tables"].items():
        if not result["exists"]:
            continue
        lines.append(f"### {name}")
        lines.append("")
        lines.append("| Column | Missing | Percentage |")
        lines.append("|---|---:|---:|")
        for column, stats in result["missing_values"].items():
            lines.append(f"| {column} | {stats['count']} | {stats['percentage']}% |")
        lines.append("")

    lines.extend(
        [
            "## Interpretation boundary",
            "",
            "This report is discovery evidence for Sprint 1. Quality thresholds and "
            "Silver/Quarantine routing are defined in the pipeline issue after the "
            "observed results are reviewed.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile the Olist Sprint 1 pilot dataset")
    parser.add_argument("--contract", type=Path, default=Path("config/pilot_olist.json"))
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated"))
    args = parser.parse_args()

    profile = profile_dataset(args.contract, args.raw_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "olist_profile.json"
    markdown_path = args.output_dir / "olist_profile.md"
    json_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path.write_text(to_markdown(profile), encoding="utf-8")

    missing = [name for name, result in profile["tables"].items() if not result["exists"]]
    print(f"Profile written to {json_path} and {markdown_path}")
    if missing:
        print(f"Missing source files: {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
