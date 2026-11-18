import React from 'react';

const checkpoints = {
  confirm_evidence: '1. Confirm extracted evidence',
  approve_report: '2. Approve the review report',
  approved: 'Review approved',
  rejected: 'Review rejected',
};

function Findings({ review }) {
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
                {row.evidence ? (
                  <p><strong>{row.evidence.source}</strong> “{row.evidence.quote}”</p>
                ) : (
                  <p><strong>Not evidenced.</strong>{row.gap_risk && ` ${row.gap_risk} risk evidence gap.`}</p>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function ReviewPanel({ review, busy, error, onDecision, onDownload, onRefresh, onNewReview }) {
  const pending = ['confirm_evidence', 'approve_report'].includes(review.stage);

  return (
    <>
      <div className="sample-header">
        <div>
          <h2>{checkpoints[review.stage]}</h2>
          <p>{review.filename} · Standards as of {review.as_of}</p>
          <p>Declared tier: <strong>{review.declared_tier}</strong>
            {review.risk_tier && <> · Assessed tier: <strong>{review.risk_tier}</strong></>}
          </p>
        </div>
        <div className="review-actions">
          <button type="button" onClick={onDownload}>Download decision record</button>
          <button type="button" disabled={busy} onClick={onNewReview}>New review</button>
        </div>
      </div>
      {review.stage === 'confirm_evidence' && <p>Every applicable rule was checked. Verify that each cited quote supports the requirement before confirming.</p>}
      <Findings review={review} />
      {pending && (
        <form key={review.stage} className="review-form review-card" onSubmit={onDecision}>
          <label>Reviewer name<input name="reviewer" required maxLength="120" /></label>
          <label>Decision note (optional)<textarea name="note" maxLength="2000" rows="3" /></label>
          <div className="review-actions">
            <button className="primary-link" value="approve" disabled={busy}>
              {review.stage === 'confirm_evidence' ? 'Confirm evidence' : 'Approve report'}
            </button>
            <button value="reject" disabled={busy}>Reject</button>
            {error && <button type="button" disabled={busy} onClick={onRefresh}>Refresh review</button>}
          </div>
        </form>
      )}
      {review.audit.length > 0 && (
        <div className="decision-history">
          <h3>Decision history</h3>
          <ol>
            {review.audit.map(entry => (
              <li key={entry.checkpoint}>
                <strong>{checkpoints[entry.checkpoint]}</strong> · {entry.decision === 'approve' ? 'Approved' : 'Rejected'} by {entry.reviewer}
                {' · '}<time dateTime={entry.at}>{new Date(entry.at).toLocaleString()}</time>
                {entry.note && <p>{entry.note}</p>}
              </li>
            ))}
          </ol>
        </div>
      )}
    </>
  );
}
