import React, { useEffect, useState } from 'react';
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
const pending = { status: 'pending' };

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
          {entry.status === 'unavailable' ? 'The saved report could not be read.' : empty}
        </p>
      )}
    </section>
  );
}

function Stat({ label, value }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

function MetricTiles({ report }) {
  return (
    <div className="performance-metrics">
      {metrics.map(([id, label, description]) => {
        const score = report?.mean_scores?.[id];
        return (
          <article className="performance-metric" key={id}>
            <h3>{label}</h3>
            <strong>{score == null ? (report ? 'N/A' : '—') : percentage.format(score)}</strong>
            {score == null ? <div className="performance-meter-empty" /> : <meter value={score} aria-label={label} />}
            <p>{description}</p>
          </article>
        );
      })}
    </div>
  );
}

function Benchmark({ entry }) {
  const report = entry.report;
  return (
    <section className="performance-panel">
      <div className="performance-panel-header">
        <div>
          <h2>AI benchmark</h2>
          <p>{report ? 'Scores are averaged across designs where each metric applies.' :
            entry.status === 'unavailable' ? 'The saved benchmark could not be read.' : 'Run a benchmark to populate these scores.'}</p>
        </div>
        {report && <RunTime timestamp={report.completed_at} />}
      </div>
      {report && (
        <dl className="performance-stats">
          <Stat label="Designs evaluated" value={`${report.case_count} of ${report.available_case_count}`} />
          <Stat label="Model" value={report.model} />
          <Stat label="Retrieval mode" value={report.retrieval_mode === 'full_document' ? 'Full document' : 'Passages'} />
        </dl>
      )}
      <MetricTiles report={report} />
      {report && (
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
      )}
    </section>
  );
}

function ArizeAssets({ assets, benchmark, publication }) {
  const report = assets.report;
  const experiment = benchmark.report;
  const prompts = report?.prompts ?? [];
  const dataset = report ?? experiment;
  const startupMessage = {
    running: 'Publishing the bundled dataset and prompt templates to Arize AX…',
    complete: 'Startup publication complete.',
    unconfigured: 'Configure Arize on the backend to publish assets on startup.',
    failed: publication?.message,
  }[publication?.status];
  return (
    <section className="performance-panel">
      <div className="performance-panel-header">
        <div>
          <h2>Arize AX assets</h2>
          <p>Latest publication IDs recorded by this backend.</p>
        </div>
        <a href="https://app.arize.com/" target="_blank" rel="noreferrer">Open Arize AX ↗</a>
      </div>
      {startupMessage && <p className="performance-caption" role="status">{startupMessage}</p>}
      <dl className="performance-assets">
        {dataset?.space_id && <Stat label="Space ID" value={<code>{dataset.space_id}</code>} />}
        <Stat label="Dataset" value={dataset ? (
          <>{dataset.dataset_name}<code>{dataset.dataset_id}</code></>
        ) : 'No dataset publication recorded'} />
        <Stat label="Prompt Hub" value={prompts.length ? (
          <ul>{prompts.map(prompt => <li key={prompt.prompt_id}>
            {prompt.name}<code>Prompt {prompt.prompt_id} · Version {prompt.version_id}</code>
          </li>)}</ul>
        ) : 'No prompt publication recorded'} />
        <Stat label="Latest experiment" value={experiment ? (
          <>{experiment.experiment_name}<code>{experiment.experiment_id}</code>
            {dataset?.dataset_id !== experiment.dataset_id && <code>Dataset {experiment.dataset_id}</code>}</>
        ) : 'No completed benchmark recorded'} />
      </dl>
    </section>
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
  const [token, setToken] = useState('');
  const [scope, setScope] = useState('smoke');
  const [submitting, setSubmitting] = useState(false);
  const [runError, setRunError] = useState('');
  const job = reports?.job;
  const publication = reports?.arize_publication;
  const isRunning = job?.status === 'running';
  const isPublishing = publication?.status === 'running';

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
        setError('');
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

  useEffect(() => {
    if ((!isRunning && !isPublishing) || loading) return;
    const timer = setTimeout(() => {
      setLoading(true);
      setRequest(value => value + 1);
    }, 3000);
    return () => clearTimeout(timer);
  }, [isRunning, isPublishing, loading]);

  function refresh() {
    setLoading(true);
    setError('');
    setRequest(value => value + 1);
  }

  async function startBenchmark(event) {
    event.preventDefault();
    setSubmitting(true);
    setRunError('');
    try {
      const response = await fetch(`${apiBaseUrl}/api/performance/benchmark?scope=${scope}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token.trim()}` },
        signal: AbortSignal.timeout(10000),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok || result?.status !== 'running') {
        throw new Error(typeof result?.detail === 'string' ? result.detail : 'Could not start the benchmark.');
      }
      setToken('');
      setReports(previous => ({ ...previous, job: result }));
      refresh();
    } catch (failure) {
      setRunError(failure.message);
      refresh();
    } finally {
      setSubmitting(false);
    }
  }

  const benchmark = reports?.benchmark ?? pending;
  const tests = reports?.tests ?? pending;
  const fixtures = reports?.fixtures ?? pending;
  const assets = reports?.assets ?? pending;
  const canRun = Boolean(reports?.job && !reports.runner_unavailable && !isPublishing);
  return (
    <div className="shell performance-dashboard">
      <div className="performance-header">
        <div>
          <h1>AI system performance</h1>
          <p>Benchmark scores, Arize publications, and application checks.</p>
        </div>
        <button type="button" onClick={refresh} disabled={loading}>{loading ? 'Loading…' : 'Refresh results'}</button>
      </div>
      <p className="performance-feedback" role="status">
        {loading && !reports ? 'Loading performance results…' : error}
      </p>
      <dl className="performance-overview">
        <Stat label="Designs evaluated" value={benchmark.report?.case_count ?? '—'} />
        <Stat label="Prompt Hub assets" value={assets.report ? `${assets.report.prompts.length} of 4` : '—'} />
        <Stat label="Application tests run" value={tests.report?.tests_run ?? '—'} />
        <Stat label="Design fixtures validated" value={fixtures.report?.case_count ?? '—'} />
      </dl>
      <div className="performance-reports">
        <div className="performance-columns">
          <section className="performance-panel">
            <div className="performance-panel-header">
              <div>
                <h2>Run an evaluation</h2>
                <p>Publish the dataset and prompt templates, then score the bundled designs with OpenAI.</p>
              </div>
            </div>
            <form className="performance-run-form" onSubmit={startBenchmark}>
              <label>Designs
                <select value={scope} onChange={event => setScope(event.target.value)} disabled={!canRun || isRunning}>
                  <option value="smoke">Smoke test · 1 design</option>
                  <option value="full">Full benchmark · All designs</option>
                </select>
              </label>
              <label>Performance run token
                <input required type="password" value={token} autoComplete="off"
                  onChange={event => setToken(event.target.value)} disabled={!canRun || isRunning} />
              </label>
              <button type="submit" disabled={!canRun || isRunning || submitting || !token.trim()}>
                {isRunning ? 'Benchmark running…' : submitting ? 'Starting…' : 'Run benchmark'}
              </button>
            </form>
            <p className="performance-caption" role="status">
              {reports?.runner_unavailable || (!loading && !reports?.job && 'Connect to an updated backend to start runs here.')}
              {isPublishing && !reports.runner_unavailable && 'Benchmark runs are available after startup publication finishes.'}
              {isRunning && `${job.phase}…`}
              {job?.status === 'complete' && 'Benchmark finished. The latest results are shown below.'}
              {job?.status === 'failed' && `Benchmark failed during ${job.phase.toLowerCase()}. Check the backend logs and credentials.`}
            </p>
            {runError && <p className="sample-error" role="alert">{runError}</p>}
            <p className="performance-caption">Document reviews send telemetry to the configured Arize trace project.</p>
          </section>
          <ArizeAssets assets={assets} benchmark={benchmark} publication={publication} />
        </div>
        <Benchmark entry={benchmark} />
        <div className="performance-columns">
          <ReportSection
            title="Application tests"
            description="Backend regression checks for evidence retrieval, gap actions, standards reset, and tracing."
            entry={tests}
            empty="No application test run has been recorded."
          >
            {report => <ApplicationTests report={report} />}
          </ReportSection>
          <ReportSection
            title="Benchmark fixture validation"
            description="Consistency checks across the bundled designs, standards, and answer workbook."
            entry={fixtures}
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
      </div>
      <details className="performance-instructions">
        <summary>How to generate results</summary>
        <p>Run these commands from the repository root in the backend environment, then refresh this page.</p>
        <dl>
          <dt>Publish assets and run the AI benchmark with OpenAI and Arize AX configured</dt>
          <dd><code>.venv/bin/python -m backend.governance.evaluate</code></dd>
          <dt>Publish the dataset and Prompt Hub templates independently</dt>
          <dd><code>.venv/bin/python -m backend.governance.evaluation.publish</code></dd>
          <dt>Application tests with backend dependencies and httpx installed</dt>
          <dd><code>.venv/bin/python -m backend.governance.run_application_tests</code></dd>
          <dt>Benchmark fixture validation with evaluation dependencies installed</dt>
          <dd><code>.venv/bin/python -m backend.governance.evaluate --validate-only</code></dd>
        </dl>
      </details>
    </div>
  );
}
