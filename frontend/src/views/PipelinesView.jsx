import React, {
  useEffect,
  useState,
} from 'react';

import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  Play,
  RefreshCw,
  ServerCog,
  XCircle,
} from 'lucide-react';

import { matchesSource } from '../services/scope';
import { isTerminalRun, monitorPipeline } from '../services/pipeline-monitor';

import {
  fetchPipelineRun,
  fetchRuns,
  fetchSources,
  triggerPipeline,
} from '../services/api';


function statusClass(status) {
  if (status === 'success') {
    return 'badge-positive';
  }

  if (status === 'failed') {
    return 'badge-negative';
  }

  return 'badge-warning';
}


function statusIcon(status) {
  if (status === 'success') {
    return <CheckCircle2 size={11} />;
  }

  if (status === 'failed') {
    return <XCircle size={11} />;
  }

  return <Clock size={11} />;
}


function sourceCode(source) {
  return (
    source.source_code
    || source.code
    || `source-${source.source_id}`
  );
}


function sourceName(source) {
  return (
    source.source_name
    || source.name
    || sourceCode(source)
  );
}


export default function PipelinesView({
  scope = {},
  onRefresh,
}) {
  const [sources, setSources] = useState([]);
  const [runs, setRuns] = useState([]);

  const [
    selectedContractId,
    setSelectedContractId,
  ] = useState('');

  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const [liveRun, setLiveRun] = useState(null);
  const [triggerResult, setTriggerResult] = useState(null);

  const [error, setError] = useState(null);
  const [monitorWarning, setMonitorWarning] = useState('');


  const loadControlPlane = async () => {
    const [sourceRows, runRows] = await Promise.all([
      fetchSources(scope),
      fetchRuns(50, scope),
    ]);

    const executableSources = sourceRows.filter(
      (source) => source.contract_id && matchesSource(source, scope),
    );

    setSources(executableSources);
    setRuns(runRows);

    setSelectedContractId((current) => {
      if (
        current
        && executableSources.some(
          (source) =>
            String(source.contract_id) === current,
        )
      ) {
        return current;
      }

      if (executableSources.length > 0) {
        return String(
          executableSources[0].contract_id,
        );
      }

      return '';
    });
  };


  useEffect(() => {
    let cancelled = false;

    async function initialLoad() {
      setLoading(true);
      setError(null);

      try {
        const [sourceRows, runRows] =
          await Promise.all([
            fetchSources(scope),
            fetchRuns(50, scope),
          ]);

        if (cancelled) {
          return;
        }

        const executableSources = sourceRows.filter(
          (source) => source.contract_id && matchesSource(source, scope),
        );

        setSources(executableSources);
        setRuns(runRows);

        if (executableSources.length > 0) {
          setSelectedContractId(
            String(executableSources[0].contract_id),
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    initialLoad();

    return () => {
      cancelled = true;
    };
  }, []);


  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);

    try {
      if (triggerResult?.external_run_id) {
        const status = await fetchPipelineRun(triggerResult.external_run_id);
        setLiveRun(status);
        setMonitorWarning(isTerminalRun(status) ? '' : 'Execution is still active. Use Refresh to check its status.');
      }
      await loadControlPlane();
    } catch (err) {
      setError(triggerResult
        ? `Could not refresh the accepted run. Its outcome is unknown; use Refresh again. ${err.message}`
        : err.message);
    } finally {
      setRefreshing(false);
    }
  };


  const pollRun = (externalRunId) => monitorPipeline(externalRunId, {
    fetchStatus: fetchPipelineRun,
    onStatus: setLiveRun,
    onWarning: setMonitorWarning,
  });


  const handleTrigger = async () => {
    if (triggering || (triggerResult && !isTerminalRun(liveRun))) return;
    if (!selectedContractId) {
      setError(
        'No active persisted contract is available.',
      );
      return;
    }

    setTriggering(true);
    setError(null);
    setTriggerResult(null);
    setLiveRun(null);
    setMonitorWarning('');

    let acceptedRun;
    try {
      const accepted = await triggerPipeline({
        contract_id: Number(selectedContractId),

        // Empty selections mean execute the complete
        // persisted configuration contract.
        datasets: [],
        gold: [],
        stages: [],

        certification: 'evaluate',
      });

      setTriggerResult(accepted);
      acceptedRun = accepted;

      const finalRun = await pollRun(
        accepted.external_run_id,
      );

      await loadControlPlane();

      if (onRefresh) {
        onRefresh();
      }

      if (finalRun?.state === 'failed') {
        setError(
          `Airflow run ${accepted.external_run_id} failed.`,
        );
      }
    } catch (err) {
      setError(acceptedRun
        ? `Pipeline ${acceptedRun.external_run_id} was accepted. Monitoring or history could not be updated; use Refresh before starting another run. ${err.message}`
        : err.message);
    } finally {
      setTriggering(false);
    }
  };


  const selectedSource = sources.find(
    (source) =>
      String(source.contract_id)
      === selectedContractId,
  );


  if (loading) {
    return (
      <div className="card">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Loader2 size={16} className="spin" />
          Loading orchestration control plane...
        </div>
      </div>
    );
  }


  return (
    <div>
      <div
        className="card"
        style={{ marginBottom: '24px' }}
      >
        <h3 className="card-title">
          Trigger Persisted Pipeline
        </h3>

        <p className="card-subtitle">
          Execute the generic DataForge Airflow DAG from a
          configuration contract persisted in PostgreSQL.
        </p>


        {error && (
          <div
            style={{
              marginBottom: '16px',
              padding: '10px 12px',
              borderRadius: '5px',
              background: 'var(--negative-bg)',
              color: 'var(--negative)',
              border:
                '1px solid var(--negative-border)',
              display: 'flex',
              alignItems: 'center',
              gap: '7px',
              fontSize: '12px',
            }}
          >
            <AlertCircle size={14} />
            {error}
          </div>
        )}

        {monitorWarning && <p role="status">{monitorWarning}</p>}


        <div
          style={{
            display: 'flex',
            gap: '16px',
            alignItems: 'flex-end',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ minWidth: '330px' }}>
            <label
              style={{
                display: 'block',
                fontSize: '11px',
                fontWeight: 600,
                color: 'var(--muted)',
                marginBottom: '4px',
              }}
            >
              Active Configuration Contract
            </label>

            <select
              value={selectedContractId}
              onChange={(event) => {
                setSelectedContractId(
                  event.target.value,
                );
                setTriggerResult(null);
                setLiveRun(null);
                setError(null);
                setMonitorWarning('');
              }}
              disabled={triggering}
              style={{
                width: '100%',
                padding: '7px 10px',
                borderRadius: '4px',
                border: '1px solid #d1d5db',
                background: '#fff',
              }}
            >
              {sources.length === 0 && (
                <option value="">
                  No persisted contracts available
                </option>
              )}

              {sources.map((source) => (
                <option
                  key={source.source_id}
                  value={source.contract_id}
                >
                  {source.client_code}
                  {' / '}
                  {source.project_code}
                  {' / '}
                  {sourceCode(source)}
                  {' '}
                  ? contract #{source.contract_id}
                  {' '}
                  rev {source.contract_revision
                    || source.revision
                    || '?'}
                </option>
              ))}
            </select>
          </div>


          <button
            className="btn btn-primary"
            onClick={handleTrigger}
            disabled={
              triggering
              || !selectedContractId
              || (triggerResult && !isTerminalRun(liveRun))
            }
          >
            {triggering
              ? (
                <Loader2
                  size={14}
                  className="spin"
                />
              )
              : <Play size={14} />}

            {triggering
              ? 'Pipeline Running...'
              : 'Run Full Pipeline'}
          </button>


          <button
            className="btn btn-secondary"
            onClick={handleRefresh}
            disabled={refreshing || triggering}
          >
            <RefreshCw
              size={14}
              className={
                refreshing ? 'spin' : undefined
              }
            />

            Refresh
          </button>
        </div>


        {selectedSource && (
          <div
            style={{
              marginTop: '14px',
              padding: '10px 12px',
              background: 'var(--surface-raised)',
              border:
                '1px solid var(--border)',
              borderRadius: '5px',
              fontSize: '12px',
            }}
          >
            <strong>{sourceName(selectedSource)}</strong>

            <span
              style={{
                color: 'var(--muted)',
                marginLeft: '8px',
              }}
            >
              source={sourceCode(selectedSource)}
              {' ? '}
              contract_id=
              {selectedSource.contract_id}
              {' ? '}
              revision=
              {selectedSource.contract_revision
                || selectedSource.revision
                || '?'}
            </span>
          </div>
        )}


        {triggerResult && (
          <div
            style={{
              marginTop: '16px',
              padding: '12px 14px',
              borderRadius: '5px',
              border: '1px solid var(--border)',
              background: 'var(--surface-raised)',
              fontSize: '12px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '7px',
                marginBottom: '8px',
              }}
            >
              <ServerCog size={15} />

              <strong>
                Airflow execution accepted
              </strong>
            </div>

            <div className="mono">
              DAG: {triggerResult.dag_id}
            </div>

            <div className="mono">
              Run: {triggerResult.external_run_id}
            </div>

            <div>
              Contract ID: {triggerResult.contract_id}
            </div>

            <div>
              Stages:{' '}
              {(triggerResult.stages || []).join(
                ' ? ',
              )}
            </div>

            <div>
              Gold targets:{' '}
              {(triggerResult.gold || []).join(', ')
                || 'none'}
            </div>

            <div>
              Certification mode:{' '}
              {triggerResult.certification}
            </div>
          </div>
        )}


        {liveRun && (
          <div
            style={{
              marginTop: '16px',
              padding: '12px 14px',
              borderRadius: '5px',
              background:
                liveRun.state === 'success'
                  ? 'var(--positive-bg)'
                  : liveRun.state === 'failed'
                    ? 'var(--negative-bg)'
                    : 'var(--surface-raised)',
              border:
                liveRun.state === 'success'
                  ? '1px solid var(--positive-border)'
                  : liveRun.state === 'failed'
                    ? '1px solid var(--negative-border)'
                    : '1px solid var(--border)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '7px',
                marginBottom: '10px',
              }}
            >
              {statusIcon(liveRun.state)}

              <strong>
                Live Airflow State:{' '}
                {liveRun.state.toUpperCase()}
              </strong>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns:
                  'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '8px',
                fontSize: '12px',
              }}
            >
              {(liveRun.tasks || []).map((task) => (
                <div
                  key={
                    task.task_id
                    || task.id
                    || JSON.stringify(task)
                  }
                  style={{
                    padding: '8px',
                    background: '#fff',
                    borderRadius: '4px',
                    border: '1px solid var(--border)',
                  }}
                >
                  <div
                    className="mono"
                    style={{ fontWeight: 600 }}
                  >
                    {task.task_id
                      || task.id
                      || 'task'}
                  </div>

                  <div
                    style={{
                      color: 'var(--muted)',
                      marginTop: '3px',
                    }}
                  >
                    {task.state || 'unknown'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>


      <div className="card">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h3 className="card-title">
              Durable Orchestration History
            </h3>

            <p className="card-subtitle">
              Runs persisted by the DataForge control plane
              independently of the browser session.
            </p>
          </div>

          <span className="badge badge-neutral">
            {runs.length} runs
          </span>
        </div>


        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run</th>
                <th>Client / Project</th>
                <th>Status</th>
                <th>Tasks</th>
                <th>Success</th>
                <th>Failed</th>
                <th>Retries</th>
                <th>Duration</th>
                <th>Started</th>
              </tr>
            </thead>

            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.orchestration_run_id}
                >
                  <td>
                    <div className="mono">
                      #{run.orchestration_run_id}
                    </div>

                    <div
                      className="mono"
                      style={{
                        fontSize: '10px',
                        color: 'var(--muted)',
                      }}
                    >
                      {run.external_run_id}
                    </div>
                  </td>

                  <td>
                    <strong>
                      {run.client_code}
                    </strong>

                    <div
                      style={{
                        fontSize: '11px',
                        color: 'var(--muted)',
                      }}
                    >
                      {run.project_code}
                    </div>
                  </td>

                  <td>
                    <span
                      className={
                        `badge ${statusClass(run.status)}`
                      }
                    >
                      {statusIcon(run.status)}
                      {run.status}
                    </span>
                  </td>

                  <td className="tabular-nums">
                    {run.task_count}
                  </td>

                  <td
                    className="tabular-nums"
                    style={{
                      color: 'var(--positive)',
                    }}
                  >
                    {run.successful_tasks}
                  </td>

                  <td className="tabular-nums">
                    {run.failed_tasks}
                  </td>

                  <td className="tabular-nums">
                    {run.retried_attempts}
                  </td>

                  <td className="tabular-nums">
                    {run.duration_seconds === null
                      || run.duration_seconds === undefined
                      ? '?'
                      : `${Number(
                        run.duration_seconds,
                      ).toFixed(2)}s`}
                  </td>

                  <td
                    style={{
                      color: 'var(--muted)',
                      fontSize: '11px',
                    }}
                  >
                    {new Date(
                      run.started_at,
                    ).toLocaleString()}
                  </td>
                </tr>
              ))}

              {runs.length === 0 && (
                <tr>
                  <td
                    colSpan={9}
                    style={{
                      textAlign: 'center',
                      color: 'var(--muted)',
                    }}
                  >
                    No orchestration runs persisted yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
