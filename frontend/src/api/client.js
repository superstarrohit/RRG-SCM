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

export function del(path) {
  return fetch(`${BASE}/api${path}`, { method: "DELETE" }).then(handle);
}

// ---- typed helpers ----
export const api = {
  health: () => get("/health"),
  dumpTypes: () => get("/meta/dump-types"),
  sourceTypes: () => get("/meta/source-types"),
  ingestionLog: () => get("/ingest/log"),
  overview: (p) => get("/analytics/overview", p),
  inventoryTimeseries: (p) => get("/analytics/inventory-timeseries", p),
  incomingTimeseries: (p) => get("/analytics/incoming-timeseries", p),
  inventoryRibbon: (p) => get("/analytics/inventory-ribbon", p),
  incoming: (p) => get("/analytics/incoming", p),
  planning: (p) => get("/analytics/planning", p),
  fgPlanning: (p) => get("/analytics/fg-planning", p),
  stockMonitoring: (p) => get("/analytics/stock-monitoring", p),
  inventoryMonitoring: (p) => get("/analytics/inventory-monitoring", p),
  vendorReceipts: (p) => get("/analytics/vendor-receipts", p),
  movements: (p) => get("/analytics/movements", p),
  forecasting: (p) => get("/analytics/forecasting", p),
  slicers: () => get("/meta/slicers"),
  testDb: (cfg) => postJSON("/ingest/db/test", cfg),
  previewDb: (cfg) => postJSON("/ingest/db/preview", cfg),
  ingestDb: (cfg) => postJSON("/ingest/db", cfg),
  uploadFile: (formData) => postForm("/ingest/file", formData),
  previewFile: (formData) => postForm("/ingest/file/preview", formData),

  // ---- Data workspace ----
  datasets: () => get("/data/datasets"),
  rows: (ds, p) => get(`/data/${ds}/rows`, p),
  profile: (ds) => get(`/data/${ds}/profile`),
  truncate: (ds) => del(`/data/${ds}`),
  deleteRows: (ds, ids) => postJSON(`/data/${ds}/delete-rows`, { ids }),
  updateRow: (ds, row_id, values) => postJSON(`/data/${ds}/update-row`, { row_id, values }),
  join: (body) => postJSON("/data/join", body),
  exportUrl: (ds, format) => `${BASE}/api/data/${ds}/export?format=${format}`,
};
