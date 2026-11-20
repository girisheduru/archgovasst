import React, { useState } from 'react';

export default function EvidenceGapActions({ row, canRecheck, busy, onSuggest, onRecheck }) {
  const [guidance, setGuidance] = useState(null);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestionError, setSuggestionError] = useState('');
  const [file, setFile] = useState(null);
  const [recheckMessage, setRecheckMessage] = useState('');
  const candidate = row.supporting_candidate;

  async function suggest() {
    setSuggestionError('');
    setSuggesting(true);
    try {
      setGuidance(await onSuggest(row.rule_id));
    } catch (error) {
      setSuggestionError(error.name === 'TimeoutError' ? 'The suggestion request timed out.' : error.message);
    } finally {
      setSuggesting(false);
    }
  }

  async function recheck() {
    setRecheckMessage('Checking the supporting document…');
    const updated = await onRecheck(row.rule_id, file);
    const found = updated?.extraction.find(item => item.rule_id === row.rule_id)?.supporting_candidate;
    setRecheckMessage(updated && found?.id === candidate?.id
      ? 'No verified supporting quote was found in this file.'
      : '');
  }

  return (
    <div className="evidence-gap-actions">
      {!guidance && (
        <button type="button" onClick={suggest} disabled={busy || suggesting}>
          {suggesting ? 'Drafting suggestion…' : 'Suggest next step'}
        </button>
      )}
      {suggestionError && <p className="sample-error" role="alert">{suggestionError}</p>}
      {guidance && (
        <div aria-live="polite">
          <h3>AI suggestion</h3>
          <p><strong>Evidence to clarify</strong> {guidance.missing_evidence}</p>
          <p><strong>Suggested next step</strong> {guidance.next_step}</p>
        </div>
      )}
      {canRecheck && (
        <details className="finding-comment">
          <summary>Recheck with a supporting document</summary>
          <label>
            Supporting document (PDF or Word)
            <input type="file" accept=".pdf,.docx" disabled={busy} onChange={event => {
              setFile(event.target.files[0] ?? null);
              setRecheckMessage('');
            }} />
          </label>
          <button type="button" disabled={!file || busy} onClick={recheck}>Recheck this rule</button>
          {recheckMessage && <p role="status">{recheckMessage}</p>}
        </details>
      )}
      {canRecheck && candidate && (
        <div className="finding-comment">
          <h3>Supporting quote awaiting confirmation</h3>
          <p><strong>{candidate.evidence.document} · {candidate.evidence.source}</strong> “{candidate.evidence.quote}”</p>
          <label className="supporting-evidence-selection">
            <input key={candidate.id} type="checkbox" name={`supporting-evidence:${row.rule_id}`}
              value={candidate.id} disabled={busy} />
            Include this quote when I confirm evidence
          </label>
        </div>
      )}
    </div>
  );
}
