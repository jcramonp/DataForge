import React, { useState } from 'react';
import { testSourceConnection } from '../services/api';
import { PlugZap, CheckCircle2, AlertCircle, FileCode, Play, Sparkles } from 'lucide-react';

const PRESET_SOURCES = [
  {
    code: 'olist-csv',
    name: 'Olist E-Commerce CSV Files',
    type: 'file',
    connection_reference: 'env:DATA_RAW_DIR',
    target_object: 'data/raw/olist/*.csv',
    description: 'Pilot multi-table CSV source covering customers, orders, items and products.',
  },
  {
    code: 'crm-postgres',
    name: 'Enterprise PostgreSQL CRM',
    type: 'postgresql',
    connection_reference: 'env:CRM_POSTGRES_URI',
    target_object: 'public.sales_orders',
    description: 'Second source demonstrating relational database extraction without Olist assumptions.',
  },
  {
    code: 'store-rest-api',
    name: 'E-Commerce JSON REST Service',
    type: 'rest',
    connection_reference: 'env:STORE_API_KEY',
    target_object: 'https://api.store.internal/v1/orders',
    description: 'Paginated JSON REST connector for ad-hoc and external cloud services.',
  },
];

export default function OnboardingView() {
  const [formData, setFormData] = useState({
    code: 'crm-postgres',
    name: 'Enterprise PostgreSQL CRM',
    source_type: 'postgresql',
    connection_reference: 'env:CRM_POSTGRES_URI',
    target_object: 'public.sales_orders',
  });

  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [onboarded, setOnboarded] = useState(false);

  const handlePresetSelect = (preset) => {
    setFormData({
      code: preset.code,
      name: preset.name,
      source_type: preset.type,
      connection_reference: preset.connection_reference,
      target_object: preset.target_object,
    });
    setTestResult(null);
    setOnboarded(false);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testSourceConnection({
        source_type: formData.source_type,
        connection_reference: formData.connection_reference,
        target_object: formData.target_object,
      });
      setTestResult(res);
    } catch (err) {
      setTestResult({
        success: false,
        message: 'Connection failed: ' + err.message,
      });
    } finally {
      setTesting(false);
    }
  };

  const handleRegister = (e) => {
    e.preventDefault();
    setOnboarded(true);
  };

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '20px' }}>
        {/* Onboarding Form */}
        <div className="card">
          <h2 className="card-title">Register Data Source</h2>
          <p className="card-subtitle">
            Configure a generic source connector conforming to DataForge contracts.
          </p>

          <form onSubmit={handleRegister}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#374151', marginBottom: '6px' }}>
                  Source Code (Unique Identifier)
                </label>
                <input
                  type="text"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '4px', border: '1px solid #d1d5db' }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#374151', marginBottom: '6px' }}>
                  Source Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '4px', border: '1px solid #d1d5db' }}
                  required
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#374151', marginBottom: '6px' }}>
                  Connector Type
                </label>
                <select
                  value={formData.source_type}
                  onChange={(e) => setFormData({ ...formData, source_type: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '4px', border: '1px solid #d1d5db', background: '#fff' }}
                >
                  <option value="file">Local / S3 File (CSV, Parquet, JSON)</option>
                  <option value="postgresql">PostgreSQL Relational Database</option>
                  <option value="rest">REST API (JSON Paginated)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#374151', marginBottom: '6px' }}>
                  Connection Reference (Environment Variable)
                </label>
                <input
                  type="text"
                  value={formData.connection_reference}
                  onChange={(e) => setFormData({ ...formData, connection_reference: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '4px', border: '1px solid #d1d5db', fontFamily: 'var(--font-mono)' }}
                  required
                />
              </div>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#374151', marginBottom: '6px' }}>
                Target Object / Query / Endpoint
              </label>
              <input
                type="text"
                value={formData.target_object}
                onChange={(e) => setFormData({ ...formData, target_object: e.target.value })}
                style={{ width: '100%', padding: '8px 12px', borderRadius: '4px', border: '1px solid #d1d5db', fontFamily: 'var(--font-mono)' }}
                required
              />
            </div>

            {/* Test connection & submit */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', paddingTop: '12px', borderTop: '1px solid var(--border)' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleTestConnection}
                disabled={testing}
              >
                <PlugZap size={14} color="#1d5fbf" />
                <span>{testing ? 'Verifying...' : 'Test Connection'}</span>
              </button>

              <button type="submit" className="btn btn-primary">
                <CheckCircle2 size={14} />
                <span>Save & Onboard Source</span>
              </button>
            </div>
          </form>

          {/* Test connection result banner */}
          {testResult && (
            <div
              style={{
                marginTop: '16px',
                padding: '12px 16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: testResult.success ? 'var(--positive-bg)' : 'var(--negative-bg)',
                border: `1px solid ${testResult.success ? 'var(--positive-border)' : 'var(--negative-border)'}`,
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
              }}
            >
              {testResult.success ? (
                <CheckCircle2 size={16} color="var(--positive)" />
              ) : (
                <AlertCircle size={16} color="var(--negative)" />
              )}
              <div style={{ flex: 1, fontSize: '13px', color: testResult.success ? 'var(--positive)' : 'var(--negative)' }}>
                <strong>{testResult.success ? 'Success:' : 'Error:'}</strong> {testResult.message}
                {testResult.latency_ms && (
                  <span style={{ marginLeft: '8px', opacity: 0.8 }} className="mono">
                    ({testResult.latency_ms} ms)
                  </span>
                )}
              </div>
            </div>
          )}

          {onboarded && (
            <div
              style={{
                marginTop: '16px',
                padding: '12px 16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--positive-bg)',
                border: '1px solid var(--positive-border)',
                color: 'var(--positive)',
                fontSize: '13px',
              }}
            >
              <strong>Source Onboarded:</strong> '{formData.name}' registered to control plane contract repository.
            </div>
          )}
        </div>

        {/* Preset Sources Panel */}
        <div>
          <div className="card">
            <h3 className="card-title" style={{ fontSize: '14px' }}>Preset Source Templates</h3>
            <p className="card-subtitle" style={{ fontSize: '12px' }}>
              Select a verified source template to pre-fill contract settings:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {PRESET_SOURCES.map((preset) => (
                <div
                  key={preset.code}
                  onClick={() => handlePresetSelect(preset)}
                  style={{
                    padding: '12px',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    cursor: 'pointer',
                    background: formData.code === preset.code ? 'var(--surface-raised)' : 'var(--surface)',
                    borderColor: formData.code === preset.code ? 'var(--accent)' : 'var(--border)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600, fontSize: '13px' }}>{preset.name}</span>
                    <span className="badge badge-neutral" style={{ textTransform: 'uppercase' }}>
                      {preset.type}
                    </span>
                  </div>
                  <p style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
                    {preset.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
