import React, { useEffect, useState } from 'react';
import { requestGapGuidance, requestReportPdf, requestReview } from '../api/reviews.js';
import ReviewPanel, { isDecisionPending } from './ReviewPanel.jsx';
import ReviewProgress from './ReviewProgress.jsx';
import UploadPanel from './UploadPanel.jsx';

const storageKey = 'archgovasst.reviewId';

function saveDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function DocumentReview({ apiBaseUrl }) {
  const [review, setReview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');
  const endpoint = `${apiBaseUrl}/api/reviews`;
  const decisionPending = isDecisionPending(review);

  useEffect(() => {
    const previous = sessionStorage.getItem(storageKey);
    if (!previous) return;
    const controller = new AbortController();
    setBusy(true);
    requestReview(`${endpoint}/${previous}`, {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
    }).then(setReview).catch(error => {
      if (controller.signal.aborted) return;
      if (error.status === 404) {
        sessionStorage.removeItem(storageKey);
        setError('The previous review is no longer available. Upload the document to start again.');
      } else {
        setError(error.message);
      }
    }).finally(() => {
      if (!controller.signal.aborted) setBusy(false);
    });
    return () => controller.abort();
  }, [endpoint]);

  async function run(action) {
    setBusy(true);
    setError('');
    try {
      const updated = await action();
      sessionStorage.setItem(storageKey, updated.review_id);
      setReview(updated);
      return updated;
    } catch (error) {
      setError(error.name === 'TimeoutError' ? 'The review request timed out.' : error.message);
    } finally {
      setBusy(false);
    }
  }

  function upload(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (!data.get('as_of')) data.delete('as_of');
    run(() => requestReview(endpoint, {
      method: 'POST', body: data, signal: AbortSignal.timeout(230000),
    }));
  }

  function decide(event) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const comments = Object.fromEntries(
      [...fields.entries()]
        .filter(([name, value]) => name.startsWith('comment:') && value.trim())
        .map(([name, value]) => [name.slice('comment:'.length), value.trim()]),
    );
    const decision = event.nativeEvent.submitter?.value ?? 'approve';
    const supportingEvidence = decision === 'approve' ? Object.fromEntries(
      [...fields.entries()]
        .filter(([name]) => name.startsWith('supporting-evidence:'))
        .map(([name, value]) => [name.slice('supporting-evidence:'.length), value]),
    ) : {};
    run(() => requestReview(`${endpoint}/${review.review_id}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reviewer: fields.get('reviewer'),
        note: fields.get('note'),
        comments,
        supporting_evidence: supportingEvidence,
        decision,
        checkpoint: review.stage,
      }),
    }));
  }

  function recheck(ruleId, file) {
    const body = new FormData();
    body.set('rule_id', ruleId);
    body.set('document', file);
    return run(() => requestReview(`${endpoint}/${review.review_id}/supporting-evidence`, {
      method: 'POST', body,
    }));
  }

  function download() {
    const blob = new Blob([JSON.stringify(review, null, 2)], { type: 'application/json' });
    saveDownload(blob, `review-${review.review_id}.json`);
  }

  async function downloadReport() {
    setDownloading(true);
    setError('');
    try {
      const report = await requestReportPdf(`${endpoint}/${review.review_id}/report.pdf`);
      saveDownload(report, `review-${review.review_id}.pdf`);
    } catch (error) {
      setError(error.name === 'TimeoutError' ? 'The PDF download timed out.' : error.message);
    } finally {
      setDownloading(false);
    }
  }

  function startNewReview() {
    sessionStorage.removeItem(storageKey);
    setReview(null);
    setError('');
  }

  return (
    <section id="document-review" className="shell review-section document-review" aria-labelledby="document-review-title">
      <h1 id="document-review-title">Review against governance standards</h1>
      <ReviewProgress review={review} />
      {!review && <p>Upload a design to check every applicable rule. The review searches relevant passages first and checks the full design for rules still missing a verified quote.</p>}
      {!review && <UploadPanel busy={busy} onSubmit={upload} />}
      {!decisionPending && busy && <p role="status">Processing review…</p>}
      {!decisionPending && error && <p className="sample-error" role="alert">{error}</p>}
      {review && (
        <ReviewPanel
          review={review}
          key={review.review_id}
          busy={busy}
          downloading={downloading}
          error={error}
          onDecision={decide}
          onSuggest={ruleId => requestGapGuidance(`${endpoint}/${review.review_id}/gap-guidance`, ruleId)}
          onRecheck={recheck}
          onDownload={download}
          onDownloadReport={downloadReport}
          onRefresh={() => run(() => requestReview(`${endpoint}/${review.review_id}`))}
          onNewReview={startNewReview}
        />
      )}
    </section>
  );
}
