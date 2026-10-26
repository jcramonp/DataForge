import React from 'react';
import { sourceKey } from '../services/scope';
import { RefreshCw, Server } from 'lucide-react';

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

export default function Header({ activeTab, onRefresh, activeSource, setActiveSource, sources = [], connected }) {
  return (
    <header className="top-header">
      <div className="header-left">
        <h1 className="page-title">{TAB_TITLES[activeTab] || 'DataForge'}</h1>
      </div>

      <div className="header-right">
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#4b5563' }}>
          <Server size={14} color="#1d5fbf" />
          <span>Control Plane:</span>
          <span className={`badge ${connected === true ? 'badge-positive' : 'badge-warning'}`} style={{ padding: '2px 6px' }}>
            {connected === null ? 'Checking…' : connected ? 'FastAPI Connected' : 'Control plane unavailable'}
          </span>
        </div>

        <select
          aria-label="Source filter"
          disabled={activeTab === 'onboarding' || activeTab === 'copilot'}
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
          {sources.map((source) => (
            <option key={sourceKey(source)} value={sourceKey(source)}>
              {source.client_code} / {source.project_code} / {source.name}
            </option>
          ))}
        </select>

        <button className="btn btn-secondary btn-sm" onClick={onRefresh} title="Refresh data">
          <RefreshCw size={13} />
          <span>Refresh</span>
        </button>
      </div>
    </header>
  );
}
