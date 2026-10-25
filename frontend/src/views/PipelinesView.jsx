import React, { useState, useEffect } from 'react';
import { triggerPipeline } from '../services/api';
import { Play, CheckCircle2, ShieldAlert, Clock, Filter, Loader2 } from 'lucide-react';

export default function PipelinesView({ overview, onRefresh }) {
  const [runs, setRuns] = useState(overview?.recent_runs || []);
  const [triggering, setTriggering] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState('products');
  const [targetLayer, setTargetLayer] = useState('silver_quality_gate');
  const [statusMessage, setStatusMessage] = useState(null);

  useEffect(() => {
    if (overview?.recent_runs) setRuns(overview.recent_runs);
  }, [overview]);

  const handleTrigger = async () => {
    setTriggering(true);
    setStatusMessage(null);
    try {
      const res = await triggerPipeline(selectedDataset);
      if (res.run) {
        setRuns([res.run, ...runs]);
        setStatusMessage({
          type: 'success',
          text: `Run #${res.run.run_id} completed: ${res.run.accepted_rows.toLocaleString()} accepted rows into Validated Silver, ${res.run.rejected_rows} routed to Quarantine.`,
        });
      }
    } catch (err) {
      setStatusMessage({ type: 'error', text: 'Pipeline failed: ' + err.message });
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div>
      {/* Pipeline Trigger Action Bar */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h3 className="card-title">Trigger Pipeline Execution</h3>
        <p className="card-subtitle">
          Execute generic deterministic processing stages without manual scripts or direct SQL access.
        </p>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--muted)', marginBottom: '4px' }}>
              Target Dataset:
            </label>
            <select
              value={selectedDataset}
              onChange={(e) => setSelectedDataset(e.target.value)}
              style={{ padding: '6px 12px', borderRadius: '4px', border: '1px solid #d1d5db', background: '#fff' }}
            >
              <option value="products">products (Olist Pilot)</option>
              <option value="orders">orders (Olist Pilot)</option>
              <option value="customers">customers (Olist Pilot)</option>
              <option value="order_items">order_items (Olist Pilot)</option>
              <option value="sales_orders">sales_orders (CRM 2nd Source)</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--muted)', marginBottom: '4px' }}>
              Pipeline Stage:
            </label>
            <select
              value={targetLayer}
              onChange={(e) => setTargetLayer(e.target.value)}
              style={{ padding: '6px 12px', borderRadius: '4px', border: '1px solid #d1d5db', background: '#fff' }}
            >
              <option value="silver_quality_gate">Bronze ➡️ Silver (Transform + Quality Gate)</option>
              <option value="source_to_bronze">Source ➡️ Bronze (Ingestion + Checksum)</option>
              <option value="gold_aggregation">Validated Silver ➡️ Gold (Curated Analytic Asset)</option>
            </select>
          </div>

          <div style={{ alignSelf: 'flex-end' }}>
            <button
              className="btn btn-primary"
              onClick={handleTrigger}
              disabled={triggering}
            >
              {triggering ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
              <span>{triggering ? 'Executing Pipeline...' : 'Run Pipeline Now'}</span>
            </button>
          </div>
        </div>

        {statusMessage && (
          <div
            style={{
              marginTop: '16px',
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              background: statusMessage.type === 'success' ? 'var(--positive-bg)' : 'var(--negative-bg)',
              border: `1px solid ${statusMessage.type === 'success' ? 'var(--positive-border)' : 'var(--negative-border)'}`,
              color: statusMessage.type === 'success' ? 'var(--positive)' : 'var(--negative)',
              fontSize: '13px',
            }}
          >
            {statusMessage.text}
          </div>
        )}
      </div>

      {/* Execution Run History */}
      <div className="card">
        <h3 className="card-title">Pipeline Execution History</h3>
        <p className="card-subtitle">
          Metadata-driven execution logs tracked in PostgreSQL control plane <code>pipeline_run</code> table.
        </p>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Dataset</th>
                <th>Source Code</th>
                <th>Stage / Layer</th>
                <th>Status</th>
                <th>Input Rows</th>
                <th>Accepted (Silver)</th>
                <th>Quarantined</th>
                <th>Duration</th>
                <th>Created At</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.run_id}>
                  <td className="mono">#{run.run_id}</td>
                  <td><strong>{run.dataset}</strong></td>
                  <td className="mono" style={{ fontSize: '12px' }}>{run.source}</td>
                  <td><span className="badge badge-neutral">{run.layer}</span></td>
                  <td>
                    <span className="badge badge-positive">
                      <CheckCircle2 size={11} />
                      {run.status}
                    </span>
                  </td>
                  <td className="tabular-nums">{run.input_rows.toLocaleString()}</td>
                  <td className="tabular-nums" style={{ color: 'var(--positive)', fontWeight: 600 }}>
                    {run.accepted_rows.toLocaleString()}
                  </td>
                  <td>
                    {run.rejected_rows > 0 ? (
                      <span className="badge badge-negative tabular-nums">
                        <ShieldAlert size={11} />
                        {run.rejected_rows}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--muted)' }}>0</span>
                    )}
                  </td>
                  <td className="tabular-nums">{run.duration_sec}s</td>
                  <td style={{ color: 'var(--muted)', fontSize: '12px' }}>
                    {new Date(run.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
