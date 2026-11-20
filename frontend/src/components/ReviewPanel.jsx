import React, { useState } from 'react';
import EvidenceGapActions from './EvidenceGapActions.jsx';

const checkpoints = {
  confirm_evidence: 'Confirm extracted evidence',
  approve_report: 'Approve the review report',
  approved: 'Review approved',
  rejected: 'Review rejected',
};

export function isDecisionPending(review) {
  return review?.stage === 'confirm_evidence' || review?.stage === 'approve_report';
}

function DecisionHistory({ audit }) {
  return (
    <details className="decision-history">
      <summary>Decision history</summary>
      {audit.length > 0 ? (
        <ol>
          {audit.map(entry => {
            const status = entry.decision === 'approve' ? 'Approved' : 'Rejected';
            return (
              <li key={entry.checkpoint}>
                <strong>{checkpoints[entry.checkpoint]}</strong> · <span className="status-badge" data-status={status}>{status}</span> by {entry.reviewer}
                {' · '}<time dateTime={entry.at}>{new Date(entry.at).toLocaleString()}</time>
                {entry.note && <p>{entry.note}</p>}
              </li>
            );
          })}
        </ol>
      ) : <p>No decisions recorded yet.</p>}
    </details>
  );
}

function Findings({ review, pending, busy, onSuggest, onRecheck }) {
  const [evidence, setEvidence] = useState('');
  const [standard, setStandard] = useState('');
  const [showEvidenceHelp, setShowEvidenceHelp] = useState(false);
  const rows = review.findings.length ? review.findings : review.extraction;
  const evidenced = rows.filter(row => row.evidence).length;
  const evidenceOptions = [
    { value: '', label: `All statuses (${rows.length})` },
    { value: 'evidenced', label: `With evidence (${evidenced})` },
    { value: 'gap', label: `Not evidenced (${rows.length - evidenced})` },
  ];
  const standards = [...new Set(rows.map(row => row.standard).filter(Boolean))].sort();
  const visibleRows = new Set(rows.filter(row =>
    (!evidence || Boolean(row.evidence) === (evidence === 'evidenced')) &&
    (!standard || row.standard === standard),
  ));

  return (
    <section className="standards-comparison" aria-labelledby="comparison-title">
      <div className="comparison-heading">
        <h2 id="comparison-title">Standards comparison</h2>
        <button
          className="evidence-help"
          type="button"
          aria-label="How to read design evidence"
          aria-expanded={showEvidenceHelp}
          aria-controls="evidence-note"
          onClick={() => setShowEvidenceHelp(open => !open)}
        >?</button>
      </div>
      <div id="evidence-note" className="evidence-note" hidden={!showEvidenceHelp}>
        <h3>How to read design evidence</h3>
        <p><strong>With evidence</strong> means the review cites text from the design or a confirmed supporting document. Confirming that the control is in place requires implementation evidence.</p>
        <p><strong>Not evidenced</strong> means the rule has no verified quote included in the review. The control may still be in place, and the evidence gap can raise the assessed risk tier.</p>
      </div>
      <div className="finding-filters">
        <div className="evidence-filters" role="radiogroup" aria-labelledby="evidence-status-label">
          <span id="evidence-status-label">Evidence status</span>
          {evidenceOptions.map(({ value, label }) => (
            <label key={value}>
              <input
                type="radio"
                name="evidence-status"
                value={value}
                checked={evidence === value}
                onChange={event => setEvidence(event.target.value)}
              />
              {label}
            </label>
          ))}
        </div>
        {standards.length > 0 && (
          <label>
            Standard
            <select value={standard} onChange={event => setStandard(event.target.value)}>
              <option value="">All standards</option>
              {standards.map(id => <option key={id} value={id}>{id}</option>)}
            </select>
          </label>
        )}
      </div>
      <p className="findings-count" role="status">
        {visibleRows.size === 0 ? 'No findings match the current filters.' : `Showing ${visibleRows.size} of ${rows.length} rules`}
      </p>
      <div className="findings">
        {/* Keep filtered rows mounted so their draft comments stay in the decision form. */}
        {rows.map(row => (
          <details className="review-card finding-row" key={row.rule_id} hidden={!visibleRows.has(row)}>
            <summary>
              <span className="finding-summary">
                <span><strong>{row.rule_id}</strong>{row.standard && ` · ${row.standard}`}</span>
                <span className="status-badge" data-status={row.evidence ? 'Evidenced' : 'Not evidenced'}>
                  {row.evidence ? 'Evidenced' : 'Not evidenced'}
                </span>
                {!row.evidence && row.gap_risk && (
                  <span className="status-badge" data-risk={row.gap_risk}>
                    {row.gap_risk[0].toUpperCase() + row.gap_risk.slice(1)} risk
                  </span>
                )}
              </span>
            </summary>
            <div className="finding-details">
              {row.effective_date && <p>Effective {row.effective_date}</p>}
              <div className="finding-comparison">
                <div>
                  <h3>Standard requirement</h3>
                  {row.rule_quote && <p>“{row.rule_quote}”</p>}
                  <p><strong>Evidence required</strong> {row.evidence_required}</p>
                </div>
                <div>
                  <h3>{row.evidence?.document ? 'Supporting evidence' : 'Design evidence'}</h3>
                  {row.evidence ? (
                    <p><strong>{row.evidence.document && `${row.evidence.document} · `}{row.evidence.source}</strong> “{row.evidence.quote}”</p>
                  ) : <p>No verified supporting quote was found.</p>}
                </div>
              </div>
              {!row.evidence && (
                <EvidenceGapActions row={row} busy={busy} canRecheck={review.stage === 'confirm_evidence'}
                  onSuggest={onSuggest} onRecheck={onRecheck} />
              )}
              {review.audit.filter(entry => Object.hasOwn(entry.comments ?? {}, row.rule_id)).map(entry => (
                <div className="finding-comment" key={entry.checkpoint}>
                  <p><strong>{entry.reviewer}</strong> · {checkpoints[entry.checkpoint]}</p>
                  <p className="finding-comment-text">{entry.comments[row.rule_id]}</p>
                </div>
              ))}
              {pending && (
                <details className="finding-comment">
                  <summary aria-label={`Add comment for ${row.rule_id}`}>Add comment</summary>
                  <label>
                    Reviewer comment (optional)
                    <textarea name={`comment:${row.rule_id}`} maxLength={2000} rows={3} disabled={busy} />
                  </label>
                </details>
              )}
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

export default function ReviewPanel({
  review, busy, downloading, error, onDecision, onSuggest, onRecheck,
  onDownload, onDownloadReport, onRefresh, onNewReview,
}) {
  const pending = isDecisionPending(review);
  const outcome = { approved: 'Approved', rejected: 'Rejected' }[review.stage];
  const finalReport = outcome && review.risk_tier;
  const findings = <Findings review={review} pending={pending} busy={busy} onSuggest={onSuggest} onRecheck={onRecheck} />;

  return (
    <>
      <div className="sample-header">
        <div>
          {outcome && <h2 data-status={outcome}>{checkpoints[review.stage]}</h2>}
          <p>{review.filename} · Standards as of {review.as_of}</p>
          <p>Declared tier: <strong>{review.declared_tier}</strong>
            {review.risk_tier && <> · Assessed tier: <strong>{review.risk_tier}</strong></>}
          </p>
        </div>
        <div className="review-actions">
          {finalReport && (
            <button className="primary-link" type="button" disabled={downloading} onClick={onDownloadReport}>
              {downloading ? 'Preparing PDF…' : 'Download final report (PDF)'}
            </button>
          )}
          <button type="button" onClick={onDownload}>Download decision record</button>
          <button type="button" disabled={busy || downloading} onClick={onNewReview}>New review</button>
        </div>
      </div>
      {pending ? (
        <form key={review.stage} onSubmit={onDecision}>
          <div className="review-decision-row">
            <section className="review-decision" aria-labelledby="review-decision-title">
              <h3 id="review-decision-title">Record decision</h3>
              <div className="review-form">
                <div className="review-fields">
                  <label>Reviewer name<input name="reviewer" required maxLength="120" /></label>
                  <label>Decision note (optional)<textarea name="note" maxLength="2000" rows={1} /></label>
                </div>
                <div className="review-actions">
                  <button className="decision-button" data-status="Approved" value="approve" disabled={busy}>
                    {review.stage === 'confirm_evidence' ? 'Confirm evidence' : 'Approve report'}
                  </button>
                  <button className="decision-button" data-status="Rejected" value="reject" disabled={busy}>Reject</button>
                  {error && <button type="button" disabled={busy} onClick={onRefresh}>Refresh review</button>}
                </div>
              </div>
              {busy && <p role="status">Processing review…</p>}
              {error && <p className="sample-error" role="alert">{error}</p>}
            </section>
            <DecisionHistory audit={review.audit} />
          </div>
          {review.stage === 'confirm_evidence' && <p>Verify that each cited quote supports its requirement before confirming.</p>}
          {findings}
        </form>
      ) : (
        <>
          <DecisionHistory audit={review.audit} />
          {findings}
        </>
      )}
    </>
  );
}
