import React, { useState, useEffect } from 'react';
import { fetchDatasets, fetchDatasetProfiling } from '../services/api';
import { Database, Key, Shield, Eye, X, CheckCircle2, AlertCircle } from 'lucide-react';

export default function DatasetsView() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [profilingData, setProfilingData] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(false);

  useEffect(() => {
    fetchDatasets().then((data) => {
      setDatasets(data);
      if (data.length > 0) setSelectedDataset(data[0]);
    });
  }, []);

  const handleOpenProfiling = async (datasetCode) => {
    setLoadingProfile(true);
    try {
      const data = await fetchDatasetProfiling(datasetCode);
      setProfilingData(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingProfile(false);
    }
  };

  return (
    <div>
      {/* Top Selector Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginBottom: '20px' }}>
        {datasets.map((d) => {
          const isSelected = selectedDataset?.code === d.code;
          return (
            <div
              key={d.code}
              onClick={() => setSelectedDataset(d)}
              style={{
                padding: '14px 16px',
                background: isSelected ? 'var(--surface-raised)' : 'var(--surface)',
                border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--accent)' }}>{d.name}</span>
                <span className="badge badge-neutral mono" style={{ fontSize: '10px' }}>{d.source_type}</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>
                {d.columns_count} columns · {d.rules_count} quality rules
              </div>
              <div style={{ marginTop: '8px', display: 'flex', gap: '6px' }}>
                <span className={`badge ${d.certification_status === 'certified' ? 'badge-positive' : 'badge-warning'}`}>
                  {d.certification_status}
                </span>
                {d.primary_keys?.length > 0 && (
                  <span className="badge badge-neutral" style={{ fontSize: '10px' }}>
                    PK: {d.primary_keys.join(', ')}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Dataset Details & Schema Table */}
      {selectedDataset && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div>
              <h2 className="card-title">Dataset Schema: {selectedDataset.name}</h2>
              <p className="card-subtitle">
                Declared contract schema with technical DataForge data types and nullability constraints.
              </p>
            </div>

            <button
              className="btn btn-secondary btn-sm"
              onClick={() => handleOpenProfiling(selectedDataset.code)}
            >
              <Eye size={13} color="#1d5fbf" />
              <span>Inspect Profiling Facts</span>
            </button>
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Column Name</th>
                  <th>DataForge Type</th>
                  <th>Nullable</th>
                  <th>Classification</th>
                  <th>Role</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {selectedDataset.schema.map((col) => {
                  const isPk = selectedDataset.primary_keys?.includes(col.name);
                  return (
                    <tr key={col.name}>
                      <td>
                        <strong className="mono" style={{ fontSize: '13px' }}>{col.name}</strong>
                      </td>
                      <td>
                        <span className="badge badge-neutral mono" style={{ fontWeight: 600 }}>
                          {col.type}
                        </span>
                      </td>
                      <td>
                        {col.nullable ? (
                          <span style={{ color: 'var(--muted)', fontSize: '12px' }}>Yes (optional)</span>
                        ) : (
                          <span className="badge badge-warning" style={{ fontSize: '11px' }}>No (required)</span>
                        )}
                      </td>
                      <td>
                        <span className="badge badge-neutral" style={{ fontSize: '11px', textTransform: 'capitalize' }}>
                          <Shield size={10} />
                          {col.classification || 'Internal'}
                        </span>
                      </td>
                      <td>
                        {isPk ? (
                          <span className="badge badge-positive" style={{ fontSize: '10px' }}>
                            <Key size={10} />
                            Primary Key
                          </span>
                        ) : (
                          <span style={{ color: 'var(--muted)' }}>—</span>
                        )}
                      </td>
                      <td style={{ color: 'var(--muted)', fontSize: '12px' }}>
                        {col.description || 'Standard technical attribute'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Profiling Facts Modal */}
      {profilingData && (
        <div className="modal-overlay" onClick={() => setProfilingData(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ width: '850px' }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Profiling Facts: {profilingData.dataset_name}</h3>
                <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                  Generated by DataForge Discovery Engine (Issue #21) · {profilingData.generated_at_utc}
                </div>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setProfilingData(null)}
                style={{ padding: '4px' }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Quick Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '16px' }}>
              <div className="card" style={{ padding: '12px', background: 'var(--surface-raised)' }}>
                <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Total Rows</div>
                <div style={{ fontSize: '18px', fontWeight: 600 }}>{profilingData.row_count.toLocaleString()}</div>
              </div>
              <div className="card" style={{ padding: '12px', background: 'var(--surface-raised)' }}>
                <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Columns</div>
                <div style={{ fontSize: '18px', fontWeight: 600 }}>{profilingData.column_count}</div>
              </div>
              <div className="card" style={{ padding: '12px', background: 'var(--surface-raised)' }}>
                <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Duplicate Rows</div>
                <div style={{ fontSize: '18px', fontWeight: 600 }}>{profilingData.duplicate_rows}</div>
              </div>
              <div className="card" style={{ padding: '12px', background: 'var(--surface-raised)' }}>
                <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Candidate Keys</div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--positive)', marginTop: '2px' }}>
                  {profilingData.candidate_keys.length > 0 ? profilingData.candidate_keys.join(', ') : 'None'}
                </div>
              </div>
            </div>

            {/* Column Profiling Facts Table */}
            <h4 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>Column Facts & Cardinality</h4>
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Inferred Type</th>
                    <th>Nulls</th>
                    <th>Distinct</th>
                    <th>Uniqueness</th>
                    <th>Sample Values</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(profilingData.columns || {}).map(([colName, colProf]) => (
                    <tr key={colName}>
                      <td className="mono" style={{ fontWeight: 600 }}>{colName}</td>
                      <td>
                        <span className="badge badge-neutral mono">{colProf.inferred_type}</span>
                      </td>
                      <td className="tabular-nums">
                        {colProf.null_count} ({colProf.null_percentage}%)
                      </td>
                      <td className="tabular-nums">{colProf.distinct_count?.toLocaleString()}</td>
                      <td className="tabular-nums">{roundPct(colProf.uniqueness_ratio)}%</td>
                      <td className="mono" style={{ fontSize: '11px', color: 'var(--muted)', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {colProf.sample_values?.slice(0, 3).join(', ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setProfilingData(null)}>
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function roundPct(ratio) {
  if (ratio === undefined || ratio === null) return '0.0';
  return (ratio * 100).toFixed(1);
}
