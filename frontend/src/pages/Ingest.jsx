import React from "react";
import { api } from "../api/client.js";
import { Panel, DataTable, useApi, fmtNum } from "../components/ui.jsx";

export default function Ingest() {
  const [tab, setTab] = React.useState("file");
  const dumpTypes = useApi(() => api.dumpTypes(), []);
  const sourceTypes = useApi(() => api.sourceTypes(), []);
  const [logKey, setLogKey] = React.useState(0);
  const log = useApi(() => api.ingestionLog(), [logKey]);

  const refreshLog = () => setLogKey((k) => k + 1);
  const dumps = dumpTypes.data || [];
  const dbSources = (sourceTypes.data || []).filter((s) => s.key !== "file");

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Data Ingestion</h1>
          <p>Upload daily dumps from Excel/CSV or pull from SQL Server, MySQL, PostgreSQL, MS Access or ODBC.</p>
        </div>
      </div>

      <div className="controls" style={{ marginBottom: 16 }}>
        <button className={tab === "file" ? "" : "secondary"} onClick={() => setTab("file")}>
          📄 File Upload
        </button>
        <button className={tab === "db" ? "" : "secondary"} onClick={() => setTab("db")}>
          🗄 Database Connection
        </button>
      </div>

      {tab === "file" ? (
        <FileUpload dumps={dumps} onDone={refreshLog} />
      ) : (
        <DbConnect dumps={dumps} sources={dbSources} onDone={refreshLog} />
      )}

      <Panel title="Recent Ingestions" right={<button className="secondary" onClick={refreshLog}>Refresh</button>}>
        <DataTable
          columns={[
            { key: "ingested_at", label: "When", render: (v) => (v ? new Date(v).toLocaleString() : "—") },
            { key: "dump_type", label: "Dump" },
            { key: "source_type", label: "Source" },
            { key: "source_name", label: "Name" },
            { key: "rows_ingested", label: "Rows", num: true, render: (v) => fmtNum(v) },
            { key: "mode", label: "Mode" },
            {
              key: "status",
              label: "Status",
              render: (v) => <span className={`badge ${v === "success" ? "ok" : "overdue"}`}>{v}</span>,
            },
          ]}
          rows={log.data || []}
        />
      </Panel>
    </div>
  );
}

