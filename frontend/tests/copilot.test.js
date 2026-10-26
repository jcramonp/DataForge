import test from 'node:test';
import assert from 'node:assert/strict';
import {suggestRulesWithLLM, approveCopilot} from '../src/services/api.js';

test('generation sends scoped intent and explicit provider mode; approval sends exact token', async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({url, body: JSON.parse(options.body)});
    return new Response(JSON.stringify({token:'signed-preview'}), {status:200, headers:{'Content-Type':'application/json'}});
  };
  const payload = {client_code:'c', project_code:'p', source_code:'s', dataset_code:'d', requirement:'required', mode:'llm'};
  await suggestRulesWithLLM(payload);
  assert.deepEqual(calls[0], {url:'/api/copilot/suggest', body:payload});
  assert.equal(calls.length, 1);
  await approveCopilot('signed-preview');
  assert.deepEqual(calls[1], {url:'/api/copilot/approve', body:{token:'signed-preview', approved:true}});
});

test('approval failures are surfaced instead of fabricated success', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({detail:'Active contract changed'}), {status:409, headers:{'Content-Type':'application/json'}});
  await assert.rejects(approveCopilot('old'), /Active contract changed/);
});
