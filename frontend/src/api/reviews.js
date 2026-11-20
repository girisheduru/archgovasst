function reviewError(response, result) {
  const detail = typeof result?.detail === 'string' ? result.detail : null;
  const fields = Array.isArray(result?.detail) ? result.detail.map(item => item.msg).join(' ') : null;
  const error = new Error(detail || fields || `Review service returned HTTP ${response.status}.`);
  error.status = response.status;
  return error;
}

async function requestJson(url, options, isValid) {
  const response = await fetch(url, {
    ...options,
    signal: options?.signal ?? AbortSignal.timeout(110000),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok || !isValid(result)) {
    throw reviewError(response, result);
  }
  return result;
}

export function requestReview(url, options) {
  return requestJson(url, options, result => result?.review_id);
}

export function requestGapGuidance(url, ruleId) {
  const body = new FormData();
  body.set('rule_id', ruleId);
  return requestJson(url, {
    method: 'POST', body, signal: AbortSignal.timeout(135000),
  }, result => result?.missing_evidence && result?.next_step);
}

export async function requestReportPdf(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(30000) });
  if (!response.ok) {
    throw reviewError(response, await response.json().catch(() => null));
  }
  const report = await response.blob();
  if (report.type !== 'application/pdf' || !report.size) {
    throw new Error('The review service did not return a PDF.');
  }
  return report;
}
