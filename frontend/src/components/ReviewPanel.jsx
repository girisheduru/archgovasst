import React from 'react';

const checkpoints = {
  confirm_evidence: '1. Confirm extracted evidence',
  approve_report: '2. Approve the review report',
  approved: 'Review approved',
  rejected: 'Review rejected',
};

function Findings({ review, pending, busy }) {
  const rows = review.findings.length ? review.findings : review.extraction;
  const evidenced = rows.filter(row => row.evidence).length;

  return (
    <section aria-labelledby="comparison-title">
      <h2 id="comparison-title">Standards comparison</h2>
      <p>{rows.length} rules reviewed · {evidenced} with evidence · {rows.length - evidenced} not evidenced</p>
      {review.risk_tier && (
        <aside className="evidence-note" aria-label="How to read design evidence">
          <p><strong>How to read design evidence</strong></p>
          <p><strong>With evidence</strong> means the review cites text in the uploaded design that supports the requirement. Confirming that the control is in place requires implementation evidence.</p>
          <p><strong>Not evidenced</strong> means the review found no supporting quote it could verify in the uploaded design. The control may still be in place, but the evidence gap can raise the assessed risk tier.</p>
        </aside>
      )}
      <div className="findings">
        {rows.map(row => (
          <article className="review-card" key={row.rule_id}>
            <h3>{row.rule_id}{row.standard && ` · ${row.standard}`}</h3>
            {row.effective_date && <p>Effective {row.effective_date}</p>}
            <div className="finding-comparison">
              <div>
                <h4>Standard requirement</h4>
                {row.rule_quote && <p>“{row.rule_quote}”</p>}
                <p><strong>Evidence required</strong> {row.evidence_required}</p>
              </div>
              <div>
                <h4>Design evidence</h4>
                <span className="status-badge" data-status={row.evidence ? 'Evidenced' : 'Not evidenced'}>
                  {row.evidence ? 'Evidenced' : 'Not evidenced'}
                </span>
                {row.evidence ? (
                  <p><strong>{row.evidence.source}</strong> “{row.evidence.quote}”</p>
                ) : row.gap_risk && <p>{row.gap_risk} risk evidence gap.</p>}
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
          </article>
        ))}
      </div>
    </section>
  );
}

export default function ReviewPanel({
  review, busy, downloading, error, onDecision, onDownload, onDownloadReport, onRefresh, onNewReview,
}) {
  const pending = ['confirm_evidence', 'approve_report'].includes(review.stage);
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
      {review.stage === 'confirm_evidence' && <p>Every applicable rule was checked. Verify that each cited quote supports the requirement before confirming.</p>}
      {pending ? (
        <form key={review.stage} onSubmit={onDecision}>
          {findings}
          <div className="review-form review-card">
            <label>Reviewer name<input name="reviewer" required maxLength="120" /></label>
            <label>Decision note (optional)<textarea name="note" maxLength="2000" rows="3" /></label>
            <div className="review-actions">
              <button className="decision-button" data-status="Approved" value="approve" disabled={busy}>
                {review.stage === 'confirm_evidence' ? 'Confirm evidence' : 'Approve report'}
              </button>
              <button className="decision-button" data-status="Rejected" value="reject" disabled={busy}>Reject</button>
              {error && <button type="button" disabled={busy} onClick={onRefresh}>Refresh review</button>}
            </div>
          </div>
        </form>
      ) : findings}
      {review.audit.length > 0 && (
        <div className="decision-history">
          <h3>Decision history</h3>
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
        </div>
      )}
    </>
  );
}
