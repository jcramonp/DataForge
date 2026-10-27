import React, { useState, useEffect } from 'react';
import { fetchAssets } from '../services/api';
import { Copy, Check } from 'lucide-react';

export default function AssetsView({ scope = {} }) {
  const [filterLayer, setFilterLayer] = useState('all');
  const [copiedId, setCopiedId] = useState(null);
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [limit, setLimit] = useState(100);
  const [refresh, setRefresh] = useState(0);
  const scopeKey = JSON.stringify(scope);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setAssets([]);
    fetchAssets({ ...scope, limit, layer: filterLayer === 'all' ? undefined : filterLayer })
      .then((rows) => { if (!cancelled) setAssets(rows); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [scopeKey, filterLayer, limit, refresh]);
  const filtered = assets;

  const handleCopy = async (uri, id) => {
    try {
      await navigator.clipboard.writeText(uri);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) { setError(`Unable to copy URI: ${err.message}`); }
  };

  const getLayerBadge = (layer) => {
    switch (layer) {
      case 'bronze':
        return <span className="badge badge-neutral" style={{ background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a' }}>Bronze</span>;
      case 'silver':
        return <span className="badge badge-positive">Silver (Validated)</span>;
      case 'quarantine':
        return <span className="badge badge-negative">Quarantine</span>;
      case 'gold':
        return <span className="badge" style={{ background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' }}>Gold</span>;
      default:
        return <span className="badge badge-neutral">{layer}</span>;
    }
  };

  return (
    <div>
      {error && <p role="alert">{error}</p>}
      <button className="btn btn-secondary btn-sm" onClick={() => setRefresh((n) => n + 1)}>Refresh assets</button>
      <label> Maximum assets <select aria-label="Maximum assets" value={limit} onChange={(e) => setLimit(Number(e.target.value))}><option value={100}>100</option><option value={200}>200</option></select></label>
      <p>{loading ? 'Loading persisted assets…' : `Showing ${assets.length} most recent assets (limit ${limit}).`}</p>
      {/* Filter Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
        {['all', 'bronze', 'silver', 'quarantine', 'gold'].map((layer) => (
          <button
            key={layer}
            onClick={() => setFilterLayer(layer)}
            className={`btn ${filterLayer === layer ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            style={{ textTransform: 'capitalize' }}
          >
            {layer === 'all' ? 'All Layers' : layer}
          </button>
        ))}
      </div>

      <div className="card">
        <h3 className="card-title">Persisted Data Plane Assets</h3>
        <p className="card-subtitle">
          Physical Parquet files persisted in MinIO/S3 and indexed in PostgreSQL <code>data_asset</code> table.
        </p>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Asset Name</th>
                <th>Layer</th>
                <th>Format</th>
                <th>Row Count</th>
                <th>SHA-256 Checksum</th>
                <th>Storage URI</th>
                <th>Created At</th>
              </tr>
            </thead>
            <tbody>
              {!loading && !error && assets.length === 0 && <tr><td colSpan={7}>No persisted assets in this scope.</td></tr>}
              {filtered.map((asset) => (
                <tr key={asset.asset_id}>
                  <td><strong>{asset.asset_name}</strong><div className="mono">#{asset.asset_id} · {asset.client_code}/{asset.project_code}/{asset.source_code}/{asset.dataset_code}</div></td>
                  <td>{getLayerBadge(asset.layer)}</td>
                  <td><span className="badge badge-neutral mono">{asset.format}</span></td>
                  <td className="tabular-nums">{asset.row_count == null ? '—' : asset.row_count.toLocaleString()}</td>
                  <td className="mono" style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    {asset.checksum ? `${asset.checksum.slice(0, 16)}…` : '—'}
                  </td>
                  <td style={{ maxWidth: '320px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="mono" style={{ fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {asset.storage_uri}
                      </span>
                      <button
                        onClick={() => handleCopy(asset.storage_uri, asset.asset_id)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px' }}
                        title="Copy S3 URI"
                      >
                        {copiedId === asset.asset_id ? <Check size={12} color="var(--positive)" /> : <Copy size={12} color="var(--muted)" />}
                      </button>
                    </div>
                  </td>
                  <td style={{ color: 'var(--muted)', fontSize: '12px' }}>{asset.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
