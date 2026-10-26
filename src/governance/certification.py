"""Dataset-version certification services for DataForge."""

from __future__ import annotations

import json
from typing import Any

import psycopg


CERTIFICATION_STATES = (
    "draft",
    "validated",
    "certified",
)

ALLOWED_TRANSITIONS = {
    "draft": {"validated"},
    "validated": {"certified"},
    "certified": set(),
}


class CertificationError(RuntimeError):
    """Base error for certification operations."""


class CertificationNotFoundError(CertificationError):
    """Raised when the dataset version does not exist."""


class CertificationTransitionError(CertificationError):
    """Raised when a state transition is not allowed."""


class CertificationCriteriaError(CertificationError):
    """Raised when required certification criteria are not satisfied."""


def evaluate_certification(
    conn: psycopg.Connection,
    dataset_version_id: int,
) -> dict[str, Any]:
    """Evaluate governance criteria for one dataset version.

    Validation readiness requires:
    - schema metadata;
    - ownership;
    - version metadata;
    - at least one successfully produced non-quarantine asset.

    Certification additionally requires:
    - quality evidence from successful upstream quality-gate runs;
    - explicit upstream asset lineage.

    Critical source-rule violations may exist when the violating rows were
    successfully isolated in Quarantine and are therefore excluded from the
    validated assets consumed downstream.
    """

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                dv.version_label,
                dv.schema_hash,
                dv.source_checksum,
                d.owner_name
            FROM dataset_version dv
            JOIN dataset d
                ON d.dataset_id = dv.dataset_id
            WHERE dv.dataset_version_id = %s
            """,
            (dataset_version_id,),
        )

        metadata_row = cursor.fetchone()

    if metadata_row is None:
        raise CertificationNotFoundError(
            f"Dataset version {dataset_version_id} does not exist."
        )

    (
        version_label,
        schema_hash,
        source_checksum,
        owner_name,
    ) = metadata_row

    with conn.cursor() as cursor:
        cursor.execute(
            """
            WITH RECURSIVE target_assets AS (
                SELECT da.asset_id
                FROM data_asset da
                JOIN pipeline_run pr
                    ON pr.run_id = da.run_id
                WHERE pr.dataset_version_id = %s
                  AND pr.status = 'success'
                  AND da.layer <> 'quarantine'
            ),
            upstream_assets AS (
                SELECT
                    al.parent_asset_id AS asset_id,
                    ARRAY[
                        al.child_asset_id,
                        al.parent_asset_id
                    ]::BIGINT[] AS path
                FROM asset_lineage al
                JOIN target_assets ta
                    ON ta.asset_id = al.child_asset_id

                UNION ALL

                SELECT
                    al.parent_asset_id,
                    ua.path || al.parent_asset_id
                FROM asset_lineage al
                JOIN upstream_assets ua
                    ON al.child_asset_id = ua.asset_id
                WHERE NOT (
                    al.parent_asset_id = ANY(ua.path)
                )
            ),
            lineage_assets AS (
                SELECT asset_id
                FROM target_assets

                UNION

                SELECT asset_id
                FROM upstream_assets
            ),
            quality_runs AS (
                SELECT DISTINCT
                    pr.run_id
                FROM lineage_assets la
                JOIN data_asset da
                    ON da.asset_id = la.asset_id
                JOIN pipeline_run pr
                    ON pr.run_id = da.run_id
                WHERE pr.run_type = 'silver_quality_gate'
                  AND pr.status = 'success'
                  AND da.layer = 'silver'
            )
            SELECT
                COUNT(qr.quality_result_id)
                    AS total_rules,

                COUNT(qr.quality_result_id) FILTER (
                    WHERE qr.status = 'fail'
                      AND COALESCE(
                          qr.details_json ->> 'severity',
                          'critical'
                      ) = 'critical'
                ) AS critical_failures,

                (
                    SELECT COUNT(*)
                    FROM quality_runs
                ) AS successful_quality_gate_runs

            FROM quality_runs qrun
            LEFT JOIN quality_result qr
                ON qr.run_id = qrun.run_id
            """,
            (dataset_version_id,),
        )

        quality_row = cursor.fetchone()

    total_quality_rules = int(
        quality_row[0] if quality_row else 0
    )

    critical_failures = int(
        quality_row[1] if quality_row else 0
    )

    successful_quality_gate_runs = int(
        quality_row[2] if quality_row else 0
    )

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS asset_count,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1
                        FROM asset_lineage al
                        WHERE al.child_asset_id = da.asset_id
                    )
                ) AS assets_with_upstream_lineage
            FROM data_asset da
            JOIN pipeline_run pr
                ON pr.run_id = da.run_id
            WHERE pr.dataset_version_id = %s
              AND pr.status = 'success'
              AND da.layer <> 'quarantine'
            """,
            (dataset_version_id,),
        )

        asset_row = cursor.fetchone()

    asset_count = int(
        asset_row[0] if asset_row else 0
    )

    lineage_asset_count = int(
        asset_row[1] if asset_row else 0
    )

    schema_ok = bool(
        schema_hash
        and str(schema_hash).strip()
    )

    ownership_ok = bool(
        owner_name
        and str(owner_name).strip()
    )

    version_ok = bool(
        version_label
        and str(version_label).strip()
        and source_checksum
        and str(source_checksum).strip()
    )

    quality_evaluated = (
        total_quality_rules > 0
        and successful_quality_gate_runs > 0
    )

    quality_ok = quality_evaluated

    asset_available = (
        asset_count > 0
    )

    lineage_ok = (
        lineage_asset_count > 0
    )

    validation_ready = all(
        (
            schema_ok,
            ownership_ok,
            version_ok,
            asset_available,
        )
    )

    certification_ready = all(
        (
            schema_ok,
            ownership_ok,
            version_ok,
            quality_ok,
            lineage_ok,
            asset_available,
        )
    )

    return {
        "dataset_version_id": dataset_version_id,
        "criteria": {
            "schema": schema_ok,
            "ownership": ownership_ok,
            "version": version_ok,
            "quality": quality_ok,
            "lineage": lineage_ok,
        },
        "details": {
            "asset_available": asset_available,
            "asset_count": asset_count,
            "assets_with_upstream_lineage": lineage_asset_count,
            "quality_evaluated": quality_evaluated,
            "quality_rule_count": total_quality_rules,
            "critical_quality_failures": critical_failures,
            "successful_quality_gate_runs":
                successful_quality_gate_runs,
        },
        "validation_ready": validation_ready,
        "certification_ready": certification_ready,
    }


