import React, { useEffect, useState } from 'react';
import { requestReview } from '../api/reviews.js';
import ReviewPanel from './ReviewPanel.jsx';
import UploadPanel from './UploadPanel.jsx';

const storageKey = 'archgovasst.reviewId';

export default function DocumentReview({ apiBaseUrl }) {
  const [review, setReview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const endpoint = `${apiBaseUrl}/api/reviews`;

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
    run(() => requestReview(endpoint, { method: 'POST', body: data }));
  }

  function decide(event) {
    event.preventDefault();
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    const decision = event.nativeEvent.submitter?.value ?? 'approve';
    run(() => requestReview(`${endpoint}/${review.review_id}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...fields, decision, checkpoint: review.stage }),
    }));
  }

  function download() {
    const blob = new Blob([JSON.stringify(review, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `review-${review.review_id}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function startNewReview() {
    sessionStorage.removeItem(storageKey);
    setReview(null);
    setError('');
  }

  return (
    <section id="document-review" className="shell review-section" aria-labelledby="document-review-title">
      <h2 id="document-review-title">Document review</h2>
      {!review && <UploadPanel busy={busy} onSubmit={upload} />}
      {busy && <p role="status">Processing review…</p>}
      {error && <p className="sample-error" role="alert">{error}</p>}
      {review && (
        <ReviewPanel
          review={review}
          busy={busy}
          error={error}
          onDecision={decide}
          onDownload={download}
          onRefresh={() => run(() => requestReview(`${endpoint}/${review.review_id}`))}
          onNewReview={startNewReview}
        />
      )}
    </section>
  );
}
