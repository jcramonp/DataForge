"""Resolve an orchestration request into a validated, serializable pipeline plan.

A plan says which contract to run, which stages, and on which targets
(source datasets for Bronze/profiling/Silver, Gold codes for Gold). It is the
only input orchestration needs: Airflow and the standalone CLI both build a
plan from the same parameters, so a new contract or dataset never needs new
orchestration code.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.common.settings import PROJECT_ROOT
from src.contracts.loader import load_contract
from src.contracts.models import DataForgeContract


# Execution order. Bronze -> profiling -> Silver (+ Quality Gate) run per
# source dataset; Gold runs per Gold code; certification runs once at the end.
STAGES = ("bronze", "profiling", "silver", "gold", "certification")
DATASET_STAGES = ("bronze", "profiling", "silver")

CERTIFICATION_MODES = ("evaluate", "validate")


class PlanError(ValueError):
    """Invalid orchestration request. Never retried: retrying cannot fix it."""


@dataclass(frozen=True)
class PipelinePlan:
    contract_path: str
    client_code: str
    project_code: str
    source_code: str
    stages: list[str]
    datasets: list[str]
    gold: list[str]
    certification: str = "evaluate"
    parameters: dict[str, Any] = field(default_factory=dict)
    contract_id: int | None = None

    def runs(self, stage: str) -> bool:
        return stage in self.stages

    def targets(self, stage: str) -> list[str]:
        """Targets a stage processes in this plan (empty when not selected)."""

        if not self.runs(stage):
            return []
        if stage in DATASET_STAGES:
            return list(self.datasets)
        if stage == "gold":
            return list(self.gold)
        return ["contract"]

    def expected_tasks(self) -> list[tuple[str, str]]:
        return [(stage, target) for stage in STAGES for target in self.targets(stage)]

    def absolute_contract_path(self) -> Path:
        if self.contract_id is not None:
            raise PlanError(
                "Persisted contracts do not have a filesystem path"
            )
        return resolve_contract_path(self.contract_path)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelinePlan":
        return cls(**data)


def resolve_contract_path(contract: str | Path) -> Path:
    """Resolve a contract path; relative paths are relative to the repository root."""

    path = Path(contract)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.is_file():
        raise PlanError(f"Contract file not found: {contract}")
    if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
        raise PlanError(f"Contract must be a .yaml, .yml or .json file: {contract}")
    return path


def display_contract_path(path: Path) -> str:
    """Repository-relative path when possible, so plans are portable across hosts/containers."""

    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _normalize(values: Iterable[str] | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = values.split(",")
    return [value.strip() for value in values if value and value.strip()]


def _load(contract_path: Path) -> DataForgeContract:
    try:
        return load_contract(contract_path)
    except ValidationError as exc:
        raise PlanError(f"Invalid contract {contract_path.name}: {exc}") from exc
    except (ValueError, yaml.YAMLError) as exc:
        raise PlanError(f"Invalid contract {contract_path.name}: {exc}") from exc


def build_plan_from_contract(
    parsed: DataForgeContract,
    *,
    contract_reference: str,
    contract_id: int | None = None,
    datasets: Iterable[str] | str | None = None,
    gold: Iterable[str] | str | None = None,
    stages: Iterable[str] | str | None = None,
    certification: str = "evaluate",
) -> PipelinePlan:
    """Build a validated plan from an already validated contract model."""

    requested_stages = _normalize(stages) or list(STAGES)

    unknown_stages = sorted(
        set(requested_stages) - set(STAGES)
    )

    if unknown_stages:
        raise PlanError(
            f"Unknown stage(s): {', '.join(unknown_stages)}. "
            f"Valid stages: {', '.join(STAGES)}"
        )

    ordered_stages = [
        stage
        for stage in STAGES
        if stage in requested_stages
    ]

    contract_datasets = [
        dataset.code
        for dataset in parsed.datasets
    ]

    requested_datasets = _normalize(datasets)

    unknown_datasets = sorted(
        set(requested_datasets)
        - set(contract_datasets)
    )

    if unknown_datasets:
        raise PlanError(
            "Unknown dataset(s) for contract "
            f"{parsed.project.code}: "
            f"{', '.join(unknown_datasets)}. "
            f"Available: {', '.join(contract_datasets)}"
        )

    selected_datasets = [
        code
        for code in contract_datasets
        if (
            not requested_datasets
            or code in requested_datasets
        )
    ]

    enabled_gold = [
        config.code
        for config in parsed.gold
        if config.enabled
    ]

    requested_gold = _normalize(gold)

    if requested_gold:
        all_gold = {
            config.code: config
            for config in parsed.gold
        }

        unknown_gold = sorted(
            code
            for code in requested_gold
            if code not in all_gold
        )

        if unknown_gold:
            raise PlanError(
                "Unknown Gold dataset(s): "
                f"{', '.join(unknown_gold)}. "
                "Available: "
                f"{', '.join(all_gold) or 'none'}"
            )

        disabled = sorted(
            code
            for code in requested_gold
            if not all_gold[code].enabled
        )

        if disabled:
            raise PlanError(
                "Gold dataset(s) disabled in the contract: "
                f"{', '.join(disabled)}"
            )

    selected_gold = [
        code
        for code in enabled_gold
        if (
            not requested_gold
            or code in requested_gold
        )
    ]

    if (
        requested_gold
        and "gold" not in ordered_stages
    ):
        raise PlanError(
            "Gold datasets were requested but the "
            "'gold' stage is not selected"
        )

    if certification not in CERTIFICATION_MODES:
        raise PlanError(
            f"Unknown certification mode '{certification}'. "
            f"Valid: {', '.join(CERTIFICATION_MODES)}"
        )

    return PipelinePlan(
        contract_path=contract_reference,
        client_code=parsed.client.code,
        project_code=parsed.project.code,
        source_code=parsed.source.code,
        stages=ordered_stages,
        datasets=selected_datasets,
        gold=(
            selected_gold
            if "gold" in ordered_stages
            else []
        ),
        certification=certification,
        parameters={
            "contract": contract_reference,
            "contract_id": contract_id,
            "datasets": requested_datasets,
            "gold": requested_gold,
            "stages": requested_stages,
            "certification": certification,
        },
        contract_id=contract_id,
    )


def build_plan(
    contract: str | Path,
    *,
    datasets: Iterable[str] | str | None = None,
    gold: Iterable[str] | str | None = None,
    stages: Iterable[str] | str | None = None,
    certification: str = "evaluate",
) -> PipelinePlan:
    """Build a plan from a filesystem contract."""

    contract_path = resolve_contract_path(contract)
    parsed = _load(contract_path)

    return build_plan_from_contract(
        parsed,
        contract_reference=display_contract_path(
            contract_path
        ),
        datasets=datasets,
        gold=gold,
        stages=stages,
        certification=certification,
    )


def build_persisted_plan(
    contract_id: int,
    *,
    datasets: Iterable[str] | str | None = None,
    gold: Iterable[str] | str | None = None,
    stages: Iterable[str] | str | None = None,
    certification: str = "evaluate",
) -> PipelinePlan:
    """Build a plan from an immutable PostgreSQL contract revision."""

    from src.orchestration.contracts import (
        PersistedContractError,
        load_persisted_contract,
    )

    try:
        parsed = load_persisted_contract(contract_id)
    except PersistedContractError as exc:
        raise PlanError(str(exc)) from exc

    return build_plan_from_contract(
        parsed,
        contract_reference=(
            f"db://configuration_contract/{contract_id}"
        ),
        contract_id=contract_id,
        datasets=datasets,
        gold=gold,
        stages=stages,
        certification=certification,
    )
