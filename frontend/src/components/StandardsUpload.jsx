import React, { useState } from 'react';

export default function StandardsUpload({ apiBaseUrl }) {
  const [operation, setOperation] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [importedFiles, setImportedFiles] = useState([]);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const busy = Boolean(operation);

  function readToken(form) {
    const input = form.elements.namedItem('token');
    const token = input.value.trim();
    if (!token) {
      setError('Enter the standards import token.');
      input.focus();
    }
    return token;
  }

  async function maintainStandards(action, token, body) {
    const response = await fetch(`${apiBaseUrl}/api/standards/${action}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body,
      signal: AbortSignal.timeout(110000),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(typeof data?.detail === 'string' ? data.detail : `Request failed (HTTP ${response.status}).`);
    }
    return data;
  }

  function selectFiles(event) {
    setSelectedFiles(Array.from(event.currentTarget.files, file => file.name));
    setImportedFiles([]);
    setStatus('');
    setError('');
  }

  async function upload(event) {
    event.preventDefault();
    if (busy) return;

    const form = event.currentTarget;
    const token = readToken(form);
    if (!token) return;

    const body = new FormData(form);
    body.delete('token');
    setOperation('import');
    setImportedFiles([]);
    setStatus('');
    setError('');

    try {
      const data = await maintainStandards('import', token, body);
      if (!Number.isInteger(data?.added) || !Number.isInteger(data?.updated)) {
        throw new Error('The server returned an unexpected response.');
      }
      form.reset();
      setSelectedFiles([]);
      setImportedFiles(selectedFiles);
      setStatus(`Import complete. Added ${data.added} rule versions and overwrote ${data.updated}.`);
    } catch (failure) {
      setError(`Could not confirm the standards import. ${failure.message}`);
    } finally {
      setOperation('');
    }
  }

  async function clear(event) {
    if (busy) return;

    const form = event.currentTarget.form;
    const token = readToken(form);
    if (!token) return;

    setError('');
    if (!window.confirm(
      'Permanently delete every governance standard and its embeddings from the RAG database? ' +
      'This cannot be undone. Import approved standards again before starting a new document review.',
    )) {
      setStatus('Database reset cancelled.');
      return;
    }

    setOperation('clear');
    setStatus('');
    try {
      const data = await maintainStandards('clear', token);
      if (typeof data?.cleared !== 'boolean') {
        throw new Error('The server returned an unexpected response.');
      }
      form.elements.namedItem('token').value = '';
      setImportedFiles([]);
      setStatus(data.cleared
        ? 'RAG database cleared. Import approved standards before starting a new review.'
        : 'The RAG database is already empty. Import approved standards before starting a new review.');
    } catch (failure) {
      setError(`Could not confirm the database reset. ${failure.message}`);
    } finally {
      setOperation('');
    }
  }

  const fileNames = importedFiles.length ? importedFiles : selectedFiles;

  return (
    <section className="shell review-section" aria-labelledby="standards-title">
      <h1 id="standards-title">Upload governance standards</h1>
      <p>Upload approved Word standards. Rules with matching IDs and effective dates are overwritten.</p>
      <form className="review-form" onSubmit={upload}>
        <label>
          Source standards documents
          <input name="documents" type="file" accept=".docx" multiple required disabled={busy} onChange={selectFiles} />
        </label>
        {fileNames.length > 0 && (
          <div className="standards-files">
            <p>{importedFiles.length ? 'Imported files' : 'Selected files'}</p>
            <ul>
              {fileNames.map((name, index) => <li key={index}>{name}</li>)}
            </ul>
          </div>
        )}
        <label>
          Standards import token
          <input name="token" type="password" autoComplete="off" required disabled={busy} />
        </label>
        <div className="review-actions">
          <button className="primary-link" type="submit" disabled={busy}>Import standards</button>
          <button className="decision-button" data-status="Rejected" type="button" disabled={busy} onClick={clear}>
            Clear RAG database
          </button>
        </div>
      </form>
      <div role="status">
        {operation === 'import' && 'Validating the selected documents and importing rules…'}
        {operation === 'clear' && 'Clearing the RAG database…'}
        {status}
      </div>
      {error && <p className="sample-error" role="alert">{error}</p>}
    </section>
  );
}
