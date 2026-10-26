import test from 'node:test';
import assert from 'node:assert/strict';
import {fetchAssets, fetchOverview, fetchDatasetProfiling, fetchRuns, triggerPipeline} from '../src/services/api.js';
import {sourceKey, sourceScope, datasetScope, matchesSource} from '../src/services/scope.js';

const scope = {client_code:'retail', project_code:'p', source_code:'orders'};
function capture(response = {}) {
  let call;
  globalThis.fetch = async (url, options) => {
    call = {url, options};
    return new Response(JSON.stringify(response), {status:200, headers:{'Content-Type':'application/json'}});
  };
  return () => call;
}

test('assets and overview send the full selected scope', async () => {
  const call = capture([]);
  await fetchAssets({...scope, layer:'quarantine'});
  let url = new URL(call().url, 'http://localhost');
  assert.equal(url.pathname, '/api/assets');
  for (const [key,value] of Object.entries(scope)) assert.equal(url.searchParams.get(key), value);
  assert.equal(url.searchParams.get('layer'), 'quarantine');
  await fetchOverview(scope);
  url = new URL(call().url, 'http://localhost');
  assert.equal(url.pathname, '/api/overview');
  assert.equal(url.searchParams.get('source_code'), 'orders');
});

test('profiling encodes dataset names and disambiguates sources', async () => {
  const call = capture({});
  await fetchDatasetProfiling('orders / daily', scope);
  assert.ok(call().url.startsWith('/api/datasets/orders%20%2F%20daily/profiling?'));
  for (const [key,value] of Object.entries(scope)) {
    assert.equal(new URL(call().url, 'http://localhost').searchParams.get(key), value);
  }
});

test('run history uses selected source and server-side limit', async () => {
  const call = capture([]);
  await fetchRuns(50, scope);
  const query = new URL(call().url, 'http://localhost').searchParams;
  assert.equal(query.get('limit'), '50');
  assert.equal(query.get('source_code'), 'orders');
});

test('trigger serializes an explicit persisted contract, never a dataset string', async () => {
  const call = capture({external_run_id:'run-4'});
  await triggerPipeline({contract_id:4, datasets:[], certification:'evaluate'});
  assert.equal(call().url, '/api/pipelines/trigger');
  assert.equal(call().options.method, 'POST');
  assert.equal(JSON.parse(call().options.body).contract_id, 4);
});

test('API failures and network failures cannot become fabricated successful data', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({detail:'Control-plane database unavailable'}),
    {status:503, headers:{'Content-Type':'application/json'}});
  await assert.rejects(fetchOverview(), (err) => err.status === 503 && /database unavailable/.test(err.message));
  globalThis.fetch = async () => { throw new Error('offline'); };
  await assert.rejects(fetchAssets(), /Unable to reach DataForge API: offline/);
});

test('equal source and dataset codes retain client/project identity', () => {
  const first = {client_code:'c1', project_code:'p', code:'orders'};
  const second = {...first, client_code:'c2'};
  assert.notEqual(sourceKey(first), sourceKey(second));
  assert.equal(matchesSource(first, sourceScope(first)), true);
  assert.equal(matchesSource(second, sourceScope(first)), false);
  assert.deepEqual(datasetScope({client:'c1', project:'p', source_code:'orders'}), sourceScope(first));
  assert.deepEqual(sourceScope(), {});
});
