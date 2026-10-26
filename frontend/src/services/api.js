/**
 * DataForge FastAPI client.
 *
 * The frontend never fabricates successful responses. If FastAPI,
 * PostgreSQL, MinIO or Airflow fail, the error is surfaced to the UI.
 */

const BASE_URL = '/api';


function buildQuery(params = {}) {
  const query = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (
      value !== undefined
      && value !== null
      && value !== ''
    ) {
      query.set(key, String(value));
    }
  });

  const encoded = query.toString();

  return encoded ? `?${encoded}` : '';
}


async function requestJson(path, options = {}) {
  let response;

  try {
    response = await fetch(
      `${BASE_URL}${path}`,
      options,
    );
  } catch (error) {
    throw new Error(
      `Unable to reach DataForge API: ${error.message}`,
    );
  }

  let body = null;

  if (response.status !== 204) {
    const contentType =
      response.headers.get('content-type') || '';

    if (contentType.includes('application/json')) {
      body = await response.json();
    } else {
      body = await response.text();
    }
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;

    if (
      body
      && typeof body === 'object'
      && body.detail
    ) {
      detail = typeof body.detail === 'string'
        ? body.detail
        : JSON.stringify(body.detail);
    } else if (
      typeof body === 'string'
      && body.trim()
    ) {
      detail = body.trim();
    }

    const error = new Error(detail);
    error.status = response.status;
    error.payload = body;

    throw error;
  }

  return body;
}


function jsonOptions(method, payload) {
  return {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  };
}


// ---------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------

export async function fetchOverview(filters = {}) {
  return requestJson(`/overview${buildQuery(filters)}`);
}


// ---------------------------------------------------------------------
// Clients / projects / sources
// ---------------------------------------------------------------------

export async function fetchClients() {
  return requestJson('/clients');
}


export async function fetchProjects(filters = {}) {
  return requestJson(
    `/projects${buildQuery(filters)}`,
  );
}


export async function fetchSources(filters = {}) {
  return requestJson(
    `/sources${buildQuery(filters)}`,
  );
}


export async function testSourceConnection(payload) {
  return requestJson(
    '/sources/test-connection',
    jsonOptions('POST', payload),
  );
}


// ---------------------------------------------------------------------
// Self-service onboarding
// ---------------------------------------------------------------------

export async function registerContract(contract) {
  return requestJson(
    '/onboarding/contracts',
    jsonOptions('POST', contract),
  );
}


export async function fetchActiveContract(
  clientCode,
  projectCode,
  sourceCode,
) {
  return requestJson(
    `/onboarding/contracts/${encodeURIComponent(clientCode)}/`
      + `${encodeURIComponent(projectCode)}/`
      + `${encodeURIComponent(sourceCode)}`,
  );
}


// ---------------------------------------------------------------------
// Datasets / discovery / quality
// ---------------------------------------------------------------------

export async function fetchDatasets(filters = {}) {
  return requestJson(
    `/datasets${buildQuery(filters)}`,
  );
}


export async function fetchDatasetProfiling(
  datasetCode,
  filters = {},
) {
  return requestJson(
    `/datasets/${encodeURIComponent(datasetCode)}/profiling`
      + buildQuery(filters),
  );
}


export async function fetchQualityRules(
  datasetCode,
  filters = {},
) {
  return requestJson(
    `/datasets/${encodeURIComponent(datasetCode)}/quality-rules`
      + buildQuery(filters),
  );
}


export async function fetchQuarantine(
  datasetCode,
  filters = {},
) {
  return requestJson(
    `/datasets/${encodeURIComponent(datasetCode)}/quarantine`
      + buildQuery(filters),
  );
}


// ---------------------------------------------------------------------
// Pipeline orchestration
// ---------------------------------------------------------------------

export async function triggerPipeline(payload) {
  return requestJson(
    '/pipelines/trigger',
    jsonOptions('POST', payload),
  );
}


export async function fetchPipelineRun(dagRunId) {
  return requestJson(
    `/pipelines/runs/${encodeURIComponent(dagRunId)}`,
  );
}


export async function fetchRuns(limit = 50, filters = {}) {
  return requestJson(
    `/runs${buildQuery({ ...filters, limit })}`,
  );
}


// ---------------------------------------------------------------------
// Assets / lineage
// ---------------------------------------------------------------------

export async function fetchAssets(filters = {}) {
  return requestJson(
    `/assets${buildQuery(filters)}`,
  );
}


export async function fetchLineage(filters = {}) {
  return requestJson(
    `/lineage${buildQuery(filters)}`,
  );
}


// ---------------------------------------------------------------------
// Certification / governance
// ---------------------------------------------------------------------

export async function fetchCertification(filters = {}) {
  return requestJson(
    `/certification${buildQuery(filters)}`,
  );
}


export async function fetchCertificationHistory(
  datasetCode,
  filters = {},
) {
  return requestJson(
    `/certification/${encodeURIComponent(datasetCode)}/history`
      + buildQuery(filters),
  );
}


export async function updateCertification(
  datasetCode,
  status,
  options = {},
) {
  const {
    certifiedBy = 'frontend',
    notes = null,
    filters = {},
  } = options;

  return requestJson(
    `/certification/${encodeURIComponent(datasetCode)}`
      + buildQuery(filters),
    jsonOptions(
      'POST',
      {
        status,
        certified_by: certifiedBy,
        notes,
      },
    ),
  );
}


// ---------------------------------------------------------------------
// Validated copilot: generation never persists; approval is a separate request.
export async function suggestRulesWithLLM(payload) {
  return requestJson('/copilot/suggest', jsonOptions('POST', payload));
}
export async function approveCopilot(token) {
  return requestJson('/copilot/approve', jsonOptions('POST', {token, approved: true}));
}