function Result({ result }) {
  if (!result) return null;
  if (result.error) return <div className="alert error">{result.error}</div>;
  const r = result.report || result;
  return (
    <div className="alert success">
      Loaded <b>{fmtNum(r.rows_ingested ?? r.rows_out ?? 0)}</b> rows
      {r.rows_dropped ? ` (${r.rows_dropped} dropped)` : ""}.
      {r.column_map && (
        <div className="muted" style={{ marginTop: 6 }}>
          Mapped: {Object.entries(r.column_map).map(([src, dst]) => (
            <span className="tag" key={src} style={{ marginRight: 4 }}>{src} → {dst}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function PreviewBox({ preview }) {
  if (!preview) return null;
  const missing = preview.missing_required || [];
  return (
    <div className={`alert ${missing.length ? "error" : "info"}`} style={{ marginTop: 10 }}>
      <div>
        <b>{fmtNum(preview.rows)}</b> rows · {(preview.source_columns || []).length} columns.
      </div>
      {preview.column_map && (
        <div style={{ marginTop: 6 }}>
          {Object.entries(preview.column_map).map(([src, dst]) => (
            <span className="tag" key={src} style={{ marginRight: 4 }}>{src} → {dst}</span>
          ))}
        </div>
      )}
      {missing.length > 0 && (
        <div style={{ marginTop: 6 }}>
          ⚠ Missing required fields: <b>{missing.join(", ")}</b>. Rename those columns or map them.
        </div>
      )}
    </div>
  );
}

function FileUpload({ dumps, onDone }) {
  const [dumpType, setDumpType] = React.useState("");
  const [mode, setMode] = React.useState("replace");
  const [sheet, setSheet] = React.useState("");
  const [file, setFile] = React.useState(null);
  const [preview, setPreview] = React.useState(null);
  const [result, setResult] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!dumpType && dumps.length) setDumpType(dumps[0].key);
  }, [dumps, dumpType]);

  const build = () => {
    const fd = new FormData();
    fd.append("dump_type", dumpType);
    fd.append("mode", mode);
    if (sheet) fd.append("sheet_name", sheet);
    if (file) fd.append("file", file);
    return fd;
  };

  const doPreview = async () => {
    if (!file) return;
    setBusy(true); setResult(null); setPreview(null);
    try {
      setPreview(await api.previewFile(build()));
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setBusy(false);
    }
  };

  const doUpload = async () => {
    if (!file) return;
    setBusy(true); setResult(null);
    try {
      setResult(await api.uploadFile(build()));
      setPreview(null);
      onDone();
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Upload Excel / CSV">
      <div className="form-grid">
        <div className="field">
          <label>Dump type</label>
          <select value={dumpType} onChange={(e) => setDumpType(e.target.value)}>
            {dumps.map((d) => (
              <option key={d.key} value={d.key}>{d.label}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Load mode</label>
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="replace">Replace (overwrite existing)</option>
            <option value="append">Append (add to existing)</option>
          </select>
        </div>
        <div className="field">
          <label>File (.xlsx, .xls, .csv, .tsv)</label>
          <input type="file" accept=".xlsx,.xls,.csv,.tsv,.txt" onChange={(e) => setFile(e.target.files[0])} />
        </div>
        <div className="field">
          <label>Excel sheet (name or index, optional)</label>
          <input value={sheet} onChange={(e) => setSheet(e.target.value)} placeholder="0" />
        </div>
      </div>
      <div className="controls">
        <button className="secondary" onClick={doPreview} disabled={!file || busy}>Preview mapping</button>
        <button onClick={doUpload} disabled={!file || busy}>{busy ? "Working…" : "Upload & Load"}</button>
      </div>
      <PreviewBox preview={preview} />
      <div style={{ marginTop: 10 }}>
        <Result result={result} />
      </div>
      <FieldHints dumps={dumps} dumpType={dumpType} />
    </Panel>
  );
}

function DbConnect({ dumps, sources, onDone }) {
  const [cfg, setCfg] = React.useState({
    source_type: "postgres",
    host: "",
    port: "",
    database: "",
    username: "",
    password: "",
    odbc_driver: "",
    dsn: "",
    file_path: "",
    table: "",
    query: "",
    dump_type: "",
    mode: "replace",
    limit: 100,
  });
  const [msg, setMsg] = React.useState(null);
  const [preview, setPreview] = React.useState(null);
  const [result, setResult] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!cfg.dump_type && dumps.length) set("dump_type", dumps[0].key);
    if (!cfg.source_type && sources.length) set("source_type", sources[0].key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dumps, sources]);

  const set = (k, v) => setCfg((c) => ({ ...c, [k]: v }));
  const payload = () => ({ ...cfg, port: cfg.port ? Number(cfg.port) : undefined, limit: Number(cfg.limit) || 100 });

  const wrap = (fn, ok) => async () => {
    setBusy(true); setMsg(null); setResult(null); setPreview(null);
    try {
      await ok(await fn(payload()));
    } catch (e) {
      setMsg({ type: "error", text: e.message });
    } finally {
      setBusy(false);
    }
  };

  const doTest = wrap(api.testDb, (r) => setMsg({ type: "success", text: r.message }));
  const doPreview = wrap(api.previewDb, (r) => setPreview(r));
  const doIngest = wrap(api.ingestDb, (r) => { setResult(r); onDone(); });

  const st = cfg.source_type;
  const isAccess = st === "access";
  const isOdbc = st === "odbc";

  return (
    <Panel title="Connect to a Database">
      <div className="form-grid">
        <div className="field">
          <label>Source type</label>
          <select value={st} onChange={(e) => set("source_type", e.target.value)}>
            {sources.map((s) => (
              <option key={s.key} value={s.key}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Dump type (target)</label>
          <select value={cfg.dump_type} onChange={(e) => set("dump_type", e.target.value)}>
            {dumps.map((d) => (
              <option key={d.key} value={d.key}>{d.label}</option>
            ))}
          </select>
        </div>

        {isAccess ? (
          <div className="field">
            <label>Access file path (.accdb/.mdb)</label>
            <input value={cfg.file_path} onChange={(e) => set("file_path", e.target.value)} placeholder="C:\\data\\scm.accdb" />
          </div>
        ) : isOdbc ? (
          <div className="field">
            <label>DSN</label>
            <input value={cfg.dsn} onChange={(e) => set("dsn", e.target.value)} placeholder="MyOdbcDsn" />
          </div>
        ) : (
          <>
            <div className="field">
              <label>Host</label>
              <input value={cfg.host} onChange={(e) => set("host", e.target.value)} placeholder="localhost" />
            </div>
            <div className="field">
              <label>Port</label>
              <input value={cfg.port} onChange={(e) => set("port", e.target.value)} placeholder="(default)" />
            </div>
            <div className="field">
              <label>Database</label>
              <input value={cfg.database} onChange={(e) => set("database", e.target.value)} />
            </div>
          </>
        )}

        {!isAccess && (
          <>
            <div className="field">
              <label>Username</label>
              <input value={cfg.username} onChange={(e) => set("username", e.target.value)} />
            </div>
            <div className="field">
              <label>Password</label>
              <input type="password" value={cfg.password} onChange={(e) => set("password", e.target.value)} />
            </div>
          </>
        )}

        {(st === "sqlserver" || isOdbc) && (
          <div className="field">
            <label>ODBC driver</label>
            <input value={cfg.odbc_driver} onChange={(e) => set("odbc_driver", e.target.value)} placeholder="ODBC Driver 17 for SQL Server" />
          </div>
        )}

        <div className="field">
          <label>Table (or use a query below)</label>
          <input value={cfg.table} onChange={(e) => set("table", e.target.value)} placeholder="dbo.open_pos" />
        </div>
        <div className="field">
          <label>Load mode</label>
          <select value={cfg.mode} onChange={(e) => set("mode", e.target.value)}>
            <option value="replace">Replace</option>
            <option value="append">Append</option>
          </select>
        </div>
      </div>

      <div className="field">
        <label>SQL query (optional — overrides table)</label>
        <textarea rows={3} value={cfg.query} onChange={(e) => set("query", e.target.value)} placeholder="SELECT * FROM open_pos WHERE open_qty > 0" />
      </div>

      <div className="controls">
        <button className="secondary" onClick={doTest} disabled={busy}>Test connection</button>
        <button className="secondary" onClick={doPreview} disabled={busy}>Preview</button>
        <button onClick={doIngest} disabled={busy}>{busy ? "Working…" : "Pull & Load"}</button>
      </div>

      {msg && <div className={`alert ${msg.type}`} style={{ marginTop: 10 }}>{msg.text}</div>}
      {preview && (
        <div className="alert info" style={{ marginTop: 10 }}>
          <b>{fmtNum(preview.rows)}</b> rows · columns: {(preview.source_columns || []).map((c) => (
            <span className="tag" key={c} style={{ marginRight: 4 }}>{c}</span>
          ))}
        </div>
      )}
      <div style={{ marginTop: 10 }}>
        <Result result={result} />
      </div>

      <div className="alert info" style={{ marginTop: 12 }}>
        Database drivers are optional. Install what you need in the backend:
        <span className="tag" style={{ margin: "0 4px" }}>pip install psycopg2-binary</span>
        <span className="tag" style={{ margin: "0 4px" }}>PyMySQL</span>
        <span className="tag" style={{ margin: "0 4px" }}>pyodbc</span>
      </div>
    </Panel>
  );
}

function FieldHints({ dumps, dumpType }) {
  const dump = dumps.find((d) => d.key === dumpType);
  if (!dump) return null;
  return (
    <div className="alert info" style={{ marginTop: 12 }}>
      <b>{dump.label}</b> — {dump.description}
      <div style={{ marginTop: 6 }}>
        {dump.fields.map((f) => (
          <span className="tag" key={f.name} style={{ marginRight: 4, marginBottom: 4 }}>
            {f.name}{f.required ? " *" : ""}
          </span>
        ))}
      </div>
      <div className="muted" style={{ marginTop: 4 }}>* required · column names are matched flexibly (aliases, case, spacing).</div>
    </div>
  );
}
