import React from 'react';
import { createRoot } from 'react-dom/client';
import DocumentReview from './components/DocumentReview.jsx';
import SampleReview from './components/SampleReview.jsx';
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

function App() {
  return (
    <>
      <header className="site-header">
        <div className="shell header-content">
          <a className="brand" href="./">AIArchGovAsst</a>
          <nav aria-label="Main navigation">
            <a href="#document-review">Document review</a>
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
              <a className="primary-link" href="#document-review">Start a document review <span aria-hidden="true">↓</span></a>
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
        <DocumentReview apiBaseUrl={apiBaseUrl} />
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
        <SampleReview apiBaseUrl={apiBaseUrl} />
      </main>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
