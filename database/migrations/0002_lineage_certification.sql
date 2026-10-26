-- DataForge Sprint 2
-- Explicit asset lineage and dataset-version certification.
--
-- This migration is intentionally additive so existing Sprint 1
-- metadata, runs, quality results and data assets remain readable.
--
-- No BEGIN/COMMIT here: src/ops/migrate.py runs each migration in its own
-- transaction (see docs/operations/migrations.md).


-- ============================================================
-- 1. Explicit asset-to-asset lineage
-- ============================================================

CREATE TABLE IF NOT EXISTS asset_lineage (
    lineage_id BIGSERIAL PRIMARY KEY,

    parent_asset_id BIGINT NOT NULL
        REFERENCES data_asset(asset_id)
        ON DELETE CASCADE,

    child_asset_id BIGINT NOT NULL
        REFERENCES data_asset(asset_id)
        ON DELETE CASCADE,

    relation_type VARCHAR(40) NOT NULL
        DEFAULT 'derived_from',

    created_by_run_id BIGINT
        REFERENCES pipeline_run(run_id)
        ON DELETE SET NULL,

    metadata_json JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT ck_asset_lineage_no_self_reference
        CHECK (parent_asset_id <> child_asset_id),

    CONSTRAINT ck_asset_lineage_relation_type
        CHECK (
            relation_type IN (
                'derived_from',
                'transformed_from',
                'validated_from',
                'quarantined_from',
                'joined_from'
            )
        ),

    CONSTRAINT uq_asset_lineage_edge
        UNIQUE (
            parent_asset_id,
            child_asset_id,
            relation_type
        )
);


CREATE INDEX IF NOT EXISTS idx_asset_lineage_parent
    ON asset_lineage(parent_asset_id);


CREATE INDEX IF NOT EXISTS idx_asset_lineage_child
    ON asset_lineage(child_asset_id);


CREATE INDEX IF NOT EXISTS idx_asset_lineage_created_by_run
    ON asset_lineage(created_by_run_id);


-- ============================================================
-- 2. Certification state for each dataset version
-- ============================================================

CREATE TABLE IF NOT EXISTS dataset_certification (
    certification_id BIGSERIAL PRIMARY KEY,

    dataset_version_id BIGINT NOT NULL UNIQUE
        REFERENCES dataset_version(dataset_version_id)
        ON DELETE CASCADE,

    state VARCHAR(20) NOT NULL
        DEFAULT 'draft',

    criteria_json JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    last_evaluated_at TIMESTAMPTZ,

    validated_at TIMESTAMPTZ,

    certified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT ck_dataset_certification_state
        CHECK (
            state IN (
                'draft',
                'validated',
                'certified'
            )
        )
);


CREATE INDEX IF NOT EXISTS idx_dataset_certification_state
    ON dataset_certification(state);


-- ============================================================
-- 3. Certification transition history
-- ============================================================

CREATE TABLE IF NOT EXISTS certification_transition (
    transition_id BIGSERIAL PRIMARY KEY,

    certification_id BIGINT NOT NULL
        REFERENCES dataset_certification(certification_id)
        ON DELETE CASCADE,

    from_state VARCHAR(20),

    to_state VARCHAR(20) NOT NULL,

    reason TEXT,

    criteria_json JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    changed_by VARCHAR(160) NOT NULL
        DEFAULT 'system',

    changed_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT ck_certification_transition_from_state
        CHECK (
            from_state IS NULL
            OR from_state IN (
                'draft',
                'validated',
                'certified'
            )
        ),

    CONSTRAINT ck_certification_transition_to_state
        CHECK (
            to_state IN (
                'draft',
                'validated',
                'certified'
            )
        )
);


CREATE INDEX IF NOT EXISTS idx_certification_transition_certification
    ON certification_transition(
        certification_id,
        changed_at DESC
    );


-- ============================================================
-- 4. Backfill Sprint 1 versions as Draft
-- ============================================================

INSERT INTO dataset_certification (
    dataset_version_id,
    state,
    criteria_json
)
SELECT
    dv.dataset_version_id,
    'draft',
    '{}'::jsonb
FROM dataset_version dv
ON CONFLICT (dataset_version_id)
DO NOTHING;


-- Record the initial Draft transition for versions that do not
-- yet have certification history.

INSERT INTO certification_transition (
    certification_id,
    from_state,
    to_state,
    reason,
    criteria_json,
    changed_by
)
SELECT
    dc.certification_id,
    NULL,
    'draft',
    'Initial certification state',
    dc.criteria_json,
    'migration'
FROM dataset_certification dc
WHERE NOT EXISTS (
    SELECT 1
    FROM certification_transition ct
    WHERE ct.certification_id = dc.certification_id
);


-- ============================================================
-- 5. Automatically create Draft certification for new versions
-- ============================================================

CREATE OR REPLACE FUNCTION initialize_dataset_certification()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    new_certification_id BIGINT;
BEGIN
    INSERT INTO dataset_certification (
        dataset_version_id,
        state,
        criteria_json
    )
    VALUES (
        NEW.dataset_version_id,
        'draft',
        '{}'::jsonb
    )
    ON CONFLICT (dataset_version_id)
    DO NOTHING
    RETURNING certification_id
    INTO new_certification_id;

    IF new_certification_id IS NOT NULL THEN
        INSERT INTO certification_transition (
            certification_id,
            from_state,
            to_state,
            reason,
            criteria_json,
            changed_by
        )
        VALUES (
            new_certification_id,
            NULL,
            'draft',
            'Dataset version created',
            '{}'::jsonb,
            'system'
        );
    END IF;

    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS trg_initialize_dataset_certification
    ON dataset_version;


CREATE TRIGGER trg_initialize_dataset_certification
AFTER INSERT
ON dataset_version
FOR EACH ROW
EXECUTE FUNCTION initialize_dataset_certification();
