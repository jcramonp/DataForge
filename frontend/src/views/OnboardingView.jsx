import React, { useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Database,
  PlugZap,
  Save,
} from 'lucide-react';

import {
  registerContract,
  testSourceConnection,
} from '../services/api';


const DEFAULT_SCHEMA = JSON.stringify(
  [
    {
      name: 'order_id',
      type: 'string',
      nullable: false,
      classification: 'internal',
    },
    {
      name: 'customer_email',
      type: 'string',
      nullable: true,
      classification: 'confidential',
    },
    {
      name: 'amount',
      type: 'float',
      nullable: false,
      classification: 'internal',
    },
    {
      name: 'status',
      type: 'string',
      nullable: false,
      classification: 'internal',
    },
    {
      name: 'created_at',
      type: 'date',
      nullable: false,
      classification: 'internal',
    },
  ],
  null,
  2,
);


const INITIAL_FORM = {
  client_code: 'ui-demo',
  client_name: 'UI Demo Client',

  project_code: 'self-service',
  project_name: 'Self-Service Data Project',

  source_code: 'retail-file-ui',
  source_name: 'Retail Orders CSV',
  source_type: 'file',
  connection_reference: '',

  dataset_code: 'orders_ui',
  dataset_name: 'Retail Orders UI',
  owner: 'DataForge',
  classification: 'internal',

  target_object: 'tests/fixtures/e2e/orders.csv',
  primary_keys: 'order_id',

  schema_json: DEFAULT_SCHEMA,
};


function sourceObjectFromForm(form) {
  if (form.source_type === 'file') {
    const lower = form.target_object.toLowerCase();

    let format = 'csv';

    if (lower.endsWith('.json')) {
      format = 'json';
    } else if (lower.endsWith('.parquet')) {
      format = 'parquet';
    }

    return {
      path: form.target_object,
      format,
    };
  }

  if (form.source_type === 'postgresql') {
    const raw = form.target_object.trim();

    if (raw.toLowerCase().startsWith('select ')) {
      return {
        query: raw,
      };
    }

    const parts = raw.split('.');

    if (parts.length >= 2) {
      return {
        schema: parts.slice(0, -1).join('.'),
        table: parts[parts.length - 1],
      };
    }

    return {
      table: raw,
    };
  }

  return {
    endpoint: form.target_object,
    method: 'GET',
    timeout_seconds: 30,
  };
}


function buildContract(form) {
  const schema = JSON.parse(form.schema_json);

  if (!Array.isArray(schema) || schema.length === 0) {
    throw new Error(
      'Schema JSON must contain at least one column.',
    );
  }

  const primaryKeys = form.primary_keys
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);

  return {
    contract_version: '1.0',

    client: {
      code: form.client_code.trim(),
      name: form.client_name.trim(),
    },

    project: {
      code: form.project_code.trim(),
      name: form.project_name.trim(),
    },

    source: {
      code: form.source_code.trim(),
      name: form.source_name.trim(),
      type: form.source_type,
      connection_reference:
        form.connection_reference.trim() || null,
    },

    datasets: [
      {
        code: form.dataset_code.trim(),
        name: form.dataset_name.trim(),
        owner: form.owner.trim() || null,
        classification: form.classification,

        source_object: sourceObjectFromForm(form),

        schema,

        keys: {
          primary: primaryKeys,
          foreign: [],
        },

        silver: {
          transformations: [],
        },

        quality: {
          rules: [],
        },
      },
    ],

    gold: [],
  };
}


function Field({
  label,
  value,
  onChange,
  type = 'text',
  required = true,
}) {
  return (
    <div>
      <label
        style={{
          display: 'block',
          fontSize: '12px',
          fontWeight: 600,
          color: '#374151',
          marginBottom: '6px',
        }}
      >
        {label}
      </label>

      <input
        type={type}
        value={value}
        onChange={onChange}
        required={required}
        style={{
          width: '100%',
          padding: '8px 12px',
          borderRadius: '4px',
          border: '1px solid #d1d5db',
        }}
      />
    </div>
  );
}


