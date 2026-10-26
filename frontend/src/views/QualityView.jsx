import React, {
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';

import {
  fetchDatasets,
  fetchQualityRules,
  fetchQuarantine,
} from '../services/api';


function datasetKey(dataset) {
  return [
    dataset.client,
    dataset.project,
    dataset.source_code,
    dataset.code,
  ].join('::');
}


function datasetScope(dataset) {
  return {
    client_code: dataset.client,
    project_code: dataset.project,
    source_code: dataset.source_code,
  };
}


function formatObservedValue(value) {
  if (value === null) {
    return 'null';
  }

  if (value === undefined) {
    return '?';
  }

  if (typeof value === 'object') {
    return JSON.stringify(value);
  }

  return String(value);
}


function statusBadge(rule) {
  const isFail = rule.status === 'fail';
  const isCritical = rule.severity === 'critical';

  if (!isFail) {
    return (
      <span className="badge badge-positive">
        <CheckCircle2 size={11} />
        PASS
      </span>
    );
  }

  return (
    <span
      className={
        `badge ${
          isCritical
            ? 'badge-negative'
            : 'badge-warning'
        }`
      }
    >
      {isCritical
        ? <ShieldAlert size={11} />
        : <AlertTriangle size={11} />}
      FAIL
    </span>
  );
}


export default function QualityView({ scope = {} }) {
  const [datasets, setDatasets] = useState([]);
  const [
    selectedDatasetKey,
    setSelectedDatasetKey,
  ] = useState('');

  const [rules, setRules] = useState([]);
  const [quarantine, setQuarantine] = useState([]);

  const [loadingDatasets, setLoadingDatasets] =
    useState(true);

  const [loadingQuality, setLoadingQuality] =
    useState(false);

  const [error, setError] = useState(null);


  const qualityDatasets = useMemo(
    () => datasets.filter(
      (dataset) =>
        dataset.rules_count > 0
        || dataset.layers?.quarantine,
    ),
    [datasets],
  );


  const selectedDataset = useMemo(
    () => qualityDatasets.find(
      (dataset) =>
        datasetKey(dataset)
        === selectedDatasetKey,
    ) || null,
    [
      qualityDatasets,
      selectedDatasetKey,
    ],
  );


  async function loadDatasets() {
    setLoadingDatasets(true);
    setError(null);

    try {
      const rows = await fetchDatasets(scope);

      setDatasets(rows);

      const eligible = rows.filter(
        (dataset) =>
          dataset.rules_count > 0
          || dataset.layers?.quarantine,
      );

      setSelectedDatasetKey((current) => {
        if (
          current
          && eligible.some(
            (dataset) =>
              datasetKey(dataset) === current,
          )
        ) {
          return current;
        }

        if (eligible.length > 0) {
          return datasetKey(eligible[0]);
        }

        return '';
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingDatasets(false);
    }
  }


  async function loadQuality(dataset) {
    if (!dataset) {
      setRules([]);
      setQuarantine([]);
      return;
    }

    setLoadingQuality(true);
    setError(null);

    try {
      const scope = datasetScope(dataset);

      const [ruleRows, quarantineRows] =
        await Promise.all([
          fetchQualityRules(
            dataset.code,
            scope,
          ),
          fetchQuarantine(
            dataset.code,
            scope,
          ),
        ]);

      setRules(ruleRows);
      setQuarantine(quarantineRows);
    } catch (err) {
      setRules([]);
      setQuarantine([]);
      setError(err.message);
    } finally {
      setLoadingQuality(false);
    }
  }


  useEffect(() => {
    loadDatasets();
  }, []);


  useEffect(() => {
    if (selectedDataset) {
      loadQuality(selectedDataset);
    }
  }, [selectedDatasetKey]);


  const failedCritical = rules.filter(
    (rule) =>
      rule.status === 'fail'
      && rule.severity === 'critical',
  ).length;

  const failedWarnings = rules.filter(
    (rule) =>
      rule.status === 'fail'
      && rule.severity === 'warning',
  ).length;

  const passedRules = rules.filter(
    (rule) => rule.status === 'pass',
  ).length;


  if (loadingDatasets) {
    return (
      <div className="card">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Loader2
            size={16}
            className="spin"
          />
          Loading quality metadata...
        </div>
      </div>
    );
  }


  return (
    <div>
      <div
        className="card"
        style={{ marginBottom: '20px' }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ minWidth: '360px' }}>
            <label
              style={{
                display: 'block',
                fontSize: '11px',
                fontWeight: 600,
                color: 'var(--muted)',
                marginBottom: '4px',
              }}
            >
              Dataset Quality Scope
            </label>

            <select
              value={selectedDatasetKey}
              onChange={(event) =>
                setSelectedDatasetKey(
                  event.target.value,
                )}
              style={{
                width: '100%',
                padding: '7px 10px',
                borderRadius: '4px',
                border: '1px solid #d1d5db',
                background: '#fff',
              }}
            >
              {qualityDatasets.length === 0 && (
                <option value="">
                  No datasets with quality evidence
                </option>
              )}

              {qualityDatasets.map(
                (dataset) => (
                  <option
                    key={datasetKey(dataset)}
                    value={datasetKey(dataset)}
                  >
                    {dataset.client}
                    {' / '}
                    {dataset.project}
                    {' / '}
                    {dataset.source_code}
                    {' / '}
                    {dataset.code}
                  </option>
                ),
              )}
            </select>
          </div>

          <button
            className="btn btn-secondary"
            disabled={
              loadingQuality
              || !selectedDataset
            }
            onClick={() =>
              loadQuality(selectedDataset)
            }
          >
            <RefreshCw
              size={14}
              className={
                loadingQuality
                  ? 'spin'
                  : undefined
              }
            />

            Refresh
          </button>
        </div>

        {selectedDataset && (
          <div
            style={{
              marginTop: '12px',
              color: 'var(--muted)',
              fontSize: '12px',
            }}
          >
            <strong
              style={{
                color: 'var(--accent)',
              }}
            >
              {selectedDataset.name}
            </strong>

            {' ? '}
            owner={selectedDataset.owner || '?'}

            {' ? '}
            rules={selectedDataset.rules_count}

            {' ? '}
            certification=
            {selectedDataset.certification_status}
          </div>
        )}
      </div>


      {error && (
        <div
          style={{
            marginBottom: '20px',
            padding: '10px 12px',
            borderRadius: '5px',
            background: 'var(--negative-bg)',
            border:
              '1px solid var(--negative-border)',
            color: 'var(--negative)',
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


      <div
        style={{
          display: 'grid',
          gridTemplateColumns:
            'repeat(4, minmax(0, 1fr))',
          gap: '12px',
          marginBottom: '20px',
        }}
      >
        <div className="card">
          <div
            style={{
              fontSize: '11px',
              color: 'var(--muted)',
            }}
          >
            Evaluated Rules
          </div>

          <div
            style={{
              fontSize: '22px',
              fontWeight: 600,
              marginTop: '4px',
            }}
          >
            {rules.length}
          </div>
        </div>


        <div className="card">
          <div
            style={{
              fontSize: '11px',
              color: 'var(--muted)',
            }}
          >
            Passed
          </div>

          <div
            style={{
              fontSize: '22px',
              fontWeight: 600,
              color: 'var(--positive)',
              marginTop: '4px',
            }}
          >
            {passedRules}
          </div>
        </div>


        <div className="card">
          <div
            style={{
              fontSize: '11px',
              color: 'var(--muted)',
            }}
          >
            Critical Failures
          </div>

          <div
            style={{
              fontSize: '22px',
              fontWeight: 600,
              color: failedCritical > 0
                ? 'var(--negative)'
                : 'var(--positive)',
              marginTop: '4px',
            }}
          >
            {failedCritical}
          </div>
        </div>


        <div className="card">
          <div
            style={{
              fontSize: '11px',
              color: 'var(--muted)',
            }}
          >
            Warning Failures
          </div>

          <div
            style={{
              fontSize: '22px',
              fontWeight: 600,
              color: failedWarnings > 0
                ? 'var(--warning)'
                : 'var(--positive)',
              marginTop: '4px',
            }}
          >
            {failedWarnings}
          </div>
        </div>
      </div>


      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '16px',
          marginBottom: '20px',
        }}
      >
        <div
          style={{
            background: 'var(--positive-bg)',
            border:
              '1px solid var(--positive-border)',
            borderRadius: 'var(--radius-md)',
            padding: '12px 16px',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 600,
              color: 'var(--positive)',
            }}
          >
            <ShieldCheck size={16} />
            Validated Silver Partition
          </div>

          <p
            style={{
              color: '#166534',
              marginTop: '4px',
              fontSize: '12px',
            }}
          >
            Rows passing every critical rule remain
            available in Validated Silver.
          </p>
        </div>


        <div
          style={{
            background: 'var(--negative-bg)',
            border:
              '1px solid var(--negative-border)',
            borderRadius: 'var(--radius-md)',
            padding: '12px 16px',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 600,
              color: 'var(--negative)',
            }}
          >
            <ShieldAlert size={16} />
            Critical Quarantine
          </div>

          <p
            style={{
              color: '#991b1b',
              marginTop: '4px',
              fontSize: '12px',
            }}
          >
            Critical rule violations are isolated in
            Quarantine rather than silently accepted.
          </p>
        </div>
      </div>


      <div
        className="card"
        style={{ marginBottom: '24px' }}
      >
        <h3 className="card-title">
          Persisted Quality Evaluation
          {selectedDataset
            ? ` ? ${selectedDataset.code}`
            : ''}
        </h3>

        <p className="card-subtitle">
          Results come from PostgreSQL
          <code> quality_result </code>
          metadata produced by the latest successful
          Silver quality gate.
        </p>


        {loadingQuality ? (
          <div
            style={{
              padding: '24px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <Loader2
              size={16}
              className="spin"
            />
            Loading persisted quality results...
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Type</th>
                  <th>Column</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Failed Rows</th>
                  <th>Failure %</th>
                  <th>Run</th>
                  <th>Evaluated</th>
                </tr>
              </thead>

              <tbody>
                {rules.map((rule) => (
                  <tr
                    key={rule.quality_result_id}
                  >
                    <td>
                      <strong
                        className="mono"
                        style={{ fontSize: '12px' }}
                      >
                        {rule.name}
                      </strong>
                    </td>

                    <td>
                      <span
                        className="badge badge-neutral mono"
                      >
                        {rule.rule_type}
                      </span>
                    </td>

                    <td className="mono">
                      {rule.column || '?'}
                    </td>

                    <td>
                      <span
                        className={
                          `badge ${
                            rule.severity === 'critical'
                              ? 'badge-negative'
                              : 'badge-warning'
                          }`
                        }
                      >
                        {rule.severity}
                      </span>
                    </td>

                    <td>
                      {statusBadge(rule)}
                    </td>

                    <td className="tabular-nums">
                      {Number(
                        rule.failed_rows || 0,
                      ).toLocaleString()}
                    </td>

                    <td className="tabular-nums">
                      {rule.failure_percentage === null
                        || rule.failure_percentage
                          === undefined
                        ? '?'
                        : `${Number(
                          rule.failure_percentage,
                        ).toFixed(4)}%`}
                    </td>

                    <td className="mono">
                      #{rule.run_id}
                    </td>

                    <td
                      style={{
                        color: 'var(--muted)',
                        fontSize: '11px',
                      }}
                    >
                      {rule.evaluated_at
                        ? new Date(
                          rule.evaluated_at,
                        ).toLocaleString()
                        : '?'}
                    </td>
                  </tr>
                ))}

                {rules.length === 0 && (
                  <tr>
                    <td
                      colSpan={9}
                      style={{
                        textAlign: 'center',
                        color: 'var(--muted)',
                      }}
                    >
                      No persisted quality evaluation
                      exists for this dataset yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>


      <div className="card">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '14px',
          }}
        >
          <div>
            <h3
              className="card-title"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <ShieldAlert
                size={18}
                color="var(--negative)"
              />

              Quarantine Inspector
              {' '}
              ({quarantine.length} records)
            </h3>

            <p className="card-subtitle">
              Critical records reconstructed from the
              latest persisted Quarantine asset.
            </p>
          </div>
        </div>


        {quarantine.length > 0 ? (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Quarantine ID</th>
                  <th>Record ID</th>
                  <th>Failed Rule</th>
                  <th>Type</th>
                  <th>Field</th>
                  <th>Observed</th>
                  <th>Severity</th>
                  <th>Run / Asset</th>
                  <th>Quarantined</th>
                </tr>
              </thead>

              <tbody>
                {quarantine.map((record) => (
                  <tr key={record.quarantine_id}>
                    <td
                      className="mono"
                      style={{
                        color: 'var(--muted)',
                        fontSize: '11px',
                      }}
                    >
                      {record.quarantine_id}
                    </td>

                    <td className="mono">
                      <strong>
                        {record.record_id}
                      </strong>
                    </td>

                    <td
                      className="mono"
                      style={{ fontSize: '12px' }}
                    >
                      {record.rule_violated}
                    </td>

                    <td>
                      <span
                        className="badge badge-neutral mono"
                      >
                        {record.rule_type}
                      </span>
                    </td>

                    <td className="mono">
                      {record.failed_field}
                    </td>

                    <td>
                      <span
                        className="badge badge-negative mono"
                      >
                        {formatObservedValue(
                          record.observed_value,
                        )}
                      </span>
                    </td>

                    <td>
                      <span className="badge badge-negative">
                        {record.severity}
                      </span>
                    </td>

                    <td
                      className="mono"
                      style={{ fontSize: '11px' }}
                    >
                      run #{record.run_id}
                      <br />
                      asset #{record.asset_id}
                    </td>

                    <td
                      style={{
                        color: 'var(--muted)',
                        fontSize: '11px',
                      }}
                    >
                      {record.quarantined_at
                        ? new Date(
                          record.quarantined_at,
                        ).toLocaleString()
                        : '?'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div
            style={{
              padding: '32px',
              textAlign: 'center',
              color: 'var(--muted)',
              background: 'var(--surface-raised)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <CheckCircle2
              size={28}
              color="var(--positive)"
              style={{
                marginBottom: '8px',
              }}
            />

            <div
              style={{
                fontWeight: 600,
                color: 'var(--accent)',
              }}
            >
              No Quarantined Records
            </div>

            <div
              style={{
                fontSize: '12px',
                marginTop: '4px',
              }}
            >
              The latest successful quality gate has no
              critical rejected rows for this dataset.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
