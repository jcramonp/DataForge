import React from 'react';
import { Database, ShieldAlert, CheckCircle2, Play, ArrowRight, Activity } from 'lucide-react';

export default function OverviewView({ overview, onNavigate, onTriggerSample }) {
  const summary = overview?.summary || {};
  const runs = overview?.recent_runs || [];

  return (
    <div>
      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Active Sources</div>
          <div className="kpi-value">{summary.total_sources || 3}</div>
          <div className="kpi-sub">CSV, PostgreSQL, REST</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Registered Datasets</div>
          <div className="kpi-value">{summary.total_datasets || 6}</div>
          <div className="kpi-sub">Across Bronze & Silver</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Total Rows Processed</div>
          <div className="kpi-value">{(summary.total_rows_processed || 359903).toLocaleString()}</div>
          <div className="kpi-sub">Through Bronze & Silver</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Quarantine Records</div>
          <div className="kpi-value" style={{ color: 'var(--negative)' }}>
            {summary.total_quarantined_rows || 4}
          </div>
          <div className="kpi-sub">Critical violations separated</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Certified Datasets</div>
          <div className="kpi-value" style={{ color: 'var(--positive)' }}>
            {summary.certified_datasets || 2} <span style={{ fontSize: '14px', color: '#6b7280' }}>({summary.certification_rate_pct || 33.3}%)</span>
          </div>
          <div className="kpi-sub">Governed & ready for Gold</div>
        </div>
      </div>

      {/* Lifecycle strip */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div>
            <h3 className="card-title">DataForge End-to-End Lifecycle</h3>
            <p className="card-subtitle">Operate data assets from source registration to certification without direct database queries.</p>
          </div>
          <button className="btn btn-primary btn-sm" onClick={onTriggerSample}>
            <Play size={13} />
            <span>Trigger Demo Pipeline</span>
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
          <div
            onClick={() => onNavigate('onboarding')}
            style={{
              padding: '14px',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              background: 'var(--surface)',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>STEP 1</div>
            <div style={{ fontSize: '14px', fontWeight: 600, marginTop: '2px', color: 'var(--accent)' }}>Onboard Source</div>
            <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>Register contract & test connectivity</div>
          </div>

          <div
            onClick={() => onNavigate('datasets')}
            style={{
              padding: '14px',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              background: 'var(--surface)',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>STEP 2</div>
            <div style={{ fontSize: '14px', fontWeight: 600, marginTop: '2px', color: 'var(--accent)' }}>Schema Discovery</div>
            <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>Profile types, nulls & candidate keys</div>
          </div>

          <div
            onClick={() => onNavigate('quality')}
            style={{
              padding: '14px',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              background: 'var(--surface)',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>STEP 3</div>
            <div style={{ fontSize: '14px', fontWeight: 600, marginTop: '2px', color: 'var(--accent)' }}>Quality & Quarantine</div>
            <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>Filter critical errors & validate Silver</div>
          </div>

          <div
            onClick={() => onNavigate('lineage')}
            style={{
              padding: '14px',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              background: 'var(--surface)',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>STEP 4</div>
            <div style={{ fontSize: '14px', fontWeight: 600, marginTop: '2px', color: 'var(--accent)' }}>Certify & Publish</div>
            <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>Inspect lineage and certify datasets</div>
          </div>
        </div>
      </div>

      {/* Recent runs table */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <div>
            <h3 className="card-title">Recent Pipeline Runs</h3>
            <p className="card-subtitle">Real-time execution status, accepted rows, and quarantine metrics.</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('pipelines')}>
            <span>View All Runs</span>
            <ArrowRight size={13} />
          </button>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Dataset</th>
                <th>Source</th>
                <th>Layer</th>
                <th>Status</th>
                <th>Input Rows</th>
                <th>Accepted (Silver)</th>
                <th>Quarantined</th>
                <th>Duration</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.run_id}>
                  <td className="mono">#{run.run_id}</td>
                  <td><strong>{run.dataset}</strong></td>
                  <td className="mono" style={{ fontSize: '12px' }}>{run.source}</td>
                  <td>
                    <span className="badge badge-neutral">{run.layer}</span>
                  </td>
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
                        {run.rejected_rows} rows
                      </span>
                    ) : (
                      <span style={{ color: 'var(--muted)' }}>0</span>
                    )}
                  </td>
                  <td className="tabular-nums">{run.duration_sec}s</td>
                  <td style={{ color: 'var(--muted)', fontSize: '12px' }}>
                    {new Date(run.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
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
