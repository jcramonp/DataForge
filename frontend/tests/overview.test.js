import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {buildSync} from 'esbuild';

// Render the real component with React's server renderer; no browser mocks.
const code = buildSync({
  stdin: {contents: `import React from 'react';
    import {renderToStaticMarkup} from 'react-dom/server';
    import OverviewView from './src/views/OverviewView.jsx';
    export function render(overview, error) {
      return renderToStaticMarkup(React.createElement(OverviewView, {overview, error}));
    }`, resolveDir: process.cwd(), loader:'jsx'},
  bundle:true, platform:'node', format:'cjs', write:false,
}).outputFiles[0].text;
const compiled = {exports:{}};
new Function('require', 'module', 'exports', code)(createRequire(import.meta.url), compiled, compiled.exports);
const {render} = compiled.exports;

test('empty persisted metrics render zeros without demo fallback values', () => {
  const html = render({summary:{total_sources:0, total_datasets:0, total_rows_processed:0,
    total_quarantined_rows:0, certified_datasets:0, certification_rate_pct:0}, recent_runs:[]});
  assert.match(html, /No persisted runs in this scope/);
  assert.doesNotMatch(html, /359,903|33.3|Demo Pipeline/);
  assert.match(html, /Registered Sources<\/div><div class="kpi-value">0/);
});

test('Gold aggregation reductions are not presented as quarantined rows', () => {
  const html = render({summary:{}, recent_runs:[{run_id:1,dataset:'daily',source:'retail',
    layer:'silver_to_gold', status:'failed',input_rows:null,accepted_rows:null,
    rejected_rows:91,duration_sec:null,created_at:'2026-10-26T12:00:00Z'}]});
  assert.doesNotMatch(html, /91 rows|badge-positive/);
  assert.match(html, /badge-negative/);
});

test('unavailable overview is an error state rather than populated demo cards', () => {
  assert.match(render(null, 'offline'), /Overview unavailable/);
  assert.doesNotMatch(render(null, 'offline'), /kpi-card/);
});
