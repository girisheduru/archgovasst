import React, { useState } from 'react';

export default function SampleReview({ apiBaseUrl }) {
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function loadReview() {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${apiBaseUrl}/api/reviews/sample`, {
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const sample = await response.json();
      setReview(sample);
    } catch {
      setError('Could not load the sample review. Check that the backend is running and try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="shell sample-section" aria-labelledby="sample-title">
      <div className="sample-header">
        <h2 id="sample-title">Sample architecture review</h2>
        <button className="primary-link" type="button" onClick={loadReview} disabled={loading}>
          {review ? 'Load another sample' : 'Load sample review'}
        </button>
      </div>
      <div role="status">{loading ? 'Loading sample review…' : review && !error ? `Showing sample review for ${review.system_name}.` : ''}</div>
      {error && <p className="sample-error" role="alert">{error}</p>}
      {review && (
        <div className="review-grid sample-results">
          {review.review_areas.map(({ title, finding, next_step }) => (
            <article className="review-card" key={title}>
              <h3>{title}</h3>
              <p>{finding}</p>
              <p><strong>Next step</strong> {next_step}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
