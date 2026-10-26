import test from 'node:test';
import assert from 'node:assert/strict';
import { monitorPipeline, isTerminalRun } from '../src/services/pipeline-monitor.js';

test('temporary failures recover while querying the same accepted run', async () => {
  const calls = [];
  const warnings = [];
  const states = [];
  const responses = [Object.assign(new Error('unavailable'), {status: 503}),
    {state: 'running'}, new Error('offline'), {state: 'success'}];
  const result = await monitorPipeline('accepted-42', {
    fetchStatus: async (id) => {
      calls.push(id);
      const response = responses.shift();
      if (response instanceof Error) throw response;
      return response;
    },
    onStatus: (status) => states.push(status.state),
    onWarning: (warning) => warnings.push(warning),
    wait: async () => {},
  });
  assert.equal(result.state, 'success');
  assert.deepEqual(calls, Array(4).fill('accepted-42'));
  assert.deepEqual(states, ['running', 'success']);
  assert.ok(warnings.some((warning) => warning.includes('may still be running')));
  assert.equal(warnings.at(-1), '');
});

test('exhaustion preserves unknown outcome instead of reporting a pipeline failure', async () => {
  const result = await monitorPipeline('accepted', {
    fetchStatus: async () => { throw Object.assign(new Error('unavailable'), {status: 503}); },
    attempts: 2, wait: async () => {},
  });
  assert.equal(result, null);
  assert.equal(isTerminalRun(result), false);
});

test('terminal failure is returned; permission failures are not retried', async () => {
  const failed = await monitorPipeline('run', {fetchStatus: async () => ({state: 'failed'})});
  assert.equal(isTerminalRun(failed), true);
  let calls = 0;
  await assert.rejects(monitorPipeline('run', {
    fetchStatus: async () => { calls += 1; throw Object.assign(new Error('forbidden'), {status: 403}); },
  }), /forbidden/);
  assert.equal(calls, 1);
});
