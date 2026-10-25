import React, { useState } from 'react';
import { Layers, Copy, Check, HardDrive } from 'lucide-react';

const MOCK_ASSETS = [
  {
    asset_id: 1,
    layer: 'bronze',
    asset_name: 'olist_customers_bronze',
    storage_uri: 's3://dataforge-bronze/olist/olist-alpha/customers/source_checksum=a1b2c3d4/customers.parquet',
    format: 'parquet',
    row_count: 99441,
    checksum: '34e1a7b98f219c4d8721bf10aa22e189',
    created_at: '2026-10-25 13:30:00',
  },
  {
    asset_id: 2,
    layer: 'bronze',
    asset_name: 'olist_orders_bronze',
    storage_uri: 's3://dataforge-bronze/olist/olist-alpha/orders/source_checksum=b2c3d4e5/orders.parquet',
    format: 'parquet',
    row_count: 99441,
    checksum: '9f21b7c89a012d4e8721bf10aa22e189',
    created_at: '2026-10-25 13:31:00',
  },
  {
    asset_id: 3,
    layer: 'silver',
    asset_name: 'olist_customers_silver_validated',
    storage_uri: 's3://dataforge-silver/olist/olist-alpha/customers/source_checksum=a1b2c3d4/validated_v1/customers.parquet',
    format: 'parquet',
    row_count: 99441,
    checksum: '82f1b0a99c716d1234901baefd7621cc',
    created_at: '2026-10-25 13:32:10',
  },
  {
    asset_id: 4,
    layer: 'silver',
    asset_name: 'olist_products_silver_validated',
    storage_uri: 's3://dataforge-silver/olist/olist-alpha/products/source_checksum=3e6569628a17/validated_v1/products.parquet',
    format: 'parquet',
    row_count: 32947,
    checksum: '551a029fe871ac99120489baec1239aa',
    created_at: '2026-10-25 13:40:12',
  },
  {
    asset_id: 5,
    layer: 'quarantine',
    asset_name: 'olist_products_quarantine',
    storage_uri: 's3://dataforge-quarantine/olist/olist-alpha/products/source_checksum=3e6569628a17/quality_v1/products.parquet',
    format: 'parquet',
    row_count: 4,
    checksum: '4457e8fa01b2389d8719ab238129ccbb',
    created_at: '2026-10-25 13:40:12',
  },
  {
    asset_id: 6,
    layer: 'gold',
    asset_name: 'olist_order_items_summary_gold',
    storage_uri: 's3://dataforge-gold/olist/olist-alpha/order_items_summary/gold_v1/order_items_summary.parquet',
    format: 'parquet',
    row_count: 112650,
    checksum: '99014bdcf87e12aa4419cb772019aaef',
    created_at: '2026-10-25 13:45:00',
  },
];

export default function AssetsView() {
  const [filterLayer, setFilterLayer] = useState('all');
  const [copiedId, setCopiedId] = useState(null);

  const filtered = filterLayer === 'all'
    ? MOCK_ASSETS
    : MOCK_ASSETS.filter((a) => a.layer === filterLayer);

  const handleCopy = (uri, id) => {
    navigator.clipboard.writeText(uri);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
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
              {filtered.map((asset) => (
                <tr key={asset.asset_id}>
                  <td><strong>{asset.asset_name}</strong></td>
                  <td>{getLayerBadge(asset.layer)}</td>
                  <td><span className="badge badge-neutral mono">{asset.format}</span></td>
                  <td className="tabular-nums">{asset.row_count.toLocaleString()}</td>
                  <td className="mono" style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    {asset.checksum.slice(0, 16)}…
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
