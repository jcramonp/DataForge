-- DataForge Sprint 2 (#21)
-- Persistent generic profiling metadata.
--
-- One profiling_result belongs to one profiling pipeline_run and records the
-- exact Bronze asset that was inspected. The dataset version is obtained from
-- pipeline_run.dataset_version_id, avoiding duplicated version references.

CREATE TABLE IF NOT EXISTS profiling_result (
    profile_id BIGSERIAL PRIMARY KEY,

    run_id BIGINT NOT NULL UNIQUE
        REFERENCES pipeline_run(run_id)
        ON DELETE CASCADE,

    source_asset_id BIGINT NOT NULL
        REFERENCES data_asset(asset_id)
        ON DELETE RESTRICT,

    profile_version VARCHAR(20) NOT NULL
        DEFAULT '1.0',

    row_count BIGINT NOT NULL,

    column_count INTEGER NOT NULL,

    duplicate_rows BIGINT NOT NULL
        DEFAULT 0,

    duplicate_rows_percentage NUMERIC(7,4) NOT NULL
        DEFAULT 0,

    candidate_keys_json JSONB NOT NULL
        DEFAULT '[]'::jsonb,

    profile_json JSONB NOT NULL,

    generated_at TIMESTAMPTZ NOT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT ck_profiling_row_count_nonnegative
        CHECK (row_count >= 0),

    CONSTRAINT ck_profiling_column_count_nonnegative
        CHECK (column_count >= 0),

    CONSTRAINT ck_profiling_duplicate_rows_nonnegative
        CHECK (duplicate_rows >= 0),

    CONSTRAINT ck_profiling_duplicate_percentage
        CHECK (
            duplicate_rows_percentage >= 0
            AND duplicate_rows_percentage <= 100
        ),

    CONSTRAINT ck_profiling_candidate_keys_array
        CHECK (jsonb_typeof(candidate_keys_json) = 'array'),

    CONSTRAINT ck_profiling_profile_object
        CHECK (jsonb_typeof(profile_json) = 'object')
);


CREATE INDEX IF NOT EXISTS idx_profiling_result_source_asset
    ON profiling_result(source_asset_id);


CREATE INDEX IF NOT EXISTS idx_profiling_result_generated_at
    ON profiling_result(generated_at DESC);


-- API/service-ready history of persisted profiling executions.
CREATE OR REPLACE VIEW dataset_profiling_history AS
SELECT
    prf.profile_id,

    c.client_code,
    p.project_code,
    ds.source_code,

    d.dataset_id,
    d.dataset_code,
    d.dataset_name,

    dv.dataset_version_id,
    dv.version_label,
    dv.schema_hash,
    dv.source_checksum,

    pr.run_id,
    pr.run_type,
    pr.status AS run_status,
    pr.started_at,
    pr.finished_at,

    da.asset_id AS source_asset_id,
    da.layer AS source_layer,
    da.storage_uri AS source_storage_uri,
    da.checksum AS source_asset_checksum,

    prf.profile_version,
    prf.row_count,
    prf.column_count,
    prf.duplicate_rows,
    prf.duplicate_rows_percentage,
    prf.candidate_keys_json,
    prf.profile_json,
    prf.generated_at,
    prf.created_at

FROM profiling_result prf

JOIN pipeline_run pr
    ON pr.run_id = prf.run_id

JOIN dataset_version dv
    ON dv.dataset_version_id = pr.dataset_version_id

JOIN dataset d
    ON d.dataset_id = dv.dataset_id

JOIN data_source ds
    ON ds.source_id = d.source_id

JOIN project p
    ON p.project_id = ds.project_id

JOIN client c
    ON c.client_id = p.client_id

JOIN data_asset da
    ON da.asset_id = prf.source_asset_id;


-- Latest successful profiling result for each exact dataset scope.
CREATE OR REPLACE VIEW dataset_latest_profile AS
SELECT DISTINCT ON (
    client_code,
    project_code,
    source_code,
    dataset_code
)
    *
FROM dataset_profiling_history
WHERE run_status = 'success'
  AND run_type = 'profiling'
ORDER BY
    client_code,
    project_code,
    source_code,
    dataset_code,
    finished_at DESC NULLS LAST,
    run_id DESC;
