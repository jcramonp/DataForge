-- Latest-version lookup used by the dataset catalog and certification API.
CREATE INDEX IF NOT EXISTS idx_dataset_version_latest
    ON dataset_version(dataset_id, discovered_at DESC, dataset_version_id DESC);

-- Explicitly refreshed operational report. This cache is NOT the live UI overview.
CREATE MATERIALIZED VIEW IF NOT EXISTS metadata_run_totals_cache AS
SELECT dv.dataset_id, pr.run_type, pr.status,
       COUNT(*) AS run_count,
       COALESCE(SUM(pr.input_rows), 0) AS input_rows,
       COALESCE(SUM(pr.accepted_rows), 0) AS accepted_rows,
       COALESCE(SUM(pr.rejected_rows), 0) AS rejected_rows
FROM pipeline_run pr
JOIN dataset_version dv ON dv.dataset_version_id = pr.dataset_version_id
GROUP BY dv.dataset_id, pr.run_type, pr.status;

CREATE UNIQUE INDEX IF NOT EXISTS idx_metadata_run_totals_key
    ON metadata_run_totals_cache(dataset_id, run_type, status);

CREATE OR REPLACE VIEW metadata_run_totals AS
SELECT dataset_id, run_type, status, run_count, input_rows, accepted_rows, rejected_rows
FROM metadata_run_totals_cache;

COMMENT ON MATERIALIZED VIEW metadata_run_totals_cache IS
    'Operational snapshot; refresh explicitly with python -m src.ops.refresh_reports. Live API totals do not use this cache.';
