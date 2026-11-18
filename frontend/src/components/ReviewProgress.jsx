import React from 'react';

export default function ReviewProgress({ review }) {
  const decisions = Object.fromEntries((review?.audit ?? []).map(entry => [entry.checkpoint, entry.decision]));
  const current = review?.stage ?? 'upload';
  const stopped = current === 'rejected';
  const stages = [
    { id: 'upload', label: 'Upload design and search for evidence', complete: Boolean(review) },
    { id: 'confirm_evidence', label: 'Confirm extracted evidence' },
    { id: 'assess_risk', label: 'Compare standards and assess risk', complete: Boolean(review?.risk_tier) },
    { id: 'approve_report', label: 'Approve review report' },
  ];
  const currentIndex = stages.findIndex(stage => stage.id === current);
  const next = currentIndex >= 0 ? stages[currentIndex + 1]?.id : undefined;

  function statusFor(stage) {
    if (stage.complete) return 'Complete';
    if (decisions[stage.id] === 'approve') return 'Passed';
    if (decisions[stage.id] === 'reject') return 'Rejected';
    if (stage.id === current) return 'Current';
    if (stopped) return 'Not reached';
    if (stage.id === next) return 'Next';
    return 'Upcoming';
  }

  return (
    <section className="review-progress" aria-labelledby="review-progress-title">
      <h2 id="review-progress-title">Review progress</h2>
      <ol role="list">
        {stages.map(stage => {
          const status = statusFor(stage);
          return (
            <li key={stage.id} data-status={status} aria-current={status === 'Current' ? 'step' : undefined}>
              <strong>{stage.label}</strong>
              <span className="status-badge">{status}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