def get_certification(
    conn: psycopg.Connection,
    dataset_version_id: int,
) -> dict[str, Any]:
    """Return the API-ready certification state for one version."""

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                dc.certification_id,
                dc.dataset_version_id,
                dc.state,
                dc.criteria_json,
                dc.last_evaluated_at,
                dc.validated_at,
                dc.certified_at,
                dc.created_at,
                dc.updated_at
            FROM dataset_certification dc
            WHERE dc.dataset_version_id = %s
            """,
            (dataset_version_id,),
        )

        row = cursor.fetchone()

    if row is None:
        raise CertificationNotFoundError(
            "Certification record was not found for "
            f"dataset version {dataset_version_id}."
        )

    return {
        "certification_id": row[0],
        "dataset_version_id": row[1],
        "state": row[2],
        "criteria": row[3] or {},
        "last_evaluated_at": row[4],
        "validated_at": row[5],
        "certified_at": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


def get_certification_history(
    conn: psycopg.Connection,
    dataset_version_id: int,
) -> list[dict[str, Any]]:
    """Return state transitions in chronological order."""

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                ct.transition_id,
                ct.from_state,
                ct.to_state,
                ct.reason,
                ct.criteria_json,
                ct.changed_by,
                ct.changed_at
            FROM certification_transition ct
            JOIN dataset_certification dc
                ON dc.certification_id =
                   ct.certification_id
            WHERE dc.dataset_version_id = %s
            ORDER BY
                ct.changed_at,
                ct.transition_id
            """,
            (dataset_version_id,),
        )

        rows = cursor.fetchall()

    return [
        {
            "transition_id": row[0],
            "from_state": row[1],
            "to_state": row[2],
            "reason": row[3],
            "criteria": row[4] or {},
            "changed_by": row[5],
            "changed_at": row[6],
        }
        for row in rows
    ]


