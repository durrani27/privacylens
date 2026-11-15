// Thin client for Member 1's API (real FastAPI backend or mock_api/server.py).
const BASE = import.meta.env.VITE_API_BASE || "/api";

async function request(path, options) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, options);
  } catch {
    throw new Error("Cannot reach the PrivacyLens+ API. Is the backend running?");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* body was not JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

export const createScan = (query, force = false) =>
  request("/scans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, force }),
  });

export const getScan = (id) => request(`/scans/${encodeURIComponent(id)}`);
export const getEvidence = (id) => request(`/scans/${encodeURIComponent(id)}/evidence`);
