import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {buildSync} from 'esbuild';
const code = buildSync({stdin:{contents:`import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import CopilotView from './src/views/CopilotView.jsx';
export const html = renderToStaticMarkup(React.createElement(CopilotView));`,
resolveDir:process.cwd(),loader:'jsx'},bundle:true,platform:'node',format:'cjs',write:false}).outputFiles[0].text;
const compiled = {exports:{}};
new Function('require','module','exports',code)(createRequire(import.meta.url),compiled,compiled.exports);
test('copilot renders explicit provider choices and cannot approve without a proposal', () => {
  const html = compiled.exports.html;
  assert.match(html, /Real LLM/);
  assert.match(html, /Deterministic fallback/);
  assert.match(html, /disabled="">Generate proposal/);
  assert.doesNotMatch(html, /Added to Quality Gate|Saved contract|Approve and save revision/);
});