def _failed_criteria(
    evaluation: dict[str, Any],
) -> list[str]:
    return [
        name
        for name, passed
        in evaluation["criteria"].items()
        if not passed
    ]


def transition_certification(
    conn: psycopg.Connection,
    dataset_version_id: int,
    target_state: str,
    *,
    reason: str | None = None,
    changed_by: str = "system",
) -> dict[str, Any]:
    """Move certification forward after enforcing governance criteria."""

    if target_state not in CERTIFICATION_STATES:
        raise CertificationTransitionError(
            f"Unknown certification state: {target_state}"
        )

    current = get_certification(
        conn,
        dataset_version_id,
    )

    current_state = current["state"]

    if target_state == current_state:
        return current

    allowed = ALLOWED_TRANSITIONS.get(
        current_state,
        set(),
    )

    if target_state not in allowed:
        raise CertificationTransitionError(
            "Invalid certification transition: "
            f"{current_state} -> {target_state}"
        )

    evaluation = evaluate_certification(
        conn,
        dataset_version_id,
    )

    if target_state == "validated":
        if not evaluation[
            "validation_ready"
        ]:
            missing = []

            criteria = evaluation["criteria"]
            details = evaluation["details"]

            for criterion in (
                "schema",
                "ownership",
                "version",
            ):
                if not criteria[criterion]:
                    missing.append(
                        criterion
                    )

            if not details[
                "asset_available"
            ]:
                missing.append(
                    "asset"
                )

            raise CertificationCriteriaError(
                "Dataset version cannot become "
                "Validated. Missing criteria: "
                + ", ".join(missing)
            )

    if target_state == "certified":
        if not evaluation[
            "certification_ready"
        ]:
            missing = _failed_criteria(
                evaluation
            )

            if not evaluation["details"][
                "asset_available"
            ]:
                missing.append(
                    "asset"
                )

            raise CertificationCriteriaError(
                "Dataset version cannot become "
                "Certified. Missing criteria: "
                + ", ".join(missing)
            )

    criteria_json = json.dumps(
        {
            "criteria": evaluation[
                "criteria"
            ],
            "details": evaluation[
                "details"
            ],
            "validation_ready": evaluation[
                "validation_ready"
            ],
            "certification_ready": evaluation[
                "certification_ready"
            ],
        },
        sort_keys=True,
        default=str,
    )

    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE dataset_certification
            SET
                state = %s,
                criteria_json = %s::jsonb,
                last_evaluated_at = NOW(),
                validated_at =
                    CASE
                        WHEN %s = 'validated'
                        THEN COALESCE(
                            validated_at,
                            NOW()
                        )
                        ELSE validated_at
                    END,
                certified_at =
                    CASE
                        WHEN %s = 'certified'
                        THEN COALESCE(
                            certified_at,
                            NOW()
                        )
                        ELSE certified_at
                    END,
                updated_at = NOW()
            WHERE dataset_version_id = %s
            RETURNING certification_id
            """,
            (
                target_state,
                criteria_json,
                target_state,
                target_state,
                dataset_version_id,
            ),
        )

        row = cursor.fetchone()

        if row is None:
            raise CertificationNotFoundError(
                "Certification record disappeared "
                f"for dataset version {dataset_version_id}."
            )

        certification_id = int(
            row[0]
        )

        cursor.execute(
            """
            INSERT INTO certification_transition (
                certification_id,
                from_state,
                to_state,
                reason,
                criteria_json,
                changed_by
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s::jsonb,
                %s
            )
            """,
            (
                certification_id,
                current_state,
                target_state,
                reason,
                criteria_json,
                changed_by,
            ),
        )

    return get_certification(
        conn,
        dataset_version_id,
    )