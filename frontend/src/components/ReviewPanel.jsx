import React, { useState } from 'react';

const checkpoints = {
  confirm_evidence: '1. Confirm extracted evidence',
  approve_report: '2. Approve the review report',
  approved: 'Review approved',
  rejected: 'Review rejected',
};

export function isDecisionPending(review) {
  return review?.stage === 'confirm_evidence' || review?.stage === 'approve_report';
}

function Findings({ review, pending, busy }) {
  const [evidence, setEvidence] = useState('');
  const [standard, setStandard] = useState('');
  const rows = review.findings.length ? review.findings : review.extraction;
  const evidenced = rows.filter(row => row.evidence).length;
  const standards = [...new Set(rows.map(row => row.standard).filter(Boolean))].sort();
  const visibleRows = new Set(rows.filter(row =>
    (!evidence || Boolean(row.evidence) === (evidence === 'evidenced')) &&
    (!standard || row.standard === standard),
  ));

  return (
    <section className="standards-comparison" aria-labelledby="comparison-title">
      <h2 id="comparison-title">Standards comparison</h2>
      <div className="finding-filters">
        <label>
          Evidence status
          <select value={evidence} onChange={event => setEvidence(event.target.value)}>
            <option value="">All statuses ({rows.length})</option>
            <option value="evidenced">With evidence ({evidenced})</option>
            <option value="gap">Not evidenced ({rows.length - evidenced})</option>
          </select>
        </label>
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
      {review.risk_tier && (
        <details className="evidence-note">
          <summary>How to read design evidence</summary>
          <p><strong>With evidence</strong> means the review cites text in the uploaded design that supports the requirement. Confirming that the control is in place requires implementation evidence.</p>
          <p><strong>Not evidenced</strong> means the review found no supporting quote it could verify in the uploaded design. The control may still be in place, but the evidence gap can raise the assessed risk tier.</p>
        </details>
      )}
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
                {!row.evidence && row.gap_risk && <span>{row.gap_risk} risk</span>}
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
                  <h3>Design evidence</h3>
                  {row.evidence ? (
                    <p><strong>{row.evidence.source}</strong> “{row.evidence.quote}”</p>
                  ) : <p>No verified supporting quote was found.</p>}
                </div>
              </div>
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
  review, busy, downloading, error, onDecision, onDownload, onDownloadReport, onRefresh, onNewReview,
}) {
  const pending = isDecisionPending(review);
  const outcome = { approved: 'Approved', rejected: 'Rejected' }[review.stage];
  const finalReport = outcome && review.risk_tier;
  const findings = <Findings review={review} pending={pending} busy={busy} />;

  return (
    <>
      <div className="sample-header">
        <div>
          <h2 data-status={outcome}>{checkpoints[review.stage]}</h2>
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
          <div className="review-decision">
            <details>
              <summary>Record decision</summary>
              <div className="review-form">
                <div className="review-fields">
                  <label>Reviewer name<input name="reviewer" required maxLength="120" /></label>
                  <label>Decision note (optional)<textarea name="note" maxLength="2000" rows="2" /></label>
                </div>
                <div className="review-actions">
                  <button className="decision-button" data-status="Approved" value="approve" disabled={busy}>
                    {review.stage === 'confirm_evidence' ? 'Confirm evidence' : 'Approve report'}
                  </button>
                  <button className="decision-button" data-status="Rejected" value="reject" disabled={busy}>Reject</button>
                  {error && <button type="button" disabled={busy} onClick={onRefresh}>Refresh review</button>}
                </div>
              </div>
            </details>
            {busy && <p role="status">Processing review…</p>}
            {error && <p className="sample-error" role="alert">{error}</p>}
          </div>
          {review.stage === 'confirm_evidence' && <p>Verify that each cited quote supports its requirement before confirming.</p>}
          {findings}
        </form>
      ) : findings}
      {review.audit.length > 0 && (
        <details className="decision-history">
          <summary>Decision history</summary>
          <ol>
            {review.audit.map(entry => {
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
        </details>
      )}
    </>
  );
}
