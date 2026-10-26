import React, { useEffect, useRef, useState } from 'react';
import { fetchSources, suggestRulesWithLLM, approveCopilot } from '../services/api';
import { sourceScope, sourceKey } from '../services/scope';

export default function CopilotView() {
  const [sources, setSources] = useState([]);
  const [source, setSource] = useState('');
  const [dataset, setDataset] = useState('');
  const [requirement, setRequirement] = useState('');
  const [mode, setMode] = useState('llm');
  const [proposal, setProposal] = useState(null);
  const [reviewed, setReviewed] = useState(false);
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const generation = useRef(0);
  const selected = sources.find(s => sourceKey(s) === source);
  const datasets = selected?.datasets || [];
  useEffect(() => { let active = true;
    fetchSources().then(rows => { if (active) setSources(rows); })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; generation.current++; };
  }, []);
  function invalidate() {
    generation.current++; setProposal(null); setReviewed(false); setSaved(null); setError('');
  }
  async function generate() {
    invalidate(); const current = generation.current; setBusy(true);
    try {
      const result = await suggestRulesWithLLM({...sourceScope(selected), dataset_code: dataset, requirement, mode});
      if (current === generation.current) setProposal(result);
    } catch(e) { if (current === generation.current) setError(e.message); }
    finally { setBusy(false); }
  }
  async function approve() {
    setBusy(true); setError('');
    try { setSaved(await approveCopilot(proposal.token)); }
    catch(e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <div className="card">
    <h2>Configuration Copilot</h2>
    <p>Review supported transformations and quality rules before saving a contract revision. Execution remains a separate pipeline action.</p>
    <label>Source <select aria-label="Source" value={source} disabled={busy} onChange={e => {invalidate(); setSource(e.target.value); setDataset('');}}>
      <option value="">Select a registered source</option>
      {sources.map(s => <option key={sourceKey(s)} value={sourceKey(s)}>{s.client_code} / {s.project_code} / {s.code}</option>)}
    </select></label>
    <label>Dataset <select aria-label="Dataset" value={dataset} disabled={busy} onChange={e => {invalidate(); setDataset(e.target.value);}}>
      <option value="">Select dataset</option>
      {datasets.map(d => <option key={d.code} value={d.code}>{d.code}</option>)}
    </select></label>
    <label>Provider <select aria-label="Provider" value={mode} disabled={busy} onChange={e => {invalidate(); setMode(e.target.value);}}>
      <option value="llm">Real LLM — Amazon Bedrock</option>
      <option value="deterministic">Deterministic fallback — no LLM</option>
    </select></label>
    <p>The active schema, existing rules and available profiling summary are included automatically.</p>
    <textarea aria-label="Requirement" rows={4} style={{width: '100%'}} value={requirement} disabled={busy}
      placeholder="El peso, cuando está presente, debe ser mayor a cero; severity critical."
      onChange={e => {invalidate(); setRequirement(e.target.value);}} />
    <button className="btn btn-primary" disabled={busy || !selected || !dataset || !requirement.trim()} onClick={generate}>
      {busy ? 'Working…' : 'Generate proposal'}
    </button>
    {error && <p role="alert">{error}</p>}
    {proposal && <section>
      <h3>Review proposal — {proposal.provider}</h3>
      <p>{proposal.profile_id ? `Profiling #${proposal.profile_id}` : 'No profiling available; schema context only.'}</p>
      <p>{proposal.proposal.explanation}</p>
      <pre style={{overflowX:'auto'}}>{JSON.stringify(proposal.proposal, null, 2)}</pre>
      <details><summary>Complete validated contract to persist</summary><pre style={{overflowX:'auto'}}>{JSON.stringify(proposal.contract, null, 2)}</pre></details>
      <label><input type="checkbox" checked={reviewed} disabled={busy || !!saved} onChange={e => setReviewed(e.target.checked)} /> I reviewed this proposal and approve saving this configuration.</label>
      <button className="btn btn-primary" disabled={!reviewed || busy || !!saved || (!proposal.proposal.rules.length && !proposal.proposal.transformations.length)} onClick={approve}>Approve and save revision</button>
      {saved && <p role="status">Saved contract #{saved.contract_id}, revision {saved.revision}. Run it separately through the pipeline controls.</p>}
    </section>}
  </div>;
}
