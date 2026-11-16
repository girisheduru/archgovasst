import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '');

const reviewAreas = [
  {
    title: 'Security & privacy',
    description: 'Document data classification, access controls, and how sensitive information is handled.',
  },
  {
    title: 'Architecture fit',
    description: 'Record the proposed components, integration points, and exceptions to existing standards.',
  },
  {
    title: 'Operational readiness',
    description: 'Identify service owners, monitoring, recovery plans, and how the system will be supported.',
  },
];

function SampleReview() {
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

function App() {
  return (
    <>
      <header className="site-header">
        <div className="shell header-content">
          <a className="brand" href="./">AIArchGovAsst</a>
          <nav aria-label="Main navigation">
            <a href="#review-areas">Review areas</a>
            <a href="https://github.com/girisheduru/archgovasst">GitHub ↗</a>
          </nav>
        </div>
      </header>
      <main>
        <section className="hero" aria-labelledby="page-title">
          <div className="shell hero-content">
            <div>
              <h1 id="page-title">Architecture governance for AI systems</h1>
              <p>Prepare AI architecture proposals for review. Capture design decisions, surface risks, and give reviewers the information they need to make a decision.</p>
              <a className="primary-link" href="#review-areas">Explore review areas <span aria-hidden="true">↓</span></a>
            </div>
            <aside className="review-brief" aria-labelledby="brief-title">
              <h2 id="brief-title">What to bring to a review</h2>
              <ul>
                <li>System scope and intended users</li>
                <li>Architecture diagram and data flows</li>
                <li>Known risks and proposed controls</li>
                <li>Open decisions and accountable owners</li>
              </ul>
            </aside>
          </div>
        </section>
        <section id="review-areas" className="shell review-section" aria-labelledby="areas-title">
          <h2 id="areas-title">Review areas</h2>
          <div className="review-grid">
            {reviewAreas.map(({ title, description }) => (
              <article className="review-card" key={title}>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </section>
        <SampleReview />
      </main>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
