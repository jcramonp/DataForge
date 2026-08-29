CREATE OR REPLACE VIEW dataset_lineage_summary AS
SELECT
    c.client_code,
    c.client_name,
    p.project_code,
    p.project_name,
    ds.source_code,
    ds.source_type,
    ds.source_name,
    d.dataset_id,
    d.dataset_code,
    d.dataset_name,
    d.logical_entity,
    d.classification,
    d.owner_name,
    dv.dataset_version_id,
    dv.version_label,
    dv.schema_hash,
    dv.source_checksum,
    pr.run_id,
    pr.run_type,
    pr.status AS run_status,
    pr.started_at,
    pr.finished_at,
    pr.input_rows,
    pr.accepted_rows,
    pr.rejected_rows,
    da.asset_id,
    da.layer,
    da.asset_name,
    da.storage_uri,
    da.format,
    da.row_count,
    da.checksum AS asset_checksum,
    da.created_at AS asset_created_at
FROM client c
JOIN project p
    ON p.client_id = c.client_id
JOIN data_source ds
    ON ds.project_id = p.project_id
JOIN dataset d
    ON d.source_id = ds.source_id
JOIN dataset_version dv
    ON dv.dataset_id = d.dataset_id
JOIN pipeline_run pr
    ON pr.dataset_version_id = dv.dataset_version_id
JOIN data_asset da
    ON da.run_id = pr.run_id;



CREATE OR REPLACE VIEW data_quality_summary AS
SELECT
    c.client_code,
    p.project_code,
    d.dataset_code,
    d.dataset_name,
    dv.version_label,
    pr.run_id,
    pr.run_type,
    pr.status AS run_status,
    pr.input_rows,
    pr.accepted_rows,
    pr.rejected_rows,
    qr.quality_result_id,
    qr.rule_name,
    qr.rule_type,
    qr.status AS rule_status,
    qr.failed_rows,
    qr.failure_percentage,
    qr.details_json,
    qr.evaluated_at
FROM client c
JOIN project p
    ON p.client_id = c.client_id
JOIN data_source ds
    ON ds.project_id = p.project_id
JOIN dataset d
    ON d.source_id = ds.source_id
JOIN dataset_version dv
    ON dv.dataset_id = d.dataset_id
JOIN pipeline_run pr
    ON pr.dataset_version_id = dv.dataset_version_id
JOIN quality_result qr
    ON qr.run_id = pr.run_id;