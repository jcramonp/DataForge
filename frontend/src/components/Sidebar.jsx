import React from 'react';
import {
  LayoutDashboard,
  PlugZap,
  Database,
  ShieldCheck,
  PlayCircle,
  Layers,
  GitFork,
  Sparkles,
} from 'lucide-react';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'onboarding', label: 'Source Onboarding', icon: PlugZap },
  { id: 'datasets', label: 'Datasets & Profiling', icon: Database },
  { id: 'quality', label: 'Quality & Quarantine', icon: ShieldCheck },
  { id: 'pipelines', label: 'Pipelines & Runs', icon: PlayCircle },
  { id: 'assets', label: 'Data Assets', icon: Layers },
  { id: 'lineage', label: 'Lineage & Governance', icon: GitFork },
  { id: 'copilot', label: 'Copilot Assistant', icon: Sparkles },
];

export default function Sidebar({ activeTab, setActiveTab }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-logo">DF</div>
        <div>
          <div className="brand-title">DataForge</div>
          <div className="brand-subtitle">Control Plane v2.0</div>
        </div>
      </div>

      <ul className="nav-list">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <li
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => setActiveTab(item.id)}
            >
              <Icon size={16} strokeWidth={isActive ? 2.2 : 1.8} />
              <span>{item.label}</span>
            </li>
          );
        })}
      </ul>

      <div className="sidebar-footer">
        <div>Platform: <strong>Generic Multi-source</strong></div>
        <div style={{ marginTop: '4px', color: '#9ca3af' }}>Sprint 2 Delivery · EAFIT</div>
      </div>
    </aside>
  );
}
