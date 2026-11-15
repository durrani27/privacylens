import { useState } from "react";

export default function SubmitForm({ onSubmit, busy, error }) {
  const [query, setQuery] = useState("");

  const handle = (e) => {
    e.preventDefault();
    if (query.trim()) onSubmit(query.trim());
  };

  return (
    <form onSubmit={handle} className="card submit" aria-label="Analyse an app">
      <label htmlFor="query">App name, package id or Google Play link</label>
      <div className="row">
        <input
          id="query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. com.whatsapp or https://play.google.com/store/apps/details?id=…"
          maxLength={300}
          autoComplete="off"
        />
        <button type="submit" disabled={busy || !query.trim()}>
          {busy ? "Submitting…" : "Analyse"}
        </button>
      </div>
      {error && <p role="alert" className="error">{error}</p>}
    </form>
  );
}
