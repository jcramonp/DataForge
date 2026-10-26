import React, {
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  AlertCircle,
  ArrowRight,
  Award,
  CheckCircle2,
  GitFork,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';

import {
  fetchCertification,
  fetchLineage,
  updateCertification,
} from '../services/api';


function targetKey(item) {
  return [
    item.client_code,
    item.project_code,
    item.source_code,
    item.dataset_code,
  ].join('::');
}


function targetFilters(item) {
  return {
    client_code: item.client_code,
    project_code: item.project_code,
    source_code: item.source_code,
    dataset_code: item.dataset_code,
  };
}


function nextState(status) {
  if (status === 'draft') {
    return 'validated';
  }

  if (status === 'validated') {
    return 'certified';
  }

  return null;
}


function layerStyle(layer) {
  if (layer === 'bronze') {
    return {
      background: '#fffbeb',
      border: '#fde68a',
      color: '#92400e',
    };
  }

  if (layer === 'silver') {
    return {
      background: 'var(--positive-bg)',
      border: 'var(--positive-border)',
      color: 'var(--positive)',
    };
  }

  if (layer === 'quarantine') {
    return {
      background: 'var(--negative-bg)',
      border: 'var(--negative-border)',
      color: 'var(--negative)',
    };
  }

  return {
    background: '#eff6ff',
    border: '#bfdbfe',
    color: '#1d4ed8',
  };
}


function stateBadge(status) {
  if (status === 'certified') {
    return 'badge-positive';
  }

  if (status === 'validated') {
    return 'badge-warning';
  }

  return 'badge-neutral';
}


export default function LineageView({ scope = {} }) {
  const [certifications, setCertifications] =
    useState([]);

  const [
    selectedTargetKey,
    setSelectedTargetKey,
  ] = useState('');

  const [lineage, setLineage] = useState({
    nodes: [],
    links: [],
  });

  const [loading, setLoading] = useState(true);
  const [loadingLineage, setLoadingLineage] =
    useState(false);

  const [updating, setUpdating] = useState(null);
  const [error, setError] = useState(null);


  const selectedTarget = useMemo(
    () => certifications.find(
      (item) =>
        targetKey(item)
        === selectedTargetKey,
    ) || null,
    [
      certifications,
      selectedTargetKey,
    ],
  );


  async function loadCertifications() {
    const rows = await fetchCertification(scope);

    setCertifications(rows);

    setSelectedTargetKey((current) => {
      if (
        current
        && rows.some(
          (item) => targetKey(item) === current,
        )
      ) {
        return current;
      }

      if (rows.length > 0) {
        return targetKey(rows[0]);
      }

      return '';
    });

    return rows;
  }


  async function loadLineage(target) {
    if (!target) {
      setLineage({
        nodes: [],
        links: [],
      });

      return;
    }

    setLoadingLineage(true);
    setError(null);

    try {
      const graph = await fetchLineage(
        targetFilters(target),
      );

      setLineage(graph);
    } catch (err) {
      setLineage({
        nodes: [],
        links: [],
      });

      setError(err.message);
    } finally {
      setLoadingLineage(false);
    }
  }


  useEffect(() => {
    let cancelled = false;

    async function initialLoad() {
      setLoading(true);
      setError(null);

      try {
        const rows = await fetchCertification(scope);

        if (cancelled) {
          return;
        }

        setCertifications(rows);

        if (rows.length > 0) {
          setSelectedTargetKey(
            targetKey(rows[0]),
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


  useEffect(() => {
    if (selectedTarget) {
      loadLineage(selectedTarget);
    }
  }, [selectedTargetKey]);


  const handleRefresh = async () => {
    setLoading(true);
    setError(null);

    try {
      const rows = await loadCertifications();

      const current = rows.find(
        (item) =>
          targetKey(item)
          === selectedTargetKey,
      ) || rows[0];

      if (current) {
        await loadLineage(current);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };


  const handlePromote = async (item) => {
    const targetState = nextState(
      item.status,
    );

    if (!targetState) {
      return;
    }

    const key = targetKey(item);

    setUpdating(key);
    setError(null);

    try {
      await updateCertification(
        item.dataset_code,
        targetState,
        {
          certifiedBy: 'frontend',
          notes:
            `Promoted through DataForge web UI: `
            + `${item.status} -> ${targetState}`,
          filters: {
            client_code: item.client_code,
            project_code: item.project_code,
            source_code: item.source_code,
          },
        },
      );

      await loadCertifications();
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdating(null);
    }
  };


  const nodesById = useMemo(
    () => Object.fromEntries(
      lineage.nodes.map(
        (node) => [node.id, node],
      ),
    ),
    [lineage.nodes],
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
          <Loader2
            size={16}
            className="spin"
          />
          Loading governance metadata...
        </div>
      </div>
    );
  }


  return (
    <div>
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
        className="card"
        style={{ marginBottom: '24px' }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <div>
            <h3 className="card-title">
              Persisted Asset Lineage
            </h3>

            <p className="card-subtitle">
              Asset-to-asset relationships stored in the
              DataForge control plane.
            </p>
          </div>

          <div
            style={{
              display: 'flex',
              gap: '8px',
              alignItems: 'flex-end',
            }}
          >
            <div style={{ minWidth: '380px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'var(--muted)',
                  marginBottom: '4px',
                }}
              >
                Lineage Scope
              </label>

              <select
                value={selectedTargetKey}
                onChange={(event) =>
                  setSelectedTargetKey(
                    event.target.value,
                  )}
                style={{
                  width: '100%',
                  padding: '7px 10px',
                  borderRadius: '4px',
                  border:
                    '1px solid #d1d5db',
                  background: '#fff',
                }}
              >
                {certifications.map(
                  (item) => (
                    <option
                      key={targetKey(item)}
                      value={targetKey(item)}
                    >
                      {item.client_code}
                      {' / '}
                      {item.project_code}
                      {' / '}
                      {item.source_code}
                      {' / '}
                      {item.dataset_code}
                    </option>
                  ),
                )}
              </select>
            </div>

            <button
              className="btn btn-secondary"
              onClick={handleRefresh}
            >
              <RefreshCw size={14} />
              Refresh
            </button>
          </div>
        </div>


        {loadingLineage ? (
          <div
            style={{
              padding: '30px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <Loader2
              size={16}
              className="spin"
            />
            Loading lineage graph...
          </div>
        ) : (
          <>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                padding: '20px 0',
                overflowX: 'auto',
              }}
            >
              {lineage.links.map((link) => {
                // Only persisted edges define connectivity; layer order does not.
                const source = nodesById[link.source];
                const target = nodesById[link.target];

                if (!source || !target) {
                  return null;
                }

                const sourceStyle =
                  layerStyle(source.layer);

                const targetStyle =
                  layerStyle(target.layer);

                return (
                  <div
                    key={link.lineage_id}
                    style={{
                      display: 'grid',
                      minWidth: '638px',
                      gridTemplateColumns:
                        'minmax(220px, 1fr) 170px minmax(220px, 1fr)',
                      alignItems: 'center',
                      gap: '14px',
                    }}
                  >
                    <div
                      style={{
                        padding: '12px 14px',
                        background:
                          sourceStyle.background,
                        border:
                          `1px solid ${sourceStyle.border}`,
                        borderRadius: '6px',
                      }}
                    >
                      <div
                        style={{
                          fontSize: '10px',
                          fontWeight: 600,
                          color: 'var(--muted)',
                          textTransform: 'uppercase',
                          marginBottom: '4px',
                        }}
                      >
                        {source.layer}
                      </div>

                      <div
                        style={{
                          fontWeight: 600,
                          color: sourceStyle.color,
                        }}
                      >
                        {source.name}
                      </div>

                      <div
                        className="mono"
                        style={{
                          fontSize: '10px',
                          color: 'var(--muted)',
                          marginTop: '3px',
                        }}
                      >
                        asset #{source.asset_id}
                      </div>
                    </div>

                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '7px',
                      }}
                    >
                      <ArrowRight
                        size={16}
                        color="#9ca3af"
                      />

                      <span className="badge badge-neutral">
                        {link.relation_type}
                      </span>
                    </div>

                    <div
                      style={{
                        padding: '12px 14px',
                        background:
                          targetStyle.background,
                        border:
                          `1px solid ${targetStyle.border}`,
                        borderRadius: '6px',
                      }}
                    >
                      <div
                        style={{
                          fontSize: '10px',
                          fontWeight: 600,
                          color: 'var(--muted)',
                          textTransform: 'uppercase',
                          marginBottom: '4px',
                        }}
                      >
                        {target.layer}
                      </div>

                      <div
                        style={{
                          fontWeight: 600,
                          color: targetStyle.color,
                        }}
                      >
                        {target.name}
                      </div>

                      <div
                        className="mono"
                        style={{
                          fontSize: '10px',
                          color: 'var(--muted)',
                          marginTop: '3px',
                        }}
                      >
                        asset #{target.asset_id}
                      </div>
                    </div>
                  </div>
                );
              })}

              {lineage.links.length === 0 && (
                <div
                  style={{
                    padding: '24px',
                    color: 'var(--muted)',
                    textAlign: 'center',
                  }}
                >
                  No persisted lineage exists for
                  this scope yet.
                </div>
              )}
            </div>


            <div
              style={{
                marginTop: '10px',
                borderTop:
                  '1px solid var(--border)',
                paddingTop: '14px',
              }}
            >
              <h4
                style={{
                  fontSize: '12px',
                  marginBottom: '8px',
                }}
              >
                Persisted Relationships
              </h4>

              {lineage.links.map((link) => (
                <div
                  key={link.lineage_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '12px',
                    marginBottom: '6px',
                  }}
                >
                  <GitFork size={13} />

                  <span className="mono">
                    {link.source}
                  </span>

                  <ArrowRight size={12} />

                  <span className="mono">
                    {link.target}
                  </span>

                  <span className="badge badge-neutral">
                    {link.relation_type}
                  </span>

                  {link.created_by_run_id && (
                    <span
                      style={{
                        color:
                          'var(--muted)',
                      }}
                    >
                      run #
                      {link.created_by_run_id}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>


      <div className="card">
        <h3 className="card-title">
          Dataset Governance & Certification
        </h3>

        <p className="card-subtitle">
          Governance lifecycle is enforced by the backend:
          {' '}
          <code>draft</code>
          {' ? '}
          <code>validated</code>
          {' ? '}
          <code>certified</code>.
        </p>


        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Scope</th>
                <th>Version</th>
                <th>Status</th>
                <th>Criteria</th>
                <th>Ready</th>
                <th>Governance Action</th>
              </tr>
            </thead>

            <tbody>
              {certifications.map((item) => {
                const transition =
                  nextState(item.status);

                const key =
                  targetKey(item);

                const criteria =
                  item.criteria || {};

                return (
                  <tr key={key}>
                    <td>
                      <strong>
                        {item.dataset_name}
                      </strong>

                      <div
                        className="mono"
                        style={{
                          fontSize: '10px',
                          color:
                            'var(--muted)',
                        }}
                      >
                        {item.dataset_code}
                      </div>
                    </td>

                    <td
                      style={{
                        fontSize: '11px',
                      }}
                    >
                      {item.client_code}
                      <br />
                      <span
                        className="mono"
                        style={{
                          color:
                            'var(--muted)',
                        }}
                      >
                        {item.source_code}
                      </span>
                    </td>

                    <td
                      className="mono"
                      style={{
                        fontSize: '11px',
                      }}
                    >
                      #{item.dataset_version_id}
                      <br />
                      {item.version_label}
                    </td>

                    <td>
                      <span
                        className={
                          `badge ${stateBadge(
                            item.status,
                          )}`
                        }
                      >
                        {item.status ===
                        'certified'
                          ? (
                            <Award
                              size={11}
                            />
                          )
                          : (
                            <ShieldCheck
                              size={11}
                            />
                          )}

                        {item.status}
                      </span>
                    </td>

                    <td>
                      <div
                        style={{
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: '4px',
                          maxWidth: '260px',
                        }}
                      >
                        {Object.entries(
                          criteria,
                        ).map(
                          ([name, passed]) => (
                            <span
                              key={name}
                              className={
                                `badge ${
                                  passed
                                    ? 'badge-positive'
                                    : 'badge-negative'
                                }`
                              }
                            >
                              {name}
                            </span>
                          ),
                        )}
                      </div>
                    </td>

                    <td>
                      <div
                        style={{
                          fontSize: '11px',
                        }}
                      >
                        Validation:{' '}
                        <strong>
                          {item.validation_ready
                            ? 'yes'
                            : 'no'}
                        </strong>
                      </div>

                      <div
                        style={{
                          fontSize: '11px',
                        }}
                      >
                        Certification:{' '}
                        <strong>
                          {item.certification_ready
                            ? 'yes'
                            : 'no'}
                        </strong>
                      </div>
                    </td>

                    <td>
                      {!transition ? (
                        <span
                          style={{
                            color:
                              'var(--positive)',
                            fontSize: '12px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '5px',
                          }}
                        >
                          <CheckCircle2
                            size={13}
                          />
                          Certified
                        </span>
                      ) : (
                        <button
                          className=
                            "btn btn-secondary btn-sm"
                          disabled={
                            updating === key
                          }
                          onClick={() =>
                            handlePromote(item)
                          }
                        >
                          {updating === key
                            ? (
                              <Loader2
                                size={12}
                                className="spin"
                              />
                            )
                            : (
                              <Award
                                size={12}
                              />
                            )}

                          {updating === key
                            ? 'Updating...'
                            : `Promote to ${transition}`}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}

              {certifications.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    style={{
                      textAlign: 'center',
                      color: 'var(--muted)',
                    }}
                  >
                    No dataset certification
                    records exist yet.
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
