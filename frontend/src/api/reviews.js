function reviewError(response, result) {
  const detail = typeof result?.detail === 'string' ? result.detail : null;
  const fields = Array.isArray(result?.detail) ? result.detail.map(item => item.msg).join(' ') : null;
  const error = new Error(detail || fields || `Review service returned HTTP ${response.status}.`);
  error.status = response.status;
  return error;
}

export async function requestReview(url, options) {
  const response = await fetch(url, {
    ...options,
    signal: options?.signal ?? AbortSignal.timeout(110000),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok || !result?.review_id) {
    throw reviewError(response, result);
  }
  return result;
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
