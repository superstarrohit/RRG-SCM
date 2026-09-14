// Thin fetch wrapper for the RRG-SCM API.
// In dev, Vite proxies /api to the FastAPI backend (see vite.config.js).
const BASE = import.meta.env.VITE_API_BASE || "";

async function handle(res) {
  if (!res.ok) {
    let detail;
    try {
      const body = await res.json();
      detail = body.detail ?? body;
    } catch {
      detail = await res.text();
    }
    if (detail && typeof detail === "object") {
      detail = detail.message || JSON.stringify(detail);
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export function get(path, params) {
  const qs = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
      ).toString()
    : "";
  return fetch(`${BASE}/api${path}${qs}`).then(handle);
}

export function postJSON(path, body) {
  return fetch(`${BASE}/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(handle);
}

export function postForm(path, formData) {
  return fetch(`${BASE}/api${path}`, { method: "POST", body: formData }).then(
    handle
  );
}

// ---- typed helpers ----
export const api = {
  health: () => get("/health"),
  dumpTypes: () => get("/meta/dump-types"),
  sourceTypes: () => get("/meta/source-types"),
  ingestionLog: () => get("/ingest/log"),
  overview: (p) => get("/analytics/overview", p),
  incoming: (p) => get("/analytics/incoming", p),
  planning: (p) => get("/analytics/planning", p),
  sourcing: (p) => get("/analytics/sourcing", p),
  costing: (p) => get("/analytics/costing", p),
  fgPlanning: (p) => get("/analytics/fg-planning", p),
  testDb: (cfg) => postJSON("/ingest/db/test", cfg),
  previewDb: (cfg) => postJSON("/ingest/db/preview", cfg),
  ingestDb: (cfg) => postJSON("/ingest/db", cfg),
  uploadFile: (formData) => postForm("/ingest/file", formData),
  previewFile: (formData) => postForm("/ingest/file/preview", formData),
};
