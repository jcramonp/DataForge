import React, { useState, useEffect } from 'react';
import { fetchCertification, updateCertification } from '../services/api';
import { GitFork, CheckCircle2, ShieldCheck, Award, ArrowRight } from 'lucide-react';

export default function LineageView() {
  const [certifications, setCertifications] = useState([]);
  const [updating, setUpdating] = useState(null);

  useEffect(() => {
    fetchCertification().then((data) => setCertifications(data));
  }, []);

  const handlePromote = async (datasetCode) => {
    setUpdating(datasetCode);
    try {
      await updateCertification(datasetCode, 'certified');
      setCertifications(
        certifications.map((c) =>
          c.dataset_code === datasetCode ? { ...c, status: 'certified', certified_by: 'gabriela611' } : c
        )
      );
    } catch (err) {
      console.error(err);
    } finally {
      setUpdating(null);
    }
  };

  return (
    <div>
      {/* Visual Lineage DAG */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h3 className="card-title">Interactive Asset-to-Asset Lineage</h3>
        <p className="card-subtitle">
          Traceable data lineage from raw extraction through Bronze, Silver, Quarantine, and analytical Gold.
        </p>

        <div
          style={{
            background: 'var(--surface-raised)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: '30px',
            position: 'relative',
            overflowX: 'auto',
          }}
        >
          {/* SVG Diagram Canvas */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', minWidth: '760px', gap: '20px' }}>
            {/* Step 1: Sources */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--muted)', textAlign: 'center' }}>SOURCE PLANE</div>
              <div style={{ padding: '12px 18px', background: '#fff', border: '1px solid var(--border)', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontWeight: 600, fontSize: '13px' }}>Olist CSV Ingest</div>
                <div style={{ fontSize: '11px', color: 'var(--muted)' }}>4 Pilot Tables</div>
              </div>
              <div style={{ padding: '12px 18px', background: '#fff', border: '1px solid var(--border)', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontWeight: 600, fontSize: '13px' }}>CRM PostgreSQL</div>
                <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Sales Orders (2nd Source)</div>
              </div>
            </div>

            <ArrowRight size={20} color="#9ca3af" />

            {/* Step 2: Bronze */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--muted)', textAlign: 'center' }}>BRONZE (IMMUTABLE)</div>
              <div style={{ padding: '12px 18px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontWeight: 600, fontSize: '13px', color: '#92400e' }}>Bronze Datasets</div>
                <div style={{ fontSize: '11px', color: '#b45309' }}>SHA-256 Verified Parquet</div>
              </div>
            </div>

            <ArrowRight size={20} color="#9ca3af" />

            {/* Step 3: Silver & Quarantine Split */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--muted)', textAlign: 'center' }}>QUALITY GATE & PARTITION</div>

              {/* Silver Validated */}
              <div style={{ padding: '12px 18px', background: 'var(--positive-bg)', border: '1px solid var(--positive-border)', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--positive)' }}>Validated Silver</div>
                <div style={{ fontSize: '11px', color: '#15803d' }}>Cleaned & Conforming</div>
              </div>

              {/* Quarantine */}
              <div style={{ padding: '10px 18px', background: 'var(--negative-bg)', border: '1px solid var(--negative-border)', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontWeight: 600, fontSize: '12px', color: 'var(--negative)' }}>Quarantine</div>
                <div style={{ fontSize: '10px', color: '#b91c1c' }}>Critical Violations (4 rows)</div>
              </div>
            </div>

            <ArrowRight size={20} color="#9ca3af" />

            {/* Step 4: Gold */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--muted)', textAlign: 'center' }}>GOLD (CURATED)</div>
              <div style={{ padding: '12px 18px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontWeight: 600, fontSize: '13px', color: '#1d4ed8' }}>Order Items Summary</div>
                <div style={{ fontSize: '11px', color: '#2563eb' }}>Integrated Fact Gold</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Dataset Governance & Certification Table */}
      <div className="card">
        <h3 className="card-title">Dataset Governance & Certification Status</h3>
        <p className="card-subtitle">
          Promote datasets through lifecycle states: <code>Draft</code> ➡️ <code>Validated</code> ➡️ <code>Certified</code>.
        </p>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Client / Source</th>
                <th>Current Status</th>
                <th>Quality Compliance</th>
                <th>Certified By</th>
                <th>Governance Action</th>
              </tr>
            </thead>
            <tbody>
              {certifications.map((item) => {
                const isCertified = item.status === 'certified';
                return (
                  <tr key={item.dataset_code}>
                    <td><strong>{item.dataset_name}</strong></td>
                    <td className="mono" style={{ fontSize: '12px' }}>{item.client}</td>
                    <td>
                      <span className={`badge ${isCertified ? 'badge-positive' : 'badge-warning'}`}>
                        {isCertified ? <Award size={11} /> : <ShieldCheck size={11} />}
                        {item.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="tabular-nums">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ width: '80px', height: '6px', background: '#e5e7eb', borderRadius: '3px', overflow: 'hidden' }}>
                          <div
                            style={{
                              width: `${item.rules_passing_pct}%`,
                              height: '100%',
                              background: item.rules_passing_pct === 100 ? 'var(--positive)' : 'var(--warning)',
                            }}
                          />
                        </div>
                        <span>{item.rules_passing_pct}%</span>
                      </div>
                    </td>
                    <td>
                      {item.certified_by ? (
                        <span className="mono" style={{ fontSize: '12px', color: 'var(--accent)' }}>
                          @{item.certified_by}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--muted)' }}>Pending audit</span>
                      )}
                    </td>
                    <td>
                      {isCertified ? (
                        <span style={{ color: 'var(--positive)', fontSize: '12px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <CheckCircle2 size={13} />
                          Ready for Production
                        </span>
                      ) : (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handlePromote(item.dataset_code)}
                          disabled={updating === item.dataset_code}
                        >
                          <Award size={12} color="#1d5fbf" />
                          <span>{updating === item.dataset_code ? 'Promoting...' : 'Promote to Certified'}</span>
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
