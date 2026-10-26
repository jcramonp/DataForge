-- DataForge Sprint 2 (#32): operational status views for runs and failures.
-- Views are read by `python -m src.ops.run_summary` and `GET /api/ops/summary`.

CREATE OR REPLACE VIEW pipeline_run_status_summary AS
SELECT
    pr.run_type,
    pr.status,
    COUNT(*) AS run_count,
    COALESCE(SUM(pr.input_rows), 0) AS input_rows,
    COALESCE(SUM(pr.accepted_rows), 0) AS accepted_rows,
    COALESCE(SUM(pr.rejected_rows), 0) AS rejected_rows,
    ROUND(
        AVG(EXTRACT(EPOCH FROM (pr.finished_at - pr.started_at)))::numeric,
        3
    ) AS avg_duration_seconds,
    MAX(pr.started_at) AS last_started_at
FROM pipeline_run pr
GROUP BY pr.run_type, pr.status;


CREATE OR REPLACE VIEW pipeline_run_failures AS
SELECT
    pr.run_id,
    c.client_code,
    p.project_code,
    d.dataset_code,
    dv.version_label,
    pr.run_type,
    pr.started_at,
    pr.finished_at,
    ROUND(
        EXTRACT(EPOCH FROM (pr.finished_at - pr.started_at))::numeric,
        3
    ) AS duration_seconds,
    pr.error_message
FROM pipeline_run pr
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
WHERE pr.status = 'failed';


-- Latest run per dataset and stage: the current operational state of each dataset.
CREATE OR REPLACE VIEW dataset_latest_run AS
SELECT DISTINCT ON (c.client_code, d.dataset_code, pr.run_type)
    c.client_code,
    p.project_code,
    d.dataset_code,
    pr.run_type,
    pr.run_id,
    pr.status,
    pr.started_at,
    pr.finished_at,
    pr.input_rows,
    pr.accepted_rows,
    pr.rejected_rows,
    pr.error_message
FROM pipeline_run pr
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
ORDER BY c.client_code, d.dataset_code, pr.run_type, pr.started_at DESC, pr.run_id DESC;
