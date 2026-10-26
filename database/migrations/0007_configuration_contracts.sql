-- DataForge Sprint 2 (#25): persisted executable configuration contracts.
--
-- PostgreSQL is the authoritative control-plane store for configuration.
-- A contract persisted here has already passed DataForgeContract validation.
-- Secrets are never stored in contract_json; source credentials remain behind
-- connection_reference and DATAFORGE_CONNECTION_* environment variables.

CREATE TABLE IF NOT EXISTS configuration_contract (
    contract_id BIGSERIAL PRIMARY KEY,

    source_id BIGINT NOT NULL
        REFERENCES data_source(source_id)
        ON DELETE CASCADE,

    contract_version VARCHAR(20) NOT NULL,

    revision INTEGER NOT NULL,

    contract_hash VARCHAR(64) NOT NULL,

    contract_json JSONB NOT NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'active',

    created_by VARCHAR(160) NOT NULL
        DEFAULT 'api',

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    activated_at TIMESTAMPTZ,

    archived_at TIMESTAMPTZ,

    CONSTRAINT ck_configuration_contract_revision
        CHECK (revision >= 1),

    CONSTRAINT ck_configuration_contract_json_object
        CHECK (jsonb_typeof(contract_json) = 'object'),

    CONSTRAINT ck_configuration_contract_status
        CHECK (
            status IN (
                'active',
                'archived'
            )
        ),

    CONSTRAINT uq_configuration_contract_revision
        UNIQUE (
            source_id,
            revision
        ),

    CONSTRAINT uq_configuration_contract_hash
        UNIQUE (
            source_id,
            contract_hash
        )
);


CREATE UNIQUE INDEX IF NOT EXISTS uq_configuration_contract_active_source
    ON configuration_contract(source_id)
    WHERE status = 'active';


CREATE INDEX IF NOT EXISTS idx_configuration_contract_source_created
    ON configuration_contract(
        source_id,
        created_at DESC
    );


CREATE OR REPLACE VIEW active_configuration_contract AS
SELECT
    cc.contract_id,
    cc.source_id,
    cc.contract_version,
    cc.revision,
    cc.contract_hash,
    cc.contract_json,
    cc.created_by,
    cc.created_at,
    cc.activated_at,

    ds.source_code,
    ds.source_type,
    ds.source_name,
    ds.connection_reference,

    p.project_id,
    p.project_code,
    p.project_name,

    c.client_id,
    c.client_code,
    c.client_name

FROM configuration_contract cc

JOIN data_source ds
    ON ds.source_id = cc.source_id

JOIN project p
    ON p.project_id = ds.project_id

JOIN client c
    ON c.client_id = p.client_id

WHERE cc.status = 'active';
