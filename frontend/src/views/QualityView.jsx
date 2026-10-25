import React, { useState, useEffect } from 'react';
import { fetchDatasets, fetchQuarantine } from '../services/api';
import { ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2, Download, Filter } from 'lucide-react';

const MOCK_RULES_BY_DATASET = {
  products: [
    {
      name: 'product_id_not_null',
      rule: 'not_null',
      column: 'product_id',
      severity: 'critical',
      status: 'pass',
      failed_rows: 0,
      failure_pct: 0.0,
      description: 'Primary key must be fully populated with zero missing values.',
    },
    {
      name: 'product_weight_positive_when_present',
      rule: 'greater_than',
      column: 'product_weight_g',
      severity: 'critical',
      status: 'fail',
      failed_rows: 4,
      failure_pct: 0.0121,
      description: 'Product weight in grams must strictly exceed zero when specified.',
    },
    {
      name: 'product_length_positive_when_present',
      rule: 'greater_than',
      column: 'product_length_cm',
      severity: 'critical',
      status: 'pass',
      failed_rows: 0,
      failure_pct: 0.0,
      description: 'Product length in centimeters must exceed zero.',
    },
    {
      name: 'product_category_present',
      rule: 'not_null',
      column: 'product_category_name',
      severity: 'warning',
      status: 'fail',
      failed_rows: 610,
      failure_pct: 1.85,
      description: 'Category name should be present for reporting completeness.',
    },
  ],
  customers: [
    {
      name: 'customer_id_not_null',
      rule: 'not_null',
      column: 'customer_id',
      severity: 'critical',
      status: 'pass',
      failed_rows: 0,
      failure_pct: 0.0,
      description: 'Customer identifier must not be null.',
    },
    {
      name: 'customer_state_iso_regex',
      rule: 'regex',
      column: 'customer_state',
      severity: 'critical',
      status: 'pass',
      failed_rows: 0,
      failure_pct: 0.0,
      description: 'State code must match 2-character uppercase Brazilian state standard.',
    },
  ],
  orders: [
    {
      name: 'order_id_not_null',
      rule: 'not_null',
      column: 'order_id',
      severity: 'critical',
      status: 'pass',
      failed_rows: 0,
      failure_pct: 0.0,
      description: 'Order primary key must not be null.',
    },
  ],
};

