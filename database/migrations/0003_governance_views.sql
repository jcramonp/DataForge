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

CREATE OR REPLACE VIEW asset_lineage_edges AS
SELECT
    al.lineage_id,
    al.relation_type,

    parent.asset_id AS parent_asset_id,
    parent.layer AS parent_layer,
    parent.asset_name AS parent_asset_name,
    parent.storage_uri AS parent_storage_uri,

    parent_dataset.dataset_code AS parent_dataset_code,
    parent_version.version_label AS parent_version_label,

    child.asset_id AS child_asset_id,
    child.layer AS child_layer,
    child.asset_name AS child_asset_name,
    child.storage_uri AS child_storage_uri,

    child_dataset.dataset_code AS child_dataset_code,
    child_version.version_label AS child_version_label,

    al.created_by_run_id,
    al.metadata_json,
    al.created_at
FROM asset_lineage al

JOIN data_asset parent
    ON parent.asset_id = al.parent_asset_id

JOIN pipeline_run parent_run
    ON parent_run.run_id = parent.run_id

JOIN dataset_version parent_version
    ON parent_version.dataset_version_id =
       parent_run.dataset_version_id

JOIN dataset parent_dataset
    ON parent_dataset.dataset_id =
       parent_version.dataset_id

JOIN data_asset child
    ON child.asset_id = al.child_asset_id

JOIN pipeline_run child_run
    ON child_run.run_id = child.run_id

JOIN dataset_version child_version
    ON child_version.dataset_version_id =
       child_run.dataset_version_id

JOIN dataset child_dataset
    ON child_dataset.dataset_id =
       child_version.dataset_id;

CREATE OR REPLACE VIEW dataset_certification_summary AS
SELECT
    c.client_code,
    p.project_code,
    ds.source_code,

    d.dataset_id,
    d.dataset_code,
    d.dataset_name,
    d.owner_name,
    d.classification,

    dv.dataset_version_id,
    dv.version_label,
    dv.schema_hash,
    dv.source_checksum,
    dv.discovered_at,

    dc.certification_id,
    dc.state AS certification_state,
    dc.criteria_json,
    dc.last_evaluated_at,
    dc.validated_at,
    dc.certified_at,
    dc.created_at AS certification_created_at,
    dc.updated_at AS certification_updated_at

FROM dataset_certification dc

JOIN dataset_version dv
    ON dv.dataset_version_id =
       dc.dataset_version_id

JOIN dataset d
    ON d.dataset_id = dv.dataset_id

JOIN data_source ds
    ON ds.source_id = d.source_id

JOIN project p
    ON p.project_id = ds.project_id

JOIN client c
    ON c.client_id = p.client_id;