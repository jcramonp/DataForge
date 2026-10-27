"""Report generators for DataForge profiling results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def to_json(profile: dict[str, Any], indent: int = 2) -> str:
    """Serialize profiling dictionary to a formatted JSON string."""
    return json.dumps(profile, indent=indent, ensure_ascii=False, default=str)


def to_markdown(profile: dict[str, Any]) -> str:
    """Generate a clean, readable Markdown report from profiling results."""
    lines = [
        f"# DataForge Discovery & Profiling Report: {profile.get('dataset_name', 'Dataset')}",
        "",
        f"- **Generated at (UTC):** {profile.get('generated_at_utc', 'N/A')}",
        f"- **Total Rows:** {profile.get('row_count', 0):,}",
        f"- **Total Columns:** {profile.get('column_count', 0)}",
        f"- **Duplicate Rows:** {profile.get('duplicate_rows', 0):,} ({profile.get('duplicate_rows_percentage', 0.0)}%)",
    ]

    candidate_keys = profile.get("candidate_keys", [])
    if candidate_keys:
        lines.append(f"- **Candidate Keys (Zero nulls & 100% unique):** `{', '.join(candidate_keys)}`")
    else:
        lines.append("- **Candidate Keys:** None detected")

    lines.extend([
        "",
        "## Column Summary",
        "",
        "| Column | Inferred Type | Physical Dtype | Null Count | Null % | Unique Values | Uniqueness % | Sample Values |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ])

    columns = profile.get("columns", {})
    for col_name, col_prof in columns.items():
        samples = ", ".join(repr(s) for s in col_prof.get("sample_values", [])[:3])
        lines.append(
            f"| `{col_name}` | **{col_prof.get('inferred_type')}** | `{col_prof.get('physical_type')}` | "
            f"{col_prof.get('null_count'):,} | {col_prof.get('null_percentage')}% | "
            f"{col_prof.get('distinct_count'):,} | {round(col_prof.get('uniqueness_ratio', 0) * 100, 1)}% | "
            f"{samples} |"
        )

    lines.extend(["", "## Column Detailed Statistics", ""])
    for col_name, col_prof in columns.items():
        stats = col_prof.get("stats", {})
        if not stats:
            continue

        inferred_type = col_prof.get("inferred_type")
        lines.append(f"### `{col_name}` ({inferred_type})")
        lines.append("")

        if inferred_type in {"integer", "float"}:
            lines.extend([
                "| Metric | Value |",
                "|---|---:|",
                f"| Min | {stats.get('min')} |",
                f"| Max | {stats.get('max')} |",
                f"| Mean | {stats.get('mean')} |",
                f"| Median | {stats.get('median')} |",
                f"| Std Dev | {stats.get('std')} |",
                f"| Zeros Count | {stats.get('zeros_count')} |",
                f"| Negative Count | {stats.get('negative_count')} |",
                "",
            ])
        elif inferred_type == "string":
            lines.extend([
                "| Metric | Value |",
                "|---|---:|",
                f"| Min Length | {stats.get('min_length')} |",
                f"| Max Length | {stats.get('max_length')} |",
                f"| Avg Length | {stats.get('avg_length')} |",
                f"| Empty Strings | {stats.get('empty_string_count')} |",
                "",
            ])
        elif inferred_type in {"date", "datetime"}:
            lines.extend([
                "| Metric | Value |",
                "|---|---|",
                f"| Earliest (Min) | {stats.get('min_date')} |",
                f"| Latest (Max) | {stats.get('max_date')} |",
                "",
            ])

    lines.extend([
        "## Interpretation Boundary",
        "",
        "This profiling report records technical facts and statistics extracted from the raw data. "
        "It does not enforce business validation rules; validation policies and routing to Quarantine "
        "are handled declaratively by the Quality Gate in Silver.",
        "",
    ])

    return "\n".join(lines)


def save_profile_reports(
    profile: dict[str, Any],
    output_dir: Path | str,
    base_name: str | None = None,
) -> tuple[Path, Path]:
    """Save profiling results as JSON and Markdown files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = base_name or profile.get("dataset_name", "profile")

    json_path = output_path / f"{filename}.json"
    markdown_path = output_path / f"{filename}.md"

    json_path.write_text(to_json(profile), encoding="utf-8")
    markdown_path.write_text(to_markdown(profile), encoding="utf-8")

    return json_path, markdown_path
