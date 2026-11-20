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
const actions = [
  ['benchmark', 'Run AI benchmark'],
  ['publish', 'Publish Arize assets'],
  ['tests', 'Run application tests'],
  ['fixtures', 'Validate benchmark fixtures'],
];
const views = [
  ['benchmark', 'AI benchmark'],
  ['prompts', 'Prompt evals'],
  ['assets', 'Arize assets'],
  ['checks', 'Tests & fixtures'],
];
const promptLabels = {
  evidence_extraction: 'Full-document evidence extraction',
  passage_extraction: 'Passage extraction',
  gap_guidance: 'Gap guidance',
  review_judge: 'Review judge',
};

function ReportTabs({ activeView, onChange }) {
  function moveTab(event, index) {
    const count = views.length;
    const next = {
      ArrowLeft: (index + count - 1) % count,
      ArrowRight: (index + 1) % count,
      Home: 0,
      End: count - 1,
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const [id] = views[next];
    onChange(id);
    event.currentTarget.parentElement.children[next].focus();
  }

  return (
    <div className="performance-tabs" role="tablist" aria-label="Performance reports">
      {views.map(([id, label], index) => (
        <button key={id} type="button" role="tab" id={`performance-tab-${id}`}
          aria-controls={`performance-view-${id}`} aria-selected={activeView === id}
          tabIndex={activeView === id ? 0 : -1} onClick={() => onChange(id)}
          onKeyDown={event => moveTab(event, index)}>
          {label}
        </button>
      ))}
    </div>
  );
}

function BackendConfiguration({ configuration }) {
  if (!configuration) return null;
  return (
    <details className="performance-configuration">
      <summary>Backend configuration</summary>
      <p>{configuration.railway ? 'Railway service variables detected.' : 'Railway service variables were not detected.'}</p>
      <dl className="performance-assets">
        {Object.entries(configuration.variables).map(([name, configured]) => (
          <Stat key={name} label={<code>{name}</code>} value={configured ? 'Detected' : 'Missing'} />
        ))}
      </dl>
    </details>
  );
}

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

function matchesAnswerKey(item) {
  return item.expected_tier === item.assessed_tier && item.missed_gaps === 0 && item.unexpected_gaps === 0;
}

function Benchmark({ entry }) {
  const report = entry.report;
  const designsPassed = report?.cases.filter(matchesAnswerKey).length;
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
          <Stat label="Designs passed" value={designsPassed} />
          <Stat label="Designs failed" value={report.cases.length - designsPassed} />
          <Stat label="Model" value={report.model} />
          <Stat label="Retrieval mode" value={report.retrieval_mode === 'full_document' ? 'Full document' : 'Passages'} />
        </dl>
      )}
      <MetricTiles report={report} />
      {report && (
        <details className="performance-details">
          <summary>Results by design ({report.cases.length})</summary>
          <p className="performance-caption">A design passes when its evidence gaps and assessed risk tier match the answer key.</p>
          <div className="performance-table" tabIndex={0} role="region" aria-label="Benchmark results by design">
            <table>
              <thead><tr>
                <th scope="col">Design</th>
                <th scope="col">Result</th>
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
                    <td>{matchesAnswerKey(item)
                      ? <span className="status-badge" data-status="Passed">Passed</span>
                      : <span className="status-badge" data-status="Rejected">Failed</span>}</td>
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
        </details>
      )}
    </section>
  );
}

