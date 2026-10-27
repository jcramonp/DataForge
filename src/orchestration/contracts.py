"""Load immutable executable contracts persisted by the control plane."""

from __future__ import annotations

from pydantic import ValidationError

from src.common.clients import connect_postgres
from src.contracts.models import DataForgeContract


class PersistedContractError(RuntimeError):
    """Raised when a persisted contract cannot be loaded safely."""


def load_persisted_contract(
    contract_id: int,
) -> DataForgeContract:
    """Load one exact configuration_contract revision by primary key."""

    if contract_id < 1:
        raise PersistedContractError(
            "contract_id must be a positive integer"
        )

    with connect_postgres() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT contract_json
                FROM configuration_contract
                WHERE contract_id = %s
                """,
                (contract_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise PersistedContractError(
            f"Configuration contract {contract_id} was not found"
        )

    try:
        return DataForgeContract.model_validate(row[0])
    except ValidationError as exc:
        raise PersistedContractError(
            f"Configuration contract {contract_id} is invalid"
        ) from exc
