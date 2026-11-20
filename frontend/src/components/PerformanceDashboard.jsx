import { useEffect, useState } from 'react';
import './PerformanceDashboard.css';

const metrics = [
  ['gap_precision', 'Gap precision', 'Share of reported gaps that the answer key expected.'],
  ['gap_recall', 'Gap recall', 'Share of expected gaps that the review found.'],
  ['gap_set_matches', 'Exact gap match', 'Share of designs with every expected gap and no extra gaps.'],
  ['risk_tier_matches', 'Risk tier agreement', 'Share of assessed tiers that matched the answer key.'],
  ['rule_coverage', 'Rule coverage', 'Share of benchmark rules represented in a review.'],
  ['rule_citation_validity', 'Rule citation validity', 'Share of findings with a matching standards quote and version.'],
  ['source_citation_validity', 'Source citation validity', 'Share of evidence quotes found in the cited design section.'],
];

const percentage = new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 1 });
const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' });

function RunTime({ timestamp }) {
  return <time dateTime={timestamp}>{dateFormat.format(new Date(timestamp))}</time>;
}

function ReportSection({ title, description, entry, empty, children }) {
  const report = entry.report;
  return (
    <section className="performance-panel">
      <div className="performance-panel-header">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        {report && <RunTime timestamp={report.completed_at} />}
      </div>
      {entry.status === 'available' ? children(report) : (
        <p className="performance-empty">
          {entry.status === 'pending' ? empty : 'The saved report could not be read.'}
        </p>
      )}
    </section>
  );
}

function Stat({ label, value }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

function Benchmark({ report }) {
  return (
    <>
      <dl className="performance-stats">
        <Stat label="Designs evaluated" value={`${report.case_count} of ${report.available_case_count}`} />
        <Stat label="Model" value={report.model} />
        <Stat label="Retrieval mode" value={report.retrieval_mode === 'full_document' ? 'Full document' : 'Passages'} />
      </dl>
      <p className="performance-caption">Scores are averaged across designs where each metric applies.</p>
      <div className="performance-metrics">
        {metrics.map(([id, label, description]) => {
          const score = report.mean_scores[id];
          return (
            <article className="performance-metric" key={id}>
              <h3>{label}</h3>
              <strong>{score == null ? 'N/A' : percentage.format(score)}</strong>
              {score != null && <meter value={score} aria-label={label} />}
              <p>{description}</p>
            </article>
          );
        })}
      </div>
      <div className="performance-table" tabIndex={0} role="region" aria-label="Benchmark results by design">
        <table>
          <caption>Results by design</caption>
          <thead><tr>
            <th scope="col">Design</th>
            <th scope="col">Expected risk</th>
            <th scope="col">Assessed risk</th>
            <th scope="col">Missed gaps</th>
            <th scope="col">Extra gaps</th>
            <th scope="col">Review time</th>
          </tr></thead>
          <tbody>
            {report.cases.map(item => (
              <tr key={item.id}>
                <th scope="row">{item.id}</th>
                <td className="performance-tier">{item.expected_tier}</td>
                <td className="performance-tier" data-discrepancy={item.expected_tier !== item.assessed_tier}>{item.assessed_tier}</td>
                <td data-discrepancy={item.missed_gaps > 0}>{item.missed_gaps}</td>
                <td data-discrepancy={item.unexpected_gaps > 0}>{item.unexpected_gaps}</td>
                <td>{item.duration_seconds} s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="performance-caption">Arize experiment <code>{report.experiment_id}</code></p>
    </>
  );
}

function ApplicationTests({ report }) {
  return (
    <>
      <span className="status-badge" data-status={report.passed ? 'Passed' : 'Rejected'}>
        {report.passed ? 'Suite passed' : 'Suite did not pass'}
      </span>
      <dl className="performance-stats">
        <Stat label="Tests run" value={report.tests_run} />
        <Stat label="Failures" value={report.failures} />
        <Stat label="Errors" value={report.errors} />
        <Stat label="Skipped" value={report.skipped} />
        <Stat label="Run time" value={`${report.duration_seconds} s`} />
        {report.expected_failures > 0 && <Stat label="Expected failures" value={report.expected_failures} />}
        {report.unexpected_successes > 0 && <Stat label="Unexpected successes" value={report.unexpected_successes} />}
      </dl>
      {report.problem_tests.length > 0 && (
        <details>
          <summary>Inspect failed checks</summary>
          <ul>{report.problem_tests.map(name => <li key={name}><code>{name}</code></li>)}</ul>
        </details>
      )}
    </>
  );
}

export default function PerformanceDashboard({ apiBaseUrl }) {
  const [reports, setReports] = useState(null);
  const [request, setRequest] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/performance`, {
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
        });
        if (!response.ok) throw new Error('Performance request failed.');
        const data = await response.json();
        if (!data.benchmark || !data.tests || !data.fixtures) throw new Error('Missing reports.');
        setReports(data);
      } catch {
        if (!controller.signal.aborted) {
          setError('Could not load the latest performance results. Check that the backend is running and try again.');
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [apiBaseUrl, request]);

  function refresh() {
    setLoading(true);
    setError('');
    setRequest(value => value + 1);
  }

  return (
    <div className="shell performance-dashboard">
      <div className="performance-header">
        <div>
          <h1>AI system performance</h1>
          <p>Latest benchmark results and application checks.</p>
        </div>
        <button type="button" onClick={refresh} disabled={loading}>{loading ? 'Loading…' : 'Refresh results'}</button>
      </div>
      <p className="performance-feedback" role="status">
        {loading ? 'Loading performance results…' : error}
      </p>
      {reports && (
        <div className="performance-reports">
          <ReportSection
            title="AI benchmark"
            description="Evidence extraction and gap assessment against the bundled design answer key."
            entry={reports.benchmark}
            empty="No benchmark run has been recorded."
          >
            {report => <Benchmark report={report} />}
          </ReportSection>
          <ReportSection
            title="Application tests"
            description="Backend regression checks for evidence retrieval, gap actions, standards reset, and tracing."
            entry={reports.tests}
            empty="No application test run has been recorded."
          >
            {report => <ApplicationTests report={report} />}
          </ReportSection>
          <ReportSection
            title="Benchmark fixture validation"
            description="Consistency checks across the bundled designs, standards, and answer workbook."
            entry={reports.fixtures}
            empty="No successful fixture validation has been recorded."
          >
            {report => (
              <dl className="performance-stats">
                <Stat label="Designs in report" value={`${report.case_count} of ${report.available_case_count}`} />
                <Stat label="Benchmark rules" value={report.rule_count} />
                <Stat label="Expected evidence gaps" value={report.expected_finding_count} />
              </dl>
            )}
          </ReportSection>
        </div>
      )}
      <details className="performance-instructions">
        <summary>How to generate results</summary>
        <p>Run these commands from the repository root in the backend environment, then refresh this page.</p>
        <dl>
          <dt>AI benchmark with OpenAI and Arize AX configured</dt>
          <dd><code>.venv/bin/python -m backend.governance.evaluate</code></dd>
          <dt>Application tests with backend dependencies and httpx installed</dt>
          <dd><code>.venv/bin/python -m backend.governance.run_application_tests</code></dd>
          <dt>Benchmark fixture validation with evaluation dependencies installed</dt>
          <dd><code>.venv/bin/python -m backend.governance.evaluate --validate-only</code></dd>
        </dl>
      </details>
    </div>
  );
}
