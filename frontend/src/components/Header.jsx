import React from 'react';
import { RefreshCw, Server, CheckCircle2 } from 'lucide-react';

const TAB_TITLES = {
  overview: 'Platform Overview & Health',
  onboarding: 'Generic Source Onboarding',
  datasets: 'Datasets, Schema Discovery & Profiling',
  quality: 'Quality Gate & Quarantine Inspector',
  pipelines: 'Pipeline Execution & Run Observability',
  assets: 'Multi-layer Data Assets',
  lineage: 'End-to-End Lineage & Certification',
  copilot: 'LLM Configuration Copilot',
};

export default function Header({ activeTab, onRefresh, activeSource, setActiveSource }) {
  return (
    <header className="top-header">
      <div className="header-left">
        <h1 className="page-title">{TAB_TITLES[activeTab] || 'DataForge'}</h1>
      </div>

      <div className="header-right">
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#4b5563' }}>
          <Server size={14} color="#1d5fbf" />
          <span>Control Plane:</span>
          <span className="badge badge-positive" style={{ padding: '2px 6px' }}>FastAPI Connected</span>
        </div>

        <select
          value={activeSource}
          onChange={(e) => setActiveSource(e.target.value)}
          style={{
            padding: '4px 8px',
            fontSize: '12px',
            borderRadius: '4px',
            border: '1px solid #d1d5db',
            background: '#fff',
            cursor: 'pointer',
          }}
        >
          <option value="all">All Sources (Multi-Source)</option>
          <option value="olist-csv">Olist CSV Pilot</option>
          <option value="crm-postgres">CRM PostgreSQL (2nd Source)</option>
        </select>

        <button className="btn btn-secondary btn-sm" onClick={onRefresh} title="Refresh data">
          <RefreshCw size={13} />
          <span>Refresh</span>
        </button>
      </div>
    </header>
  );
}
