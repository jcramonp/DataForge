-- DataForge Sprint 1 Alpha
-- Operational metadata schema draft
-- This schema models the DataForge control plane. Client business data remains in Parquet/object storage.

CREATE TABLE IF NOT EXISTS client (
    client_id BIGSERIAL PRIMARY KEY,
    client_code VARCHAR(80) NOT NULL UNIQUE,
    client_name VARCHAR(160) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project (
    project_id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES client(client_id),
    project_code VARCHAR(80) NOT NULL UNIQUE,
    project_name VARCHAR(160) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS data_source (
    source_id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES project(project_id),
    source_code VARCHAR(80) NOT NULL,
    source_type VARCHAR(40) NOT NULL,
    source_name VARCHAR(160) NOT NULL,
    connection_reference TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_data_source_project_code UNIQUE (project_id, source_code)
);

CREATE TABLE IF NOT EXISTS dataset (
    dataset_id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES data_source(source_id),
    dataset_code VARCHAR(100) NOT NULL,
    dataset_name VARCHAR(160) NOT NULL,
    logical_entity VARCHAR(160),
    classification VARCHAR(40) NOT NULL DEFAULT 'internal',
    owner_name VARCHAR(160),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dataset_source_code UNIQUE (source_id, dataset_code)
);

CREATE TABLE IF NOT EXISTS dataset_version (
    dataset_version_id BIGSERIAL PRIMARY KEY,
    dataset_id BIGINT NOT NULL REFERENCES dataset(dataset_id),
    version_label VARCHAR(100) NOT NULL,
    schema_hash VARCHAR(128),
    source_checksum VARCHAR(128),
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dataset_version UNIQUE (dataset_id, version_label)
);

CREATE TABLE IF NOT EXISTS pipeline_run (
    run_id BIGSERIAL PRIMARY KEY,
    dataset_version_id BIGINT NOT NULL REFERENCES dataset_version(dataset_version_id),
    run_type VARCHAR(40) NOT NULL,
    status VARCHAR(30) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    input_rows BIGINT,
    accepted_rows BIGINT,
    rejected_rows BIGINT,
    error_message TEXT,
    CONSTRAINT ck_pipeline_run_counts_nonnegative CHECK (
        COALESCE(input_rows, 0) >= 0
        AND COALESCE(accepted_rows, 0) >= 0
        AND COALESCE(rejected_rows, 0) >= 0
    )
);

CREATE TABLE IF NOT EXISTS quality_result (
    quality_result_id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES pipeline_run(run_id) ON DELETE CASCADE,
    rule_name VARCHAR(160) NOT NULL,
    rule_type VARCHAR(80) NOT NULL,
    status VARCHAR(30) NOT NULL,
    failed_rows BIGINT NOT NULL DEFAULT 0,
    failure_percentage NUMERIC(7,4),
    details_json JSONB,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_quality_failed_rows_nonnegative CHECK (failed_rows >= 0),
    CONSTRAINT ck_quality_failure_percentage CHECK (
        failure_percentage IS NULL OR (failure_percentage >= 0 AND failure_percentage <= 100)
    )
);

CREATE TABLE IF NOT EXISTS data_asset (
    asset_id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES pipeline_run(run_id) ON DELETE CASCADE,
    layer VARCHAR(30) NOT NULL,
    asset_name VARCHAR(200) NOT NULL,
    storage_uri TEXT NOT NULL,
    format VARCHAR(30) NOT NULL,
    row_count BIGINT,
    checksum VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_data_asset_row_count_nonnegative CHECK (row_count IS NULL OR row_count >= 0),
    CONSTRAINT ck_data_asset_layer CHECK (layer IN ('bronze', 'silver', 'quarantine', 'gold'))
);

-- Initial indexes justified by expected metadata access patterns.
CREATE INDEX IF NOT EXISTS idx_project_client_id
    ON project(client_id);

CREATE INDEX IF NOT EXISTS idx_data_source_project_id
    ON data_source(project_id);

CREATE INDEX IF NOT EXISTS idx_dataset_source_id
    ON dataset(source_id);

CREATE INDEX IF NOT EXISTS idx_dataset_version_dataset_id
    ON dataset_version(dataset_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_dataset_version_id
    ON pipeline_run(dataset_version_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_status_started_at
    ON pipeline_run(status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_quality_result_run_id
    ON quality_result(run_id);

CREATE INDEX IF NOT EXISTS idx_data_asset_run_id_layer
    ON data_asset(run_id, layer);
