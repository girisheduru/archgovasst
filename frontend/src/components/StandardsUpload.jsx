import React, { useState } from 'react';

export default function StandardsUpload({ apiBaseUrl }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  async function upload(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = new FormData(form);
    const token = body.get('token').trim();
    body.delete('token');
    setBusy(true);
    setResult(null);
    setError('');

    try {
      const response = await fetch(`${apiBaseUrl}/api/standards/import`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body,
        signal: AbortSignal.timeout(110000),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok || !Number.isInteger(data?.added)) {
        throw new Error(typeof data?.detail === 'string' ? data.detail : `Standards import failed (HTTP ${response.status}).`);
      }
      form.reset();
      setResult(data);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="shell review-section" aria-labelledby="standards-title">
      <h1 id="standards-title">Upload governance standards</h1>
      <p>Upload approved Word standards to import their rules.</p>
      <form className="review-form" onSubmit={upload}>
        <label>
          Source standards documents
          <input name="documents" type="file" accept=".docx" multiple required />
        </label>
        <label>
          Standards import token
          <input name="token" type="password" autoComplete="off" required />
        </label>
        <button className="primary-link" type="submit" disabled={busy}>Import standards</button>
      </form>
      <div role="status">
        {busy && 'Checking documents and importing rules…'}
        {result && `Rule versions added: ${result.added}. Already present: ${result.unchanged}.`}
      </div>
      {error && <p className="sample-error" role="alert">{error}</p>}
    </section>
  );
}
