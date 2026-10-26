-- DataForge Sprint 2 (#24): orchestration run state.
--
-- One orchestration_run per pipeline execution (an Airflow DAG run or a
-- standalone CLI run) and one orchestration_task_run per stage/target attempt.
-- Each stage still records its own pipeline_run; task runs link to it so a
-- DAG run can be traced to the control-plane runs it produced.
--
-- Profiling results are intentionally NOT stored here (summary_json stays
-- NULL for the profiling stage): profiling persistence is owned by #21.

CREATE TABLE IF NOT EXISTS orchestration_run (
    orchestration_run_id BIGSERIAL PRIMARY KEY,
    orchestrator VARCHAR(30) NOT NULL,
    external_run_id VARCHAR(250) NOT NULL,
    contract_path TEXT NOT NULL,
    client_code VARCHAR(80) NOT NULL,
    project_code VARCHAR(80) NOT NULL,
    parameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    CONSTRAINT uq_orchestration_run_external UNIQUE (orchestrator, external_run_id),
    CONSTRAINT ck_orchestration_run_orchestrator CHECK (orchestrator IN ('airflow', 'cli')),
    CONSTRAINT ck_orchestration_run_status CHECK (status IN ('running', 'success', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_orchestration_run_status_started_at
    ON orchestration_run(status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_orchestration_run_client_project
    ON orchestration_run(client_code, project_code, started_at DESC);


CREATE TABLE IF NOT EXISTS orchestration_task_run (
    task_run_id BIGSERIAL PRIMARY KEY,
    orchestration_run_id BIGINT NOT NULL
        REFERENCES orchestration_run(orchestration_run_id)
        ON DELETE CASCADE,
    stage VARCHAR(30) NOT NULL,
    target VARCHAR(100) NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(30) NOT NULL DEFAULT 'running',
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(run_id)
        ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    summary_json JSONB,
    CONSTRAINT uq_orchestration_task_attempt UNIQUE (orchestration_run_id, stage, target, attempt),
    CONSTRAINT ck_orchestration_task_stage CHECK (
        stage IN ('bronze', 'profiling', 'silver', 'gold', 'certification')
    ),
    CONSTRAINT ck_orchestration_task_status CHECK (status IN ('running', 'success', 'failed')),
    CONSTRAINT ck_orchestration_task_attempt CHECK (attempt >= 1)
);

CREATE INDEX IF NOT EXISTS idx_orchestration_task_run_run
    ON orchestration_task_run(orchestration_run_id, stage, target);

CREATE INDEX IF NOT EXISTS idx_orchestration_task_run_pipeline_run
    ON orchestration_task_run(pipeline_run_id);


-- Latest attempt of every stage/target in each orchestration run.
CREATE OR REPLACE VIEW orchestration_task_latest AS
SELECT DISTINCT ON (otr.orchestration_run_id, otr.stage, otr.target)
    otr.orchestration_run_id,
    otr.stage,
    otr.target,
    otr.attempt,
    otr.status,
    otr.pipeline_run_id,
    otr.started_at,
    otr.finished_at,
    otr.error_message
FROM orchestration_task_run otr
ORDER BY otr.orchestration_run_id, otr.stage, otr.target, otr.attempt DESC;


CREATE OR REPLACE VIEW orchestration_run_summary AS
SELECT
    o.orchestration_run_id,
    o.orchestrator,
    o.external_run_id,
    o.contract_path,
    o.client_code,
    o.project_code,
    o.status,
    o.started_at,
    o.finished_at,
    ROUND(EXTRACT(EPOCH FROM (o.finished_at - o.started_at))::numeric, 3) AS duration_seconds,
    COUNT(l.stage) AS task_count,
    COUNT(l.stage) FILTER (WHERE l.status = 'success') AS successful_tasks,
    COUNT(l.stage) FILTER (WHERE l.status = 'failed') AS failed_tasks,
    COALESCE(SUM(l.attempt - 1), 0) AS retried_attempts,
    o.error_message
FROM orchestration_run o
LEFT JOIN orchestration_task_latest l
    ON l.orchestration_run_id = o.orchestration_run_id
GROUP BY o.orchestration_run_id;