export default function OnboardingView({ onRegistered }) {
  const [form, setForm] = useState(INITIAL_FORM);

  const [testing, setTesting] = useState(false);
  const [registering, setRegistering] = useState(false);

  const [testResult, setTestResult] = useState(null);
  const [registration, setRegistration] = useState(null);
  const [error, setError] = useState(null);


  const update = (field, value) => {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));

    setRegistration(null);
    setError(null);
  };


  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);

    try {
      const result = await testSourceConnection({
        source_type: form.source_type,
        connection_reference:
          form.connection_reference || null,
        target_object: form.target_object,
      });

      setTestResult(result);
    } catch (err) {
      setTestResult({
        success: false,
        message: err.message,
      });
    } finally {
      setTesting(false);
    }
  };


  const handleRegister = async (event) => {
    event.preventDefault();

    setRegistering(true);
    setRegistration(null);
    setError(null);

    try {
      const contract = buildContract(form);

      const result = await registerContract(contract);

      setRegistration(result);
      onRegistered?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setRegistering(false);
    }
  };


  return (
    <div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) 340px',
          gap: '20px',
          alignItems: 'start',
        }}
      >
        <div className="card">
          <h2 className="card-title">
            Self-Service Data Source Onboarding
          </h2>

          <p className="card-subtitle">
            Register client, project, source and dataset metadata
            through the FastAPI control plane.
          </p>

          <form onSubmit={handleRegister}>
            <h3
              style={{
                fontSize: '13px',
                marginTop: '20px',
                marginBottom: '12px',
              }}
            >
              Client & Project
            </h3>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
              }}
            >
              <Field
                label="Client Code"
                value={form.client_code}
                onChange={(e) => update(
                  'client_code',
                  e.target.value,
                )}
              />

              <Field
                label="Client Name"
                value={form.client_name}
                onChange={(e) => update(
                  'client_name',
                  e.target.value,
                )}
              />

              <Field
                label="Project Code"
                value={form.project_code}
                onChange={(e) => update(
                  'project_code',
                  e.target.value,
                )}
              />

              <Field
                label="Project Name"
                value={form.project_name}
                onChange={(e) => update(
                  'project_name',
                  e.target.value,
                )}
              />
            </div>


            <h3
              style={{
                fontSize: '13px',
                marginTop: '24px',
                marginBottom: '12px',
              }}
            >
              Source
            </h3>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
              }}
            >
              <Field
                label="Source Code"
                value={form.source_code}
                onChange={(e) => update(
                  'source_code',
                  e.target.value,
                )}
              />

              <Field
                label="Source Name"
                value={form.source_name}
                onChange={(e) => update(
                  'source_name',
                  e.target.value,
                )}
              />

              <div>
                <label
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 600,
                    color: '#374151',
                    marginBottom: '6px',
                  }}
                >
                  Connector Type
                </label>

                <select
                  value={form.source_type}
                  onChange={(e) => update(
                    'source_type',
                    e.target.value,
                  )}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '4px',
                    border: '1px solid #d1d5db',
                    background: '#fff',
                  }}
                >
                  <option value="file">
                    File / CSV / JSON / Parquet
                  </option>

                  <option value="postgresql">
                    PostgreSQL
                  </option>

                  <option value="rest">
                    REST API
                  </option>
                </select>
              </div>

              <Field
                label="Connection Reference"
                value={form.connection_reference}
                onChange={(e) => update(
                  'connection_reference',
                  e.target.value,
                )}
                required={false}
              />
            </div>

            <div style={{ marginTop: '12px' }}>
              <Field
                label={
                  form.source_type === 'file'
                    ? 'File Path'
                    : form.source_type === 'postgresql'
                      ? 'Table (schema.table) or SELECT query'
                      : 'REST Endpoint'
                }
                value={form.target_object}
                onChange={(e) => update(
                  'target_object',
                  e.target.value,
                )}
              />
            </div>

            <div
              style={{
                marginTop: '12px',
                display: 'flex',
                gap: '10px',
                alignItems: 'center',
              }}
            >
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleTestConnection}
                disabled={testing}
              >
                <PlugZap size={14} />

                {testing
                  ? 'Testing...'
                  : 'Test Connection'}
              </button>

              {testResult && (
                <span
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '12px',
                    color: testResult.success
                      ? 'var(--positive)'
                      : 'var(--negative)',
                  }}
                >
                  {testResult.success
                    ? <CheckCircle2 size={14} />
                    : <AlertCircle size={14} />}

                  {testResult.message}
                </span>
              )}
            </div>


            <h3
              style={{
                fontSize: '13px',
                marginTop: '24px',
                marginBottom: '12px',
              }}
            >
              Dataset Contract
            </h3>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
              }}
            >
              <Field
                label="Dataset Code"
                value={form.dataset_code}
                onChange={(e) => update(
                  'dataset_code',
                  e.target.value,
                )}
              />

              <Field
                label="Dataset Name"
                value={form.dataset_name}
                onChange={(e) => update(
                  'dataset_name',
                  e.target.value,
                )}
              />

              <Field
                label="Owner"
                value={form.owner}
                onChange={(e) => update(
                  'owner',
                  e.target.value,
                )}
              />

              <div>
                <label
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 600,
                    color: '#374151',
                    marginBottom: '6px',
                  }}
                >
                  Classification
                </label>

                <select
                  value={form.classification}
                  onChange={(e) => update(
                    'classification',
                    e.target.value,
                  )}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '4px',
                    border: '1px solid #d1d5db',
                    background: '#fff',
                  }}
                >
                  <option value="public">Public</option>
                  <option value="internal">Internal</option>
                  <option value="confidential">
                    Confidential
                  </option>
                  <option value="restricted">
                    Restricted
                  </option>
                </select>
              </div>
            </div>

            <div style={{ marginTop: '12px' }}>
              <Field
                label="Primary Keys (comma separated)"
                value={form.primary_keys}
                onChange={(e) => update(
                  'primary_keys',
                  e.target.value,
                )}
                required={false}
              />
            </div>

            <div style={{ marginTop: '12px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#374151',
                  marginBottom: '6px',
                }}
              >
                Schema JSON
              </label>

              <textarea
                value={form.schema_json}
                onChange={(e) => update(
                  'schema_json',
                  e.target.value,
                )}
                rows={16}
                spellCheck={false}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '4px',
                  border: '1px solid #d1d5db',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                  resize: 'vertical',
                }}
              />
            </div>


            {error && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '10px 12px',
                  borderRadius: '5px',
                  background: 'var(--negative-bg)',
                  color: 'var(--negative)',
                  fontSize: '12px',
                  display: 'flex',
                  gap: '8px',
                  alignItems: 'center',
                }}
              >
                <AlertCircle size={14} />
                {error}
              </div>
            )}


            <div
              style={{
                marginTop: '18px',
                display: 'flex',
                justifyContent: 'flex-end',
              }}
            >
              <button
                className="btn btn-primary"
                type="submit"
                disabled={registering}
              >
                <Save size={14} />

                {registering
                  ? 'Registering...'
                  : 'Register Contract'}
              </button>
            </div>
          </form>
        </div>


        <div className="card">
          <h3 className="card-title">
            Control Plane Result
          </h3>

          <p className="card-subtitle">
            Registration is persisted by FastAPI in PostgreSQL.
          </p>

          {!registration && (
            <div
              style={{
                color: 'var(--muted)',
                fontSize: '12px',
                lineHeight: 1.6,
              }}
            >
              <Database
                size={30}
                style={{ marginBottom: '10px' }}
              />

              <div>
                No contract has been registered in this
                session yet.
              </div>
            </div>
          )}

          {registration && (
            <div
              style={{
                fontSize: '12px',
                lineHeight: 1.7,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: 'var(--positive)',
                  fontWeight: 600,
                  marginBottom: '12px',
                }}
              >
                <CheckCircle2 size={15} />
                Contract persisted successfully
              </div>

              <div>
                Contract ID:{' '}
                <strong>{registration.contract_id}</strong>
              </div>

              <div>
                Revision:{' '}
                <strong>{registration.revision}</strong>
              </div>

              <div>
                Status:{' '}
                <strong>{registration.status}</strong>
              </div>

              <div>
                Created:{' '}
                <strong>
                  {registration.created ? 'yes' : 'no'}
                </strong>
              </div>

              <div>
                Reactivated:{' '}
                <strong>
                  {registration.reactivated ? 'yes' : 'no'}
                </strong>
              </div>

              <div
                style={{
                  marginTop: '10px',
                  wordBreak: 'break-all',
                }}
              >
                SHA-256:
                <div className="mono">
                  {registration.contract_hash}
                </div>
              </div>

              <div style={{ marginTop: '12px' }}>
                Datasets:
                {(registration.datasets || []).map(
                  (dataset) => (
                    <div
                      key={dataset.dataset_id}
                      className="mono"
                    >
                      {dataset.dataset_code}
                      {' '}
                      (id={dataset.dataset_id})
                    </div>
                  ),
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