function PromptEvaluations({ entry }) {
  const report = entry.report;
  return (
    <section className="performance-panel">
      <div className="performance-panel-header">
        <h2>Prompt evaluations</h2>
        {report?.prompt_evals && <RunTime timestamp={report.completed_at} />}
      </div>
      {report?.prompt_evals ? (
        <div className="performance-table performance-prompt-table">
          <table>
            <thead><tr>
              <th scope="col">Prompt</th>
              <th scope="col">Passed</th>
              <th scope="col">Failed</th>
              <th scope="col">Errors</th>
            </tr></thead>
            <tbody>
              {Object.entries(report.prompt_evals).map(([name, result]) => {
                const publication = report.prompt_experiments?.[name];
                return (
                  <tr key={name}>
                    <th scope="row">
                      {promptLabels[name] ?? name}
                      {publication && (
                        <div className="performance-prompt-publication">
                          <span>{publication.experiment_name}</span>
                          {publication.experiment_id && <code>{publication.experiment_id}</code>}
                          {publication.experiment_publication_error
                            ? <span data-discrepancy="true">{publication.experiment_publication_error}</span>
                            : !publication.experiment_scores_published && <span>Publication pending.</span>}
                        </div>
                      )}
                    </th>
                    <td>{result.passed}</td>
                    <td data-discrepancy={result.failed > 0}>{result.failed}</td>
                    <td data-discrepancy={result.errors > 0}>{result.errors}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="performance-empty">Run a smoke or full benchmark to see results for all four prompts.</p>
      )}
    </section>
  );
}

function ArizeAssets({ assets, benchmark, publication }) {
  const report = assets.report;
  const experiment = benchmark.report;
  const prompts = report?.prompts ?? [];
  const evaluators = report?.evaluators ?? [];
  const dataset = report ?? experiment;
  const startupMessage = {
    running: 'Publishing the bundled dataset, prompts, and evaluators to Arize AX…',
    complete: 'Startup publication complete.',
    partial: 'Startup published the dataset and prompts. See Eval Hub for evaluator status.',
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
        <Stat label="Latest experiment" value={experiment?.experiment_id ? (
          <>{experiment.experiment_name}<code>{experiment.experiment_id}</code>
            {experiment.experiment_scores_published === false && <span>Score upload incomplete.</span>}
            {dataset?.dataset_id !== experiment.dataset_id && <code>Dataset {experiment.dataset_id}</code>}</>
        ) : experiment ? 'Benchmark scores saved. Arize experiment ID unavailable.' : 'No completed benchmark recorded'} />
      </dl>
      {report?.evaluator_publication_error && <p className="sample-error">{report.evaluator_publication_error}</p>}
      <details className="performance-details">
        <summary>Prompt Hub ({prompts.length})</summary>
        {prompts.length ? (
          <ul className="performance-asset-list">{prompts.map(prompt => <li key={prompt.prompt_id}>
            {prompt.name}<code>Prompt {prompt.prompt_id} · Version {prompt.version_id}</code>
          </li>)}</ul>
        ) : <p className="performance-caption">No prompt publication recorded.</p>}
      </details>
      <details className="performance-details">
        <summary>Eval Hub ({evaluators.length})</summary>
        {evaluators.length ? (
          <ul className="performance-asset-list">{evaluators.map(evaluator => <li key={evaluator.evaluator_id}>
            {evaluator.name}<code>Evaluator {evaluator.evaluator_id} · Version {evaluator.version_id}</code>
          </li>)}</ul>
        ) : <p className="performance-caption">No evaluator publication recorded.</p>}
      </details>
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
        <Stat label="Passed" value={report.passed_count ?? '—'} />
        <Stat label="Failed" value={report.failed_count ?? report.problem_tests.length} />
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
  const [activeView, setActiveView] = useState('benchmark');
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
      const connectionHint = apiBaseUrl
        ? `Check ${apiBaseUrl} and confirm the backend allows this frontend origin in CORS_ALLOWED_ORIGINS.`
        : 'Set VITE_API_BASE_URL to the Railway FastAPI HTTPS URL and rebuild the frontend, or route /api to FastAPI.';
      try {
        const response = await fetch(`${apiBaseUrl}/api/performance`, {
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
        }).catch(() => null);
        if (!response) throw new Error(`Could not connect to the performance API. ${connectionHint}`);
        if (response.status === 404) {
          throw new Error(`The performance API is missing at this address. Check that the latest backend is deployed. ${connectionHint}`);
        }
        if (!response.ok) throw new Error(`The performance API returned HTTP ${response.status}. Check the backend deployment logs.`);
        const data = await response.json().catch(() => null);
        if (!data?.benchmark || !data.tests || !data.fixtures) {
          throw new Error(`The request did not return dashboard data. ${connectionHint}`);
        }
        setReports(data);
        setError('');
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure.message);
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

  async function startAction(event) {
    event.preventDefault();
    if (!token.trim()) {
      setRunError('Enter the performance run token configured on the FastAPI backend.');
      return;
    }
    const action = event.nativeEvent.submitter?.value || 'benchmark';
    const query = action === 'benchmark' ? `?scope=${scope}` : '';
    setSubmitting(true);
    setRunError('');
    try {
      const response = await fetch(`${apiBaseUrl}/api/performance/${action}${query}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token.trim()}` },
        signal: AbortSignal.timeout(10000),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok || result?.status !== 'running') {
        throw new Error(typeof result?.detail === 'string' ? result.detail : 'Could not start the action.');
      }
      setReports(previous => ({ ...previous, job: result }));
      setActiveView(action === 'publish' ? 'assets' : action === 'benchmark' ? 'benchmark' : 'checks');
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
  const availability = reports?.actions ?? (reports?.job ? { benchmark: reports.runner_unavailable } : null);
  const controlsUnavailable = reports?.controls_unavailable;
  const busy = isRunning || submitting;
  const jobMessage = isRunning ? `${job.phase}…` : job?.message ?? (
    job?.status === 'complete' ? 'Benchmark finished.' :
    job?.status === 'failed' ? 'Benchmark failed. Check the backend logs.' : ''
  );
  return (
    <div className="shell performance-dashboard">
      <div className="performance-header">
        <h1>AI system performance</h1>
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
        <section className="performance-panel">
          <div className="performance-panel-header">
            <h2>Run evaluations and checks</h2>
          </div>
          <form className="performance-run-form" onSubmit={startAction}>
            <div className="performance-run-fields">
              <label>Performance run token
                <input required type="password" value={token} autoComplete="off"
                  aria-describedby="performance-token-help"
                  onChange={event => setToken(event.target.value)} disabled={!availability || Boolean(controlsUnavailable) || busy} />
              </label>
              <label>Benchmark scope
                <select value={scope} onChange={event => setScope(event.target.value)}
                  disabled={!availability || Boolean(controlsUnavailable || availability.benchmark) || busy || isPublishing}>
                  <option value="smoke">Smoke · 1 design</option>
                  <option value="full">Full · All designs</option>
                </select>
              </label>
            </div>
            <p id="performance-token-help" className="performance-token-help">
              {controlsUnavailable || (availability && 'Enter the PERFORMANCE_RUN_TOKEN set on the FastAPI backend.')}
            </p>
            <div className="performance-action-buttons">
              {actions.map(([action, label]) => {
                const needsArize = action === 'benchmark' || action === 'publish';
                const reason = availability && (
                  action in availability ? availability[action] : 'Update the backend to enable this action.'
                );
                return (
                  <div key={action}>
                    <button type="submit" value={action}
                      disabled={!availability || Boolean(controlsUnavailable || reason) || busy ||
                        (needsArize && isPublishing)}>
                      {label}
                    </button>
                    {reason && <small>{reason}</small>}
                  </div>
                );
              })}
            </div>
          </form>
          <p className="performance-caption" role="status">
            {jobMessage || (isPublishing ? 'Arize actions are available after startup publication finishes.' :
              publication?.status === 'failed' ? publication.message :
              publication?.status === 'partial' ? 'See Arize assets for evaluator publication status.' : '')}
          </p>
          {runError && <p className="sample-error" role="alert">{runError}</p>}
          <BackendConfiguration configuration={reports?.configuration} />
        </section>
        <ReportTabs activeView={activeView} onChange={setActiveView} />
        <div id="performance-view-benchmark" role="tabpanel" aria-labelledby="performance-tab-benchmark"
          hidden={activeView !== 'benchmark'} tabIndex={0}>
          <Benchmark entry={benchmark} />
        </div>
        <div id="performance-view-prompts" role="tabpanel" aria-labelledby="performance-tab-prompts"
          hidden={activeView !== 'prompts'} tabIndex={0}>
          <PromptEvaluations entry={benchmark} />
        </div>
        <div id="performance-view-assets" role="tabpanel" aria-labelledby="performance-tab-assets"
          hidden={activeView !== 'assets'} tabIndex={0}>
          <ArizeAssets assets={assets} benchmark={benchmark} publication={publication} />
        </div>
        <div id="performance-view-checks" role="tabpanel" aria-labelledby="performance-tab-checks"
          hidden={activeView !== 'checks'} tabIndex={0}>
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
      </div>
    </div>
  );
}
