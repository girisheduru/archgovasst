import React from 'react';

export default function UploadPanel({ busy, onSubmit }) {
  return (
    <form className="review-form review-card" onSubmit={onSubmit}>
      <label>Design document
        <input name="document" type="file" accept=".docx,.pdf" required />
      </label>
      <p className="field-hint">Text-based PDF or Word, up to 10 MB. Extracted text is sent to OpenAI.</p>
      <div className="review-fields">
        <label>Document type
          <select name="document_type">
            <option value="solution_design">Solution design</option>
            <option value="architecture_decision">Architecture decision</option>
          </select>
        </label>
        <label>Declared risk tier
          <select name="declared_tier">
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </label>
        <label>Standards effective on (optional)
          <input type="date" name="as_of" />
        </label>
      </div>
      <button className="primary-link" disabled={busy}>Start review</button>
    </form>
  );
}