export default function QualityView() {
  const [selectedDataset, setSelectedDataset] = useState('products');
  const [quarantineRecords, setQuarantineRecords] = useState([]);

  useEffect(() => {
    fetchQuarantine(selectedDataset).then((data) => setQuarantineRecords(data));
  }, [selectedDataset]);

  const rules = MOCK_RULES_BY_DATASET[selectedDataset] || MOCK_RULES_BY_DATASET.products;

  return (
    <div>
      {/* Dataset Selection Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--muted)', marginRight: '8px' }}>
          Select Dataset:
        </span>
        {['products', 'customers', 'orders'].map((ds) => (
          <button
            key={ds}
            onClick={() => setSelectedDataset(ds)}
            className={`btn ${selectedDataset === ds ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            style={{ textTransform: 'capitalize' }}
          >
            {ds}
          </button>
        ))}
      </div>

      {/* Severity Rules Banner */}
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
            border: '1px solid var(--positive-border)',
            borderRadius: 'var(--radius-md)',
            padding: '12px 16px',
            fontSize: '13px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: 'var(--positive)' }}>
            <CheckCircle2 size={16} />
            <span>Validated Silver Partitioning</span>
          </div>
          <p style={{ color: '#166534', marginTop: '4px', fontSize: '12px' }}>
            Records passing all critical quality checks are persisted to <code>s3://dataforge-silver/</code> and certified for downstream Gold models.
          </p>
        </div>

        <div
          style={{
            background: 'var(--negative-bg)',
            border: '1px solid var(--negative-border)',
            borderRadius: 'var(--radius-md)',
            padding: '12px 16px',
            fontSize: '13px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: 'var(--negative)' }}>
            <ShieldAlert size={16} />
            <span>Automatic Quarantine Routing</span>
          </div>
          <p style={{ color: '#991b1b', marginTop: '4px', fontSize: '12px' }}>
            Records failing <strong>critical</strong> rules are automatically quarantined into <code>s3://dataforge-quarantine/</code> without breaking the pipeline.
          </p>
        </div>
      </div>

      {/* Rules Evaluation Table */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h3 className="card-title">Declared Quality Gate Rules ({selectedDataset})</h3>
        <p className="card-subtitle">
          Evaluated via Great Expectations and deterministic row-level failure masks.
        </p>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Rule Name</th>
                <th>Type</th>
                <th>Target Column</th>
                <th>Severity</th>
                <th>Evaluation Status</th>
                <th>Failed Rows</th>
                <th>Failure %</th>
                <th>Policy Description</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => {
                const isFail = rule.status === 'fail';
                const isCritical = rule.severity === 'critical';
                return (
                  <tr key={rule.name}>
                    <td><strong className="mono" style={{ fontSize: '12px' }}>{rule.name}</strong></td>
                    <td><span className="badge badge-neutral mono">{rule.rule}</span></td>
                    <td className="mono">{rule.column}</td>
                    <td>
                      <span className={`badge ${isCritical ? 'badge-negative' : 'badge-warning'}`}>
                        {isCritical ? 'Critical' : 'Warning'}
                      </span>
                    </td>
                    <td>
                      {isFail ? (
                        <span className={`badge ${isCritical ? 'badge-negative' : 'badge-warning'}`}>
                          {isCritical ? <ShieldAlert size={11} /> : <AlertTriangle size={11} />}
                          Failed
                        </span>
                      ) : (
                        <span className="badge badge-positive">
                          <CheckCircle2 size={11} />
                          Passed
                        </span>
                      )}
                    </td>
                    <td className="tabular-nums" style={{ fontWeight: isFail ? 600 : 400 }}>
                      {rule.failed_rows.toLocaleString()}
                    </td>
                    <td className="tabular-nums">
                      {rule.failure_pct}%
                    </td>
                    <td style={{ color: 'var(--muted)', fontSize: '12px' }}>
                      {rule.description}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quarantine Inspector */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <div>
            <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldAlert size={18} color="var(--negative)" />
              <span>Quarantine Inspector ({quarantineRecords.length} records)</span>
            </h3>
            <p className="card-subtitle">
              Inspect critical rejected records isolated by the Quality Gate from <code>{selectedDataset}</code>.
            </p>
          </div>

          {quarantineRecords.length > 0 && (
            <button className="btn btn-secondary btn-sm" onClick={() => alert('Quarantine parquet asset downloaded.')}>
              <Download size={13} />
              <span>Export Quarantine Parquet</span>
            </button>
          )}
        </div>

        {quarantineRecords.length > 0 ? (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Quarantine ID</th>
                  <th>Record Key / ID</th>
                  <th>Failed Rule</th>
                  <th>Violated Field</th>
                  <th>Observed Value</th>
                  <th>Severity</th>
                  <th>Quarantined At</th>
                </tr>
              </thead>
              <tbody>
                {quarantineRecords.map((qr) => (
                  <tr key={qr.quarantine_id}>
                    <td className="mono" style={{ color: 'var(--muted)' }}>{qr.quarantine_id}</td>
                    <td className="mono"><strong>{qr.record_id}</strong></td>
                    <td className="mono" style={{ fontSize: '12px' }}>{qr.rule_violated}</td>
                    <td className="mono">{qr.failed_field}</td>
                    <td>
                      <span className="badge badge-negative tabular-nums">
                        {qr.observed_value}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-negative">CRITICAL</span>
                    </td>
                    <td style={{ color: 'var(--muted)', fontSize: '12px' }}>{qr.quarantined_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--muted)', background: 'var(--surface-raised)', borderRadius: 'var(--radius-md)' }}>
            <CheckCircle2 size={28} color="var(--positive)" style={{ marginBottom: '8px' }} />
            <div style={{ fontWeight: 600, color: 'var(--accent)' }}>Zero Quarantine Records Detected</div>
            <div style={{ fontSize: '12px', marginTop: '4px' }}>All ingested records passed critical quality gates into Validated Silver.</div>
          </div>
        )}
      </div>
    </div>
  );
}
