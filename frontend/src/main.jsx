import React from 'react';
import { createRoot } from 'react-dom/client';
import DocumentReview from './components/DocumentReview.jsx';
import PerformanceDashboard from './components/PerformanceDashboard.jsx';
import StandardsUpload from './components/StandardsUpload.jsx';
import './style.css';

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '');

const reviewAreas = [
  {
    title: 'Encryption & identity',
    description: 'Document encryption at rest and in transit, authentication, and access controls against applicable policies.',
  },
  {
    title: 'Networking & secrets',
    description: 'Describe network boundaries, connectivity, and how credentials and secrets are stored, accessed, and rotated.',
  },
  {
    title: 'Observability & resiliency',
    description: 'Record logging, monitoring, alerting, failure handling, and recovery plans so reviewers can check the supporting evidence.',
  },
];

function HomePage() {
  return (
    <>
      <section className="hero" aria-labelledby="page-title">
        <div className="shell hero-content">
          <div>
            <h1 id="page-title">AI Architecture Governance Assistant</h1>
            <p>Review solution design documents against applicable architecture policies. Bring approved standards together, identify missing evidence, and give architects a consistent basis for review.</p>
            <div className="hero-actions">
              <a className="primary-link" href="/review">Start a document review <span aria-hidden="true">→</span></a>
              <a className="primary-link" href="/standards">Upload standards <span aria-hidden="true">→</span></a>
            </div>
          </div>
          <aside className="review-brief" aria-labelledby="brief-title">
            <h2 id="brief-title">Why reviews need support</h2>
            <ul>
              <li>Architecture policies often exist in scattered artifacts.</li>
              <li>Development teams don’t always know which policies apply to their proposed solution.</li>
              <li>Architects manually review solution design documents.</li>
              <li>Important questions can be overlooked, and reviews can be inconsistent.</li>
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
    </>
  );
}

function App({ path }) {
  const pages = {
    '/review': <DocumentReview apiBaseUrl={apiBaseUrl} />,
    '/standards': <StandardsUpload apiBaseUrl={apiBaseUrl} />,
    '/performance': <PerformanceDashboard apiBaseUrl={apiBaseUrl} />,
  };
  return (
    <>
      <header className="site-header">
        <div className="shell header-content">
          <a className="brand" href="/">AIArchGovAsst</a>
          <nav aria-label="Main navigation">
            <a href="/review" aria-current={path === '/review' ? 'page' : undefined}>Document review</a>
            <a href="/standards" aria-current={path === '/standards' ? 'page' : undefined}>Standards</a>
            <a href="/performance" aria-current={path === '/performance' ? 'page' : undefined}>Performance</a>
            <a href="https://github.com/girisheduru/archgovasst">GitHub ↗</a>
          </nav>
        </div>
      </header>
      <main>
        {pages[path] ?? <HomePage />}
      </main>
    </>
  );
}

const path = window.location.pathname.replace(/\/$/, '');
if (path === '/review') document.title = 'Document review | AI Architecture Governance Assistant';
if (path === '/standards') document.title = 'Upload governance standards | AI Architecture Governance Assistant';
if (path === '/performance') document.title = 'AI system performance | AI Architecture Governance Assistant';

createRoot(document.getElementById('root')).render(<App path={path} />);
