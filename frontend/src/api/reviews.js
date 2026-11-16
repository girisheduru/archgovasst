export async function requestReview(url, options) {
  const response = await fetch(url, {
    ...options,
    signal: options?.signal ?? AbortSignal.timeout(110000),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok || !result?.review_id) {
    const detail = typeof result?.detail === 'string' ? result.detail : null;
    const fields = Array.isArray(result?.detail) ? result.detail.map(item => item.msg).join(' ') : null;
    const error = new Error(detail || fields || `Review service returned HTTP ${response.status}.`);
    error.status = response.status;
    throw error;
  }
  return result;
}
