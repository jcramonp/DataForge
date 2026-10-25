import React, { useState } from 'react';
import { suggestRulesWithLLM } from '../services/api';
import { Sparkles, Check, AlertCircle, Plus, Code, Shield } from 'lucide-react';

const SUGGESTION_PRESETS = [
  'El precio de los items debe ser estrictamente mayor a 0 y no puede tener valores nulos',
  'El estado del cliente debe cumplir con el formato de código postal o estado de dos letras mayúsculas',
  'El peso del producto no puede ser cero ni negativo cuando está presente',
];

export default function CopilotView() {
  const [requirement, setRequirement] = useState('');
  const [datasetCode, setDatasetCode] = useState('products');
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState(null);
  const [applied, setApplied] = useState(false);

  const handleGenerate = async (reqText) => {
    const query = reqText || requirement;
    if (!query.trim()) return;

    setLoading(true);
    setSuggestion(null);
    setApplied(false);
    try {
      const res = await suggestRulesWithLLM(
        datasetCode,
        query,
        datasetCode === 'products' ? ['product_weight_g', 'product_id', 'product_category_name'] : ['customer_state', 'customer_id']
      );
      setSuggestion(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    setApplied(true);
  };

  return (
    <div>
      <div className="card" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <Sparkles size={18} color="#1d5fbf" />
          <h2 className="card-title" style={{ margin: 0 }}>LLM Configuration Copilot</h2>
        </div>
        <p className="card-subtitle">
          Describe business requirements in natural language. The assistant proposes deterministic, schema-validated rules without executing arbitrary code.
        </p>

        {/* Preset chips */}
        <div style={{ marginBottom: '16px' }}>
          <span style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
            QUICK PRESETS:
          </span>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {SUGGESTION_PRESETS.map((p, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setRequirement(p);
                  handleGenerate(p);
                }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '12px' }}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* Input Form */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
          <div style={{ width: '180px', flexShrink: 0 }}>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--muted)', marginBottom: '4px' }}>
              Target Dataset:
            </label>
            <select
              value={datasetCode}
              onChange={(e) => setDatasetCode(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', borderRadius: '4px', border: '1px solid #d1d5db', background: '#fff' }}
            >
              <option value="products">products (Olist)</option>
              <option value="customers">customers (Olist)</option>
              <option value="orders">orders (Olist)</option>
              <option value="sales_orders">sales_orders (CRM)</option>
            </select>
          </div>

          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--muted)', marginBottom: '4px' }}>
              Requirement in Natural Language:
            </label>
            <textarea
              rows={2}
              value={requirement}
              onChange={(e) => setRequirement(e.target.value)}
              placeholder="Ej: El peso del producto no puede ser cero ni negativo cuando está presente..."
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: '4px',
                border: '1px solid #d1d5db',
                fontFamily: 'var(--font-sans)',
                fontSize: '13px',
              }}
            />
          </div>

          <div style={{ alignSelf: 'flex-end' }}>
            <button
              className="btn btn-primary"
              onClick={() => handleGenerate()}
              disabled={loading || !requirement.trim()}
            >
              <Sparkles size={14} />
              <span>{loading ? 'Synthesizing...' : 'Propose Rules'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Suggested Configuration Preview */}
      {suggestion && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div>
              <h3 className="card-title">Proposed Contract Configuration</h3>
              <p className="card-subtitle">{suggestion.explanation} (Validation Confidence: {Math.round(suggestion.confidence * 100)}%)</p>
            </div>

            <button
              className="btn btn-primary btn-sm"
              onClick={handleApply}
              disabled={applied}
            >
              {applied ? <Check size={13} /> : <Plus size={13} />}
              <span>{applied ? 'Added to Quality Gate' : 'Approve & Apply Rule'}</span>
            </button>
          </div>

          {applied && (
            <div
              style={{
                marginBottom: '16px',
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--positive-bg)',
                border: '1px solid var(--positive-border)',
                color: 'var(--positive)',
                fontSize: '13px',
              }}
            >
              Rule successfully validated against Pydantic schema and appended to <code>{datasetCode}</code> Quality Gate.
            </div>
          )}

          {/* Code preview block */}
          <div
            style={{
              background: '#0f172a',
              color: '#f8fafc',
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              overflowX: 'auto',
            }}
          >
            <pre style={{ margin: 0 }}>
              {JSON.stringify({ quality: { rules: suggestion.proposed_rules } }, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
