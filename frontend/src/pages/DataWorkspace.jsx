import React from "react";
import { api } from "../api/client.js";
import { PageHeader, Panel, useApi, fmtNum } from "../components/ui.jsx";
import Icon from "../components/icons.jsx";

const WS_TABS = [
  { id: "browse", label: "Datasets", icon: "database" },
  { id: "link", label: "Link Tables", icon: "link" },
  { id: "import", label: "Import", icon: "upload" },
  { id: "quality", label: "Data Quality", icon: "report" },
];

export default function DataWorkspace() {
  const [tab, setTab] = React.useState("browse");
  const dsState = useApi(() => api.datasets(), []);
  const [reloadKey, setReloadKey] = React.useState(0);
  const datasets = dsState.data || [];
  const [selected, setSelected] = React.useState(null);

  React.useEffect(() => {
    if (!selected && datasets.length) setSelected(datasets[0].key);
  }, [datasets, selected]);

  const reloadDatasets = () => setReloadKey((k) => k + 1);
  // re-fetch datasets when reloadKey changes
  const ds2 = useApi(() => api.datasets(), [reloadKey]);
  const liveDatasets = reloadKey ? (ds2.data || datasets) : datasets;

  return (
    <div>
      <PageHeader
        title="Data Workspace"
        subtitle="Browse, edit, delete, append, merge and link your datasets · import/export across Excel, CSV, JSON and live database connectors."
      />

      <div className="seg" style={{ marginBottom: 18 }}>
        {WS_TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)}
            style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 15, height: 15, display: "inline-flex" }}><Icon name={t.icon} size={15} /></span>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "browse" && (
        <DatasetsView datasets={liveDatasets} selected={selected} setSelected={setSelected} onChanged={reloadDatasets} goImport={() => setTab("import")} />
      )}
      {tab === "link" && <LinkView datasets={liveDatasets} />}
      {tab === "import" && <ImportView datasets={liveDatasets} onDone={reloadDatasets} />}
      {tab === "quality" && <QualityView datasets={liveDatasets} selected={selected} setSelected={setSelected} />}
    </div>
  );
}

/* ============================ Datasets browse/edit ============================ */
function DatasetsView({ datasets, selected, setSelected, onChanged, goImport }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 18, alignItems: "start" }} className="ws-split">
      <Panel title="Datasets">
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {datasets.map((d) => (
            <button key={d.key} onClick={() => setSelected(d.key)}
              className="ds-item" data-on={selected === d.key}>
              <span className="ds-ic"><Icon name={iconForDataset(d.key)} size={16} /></span>
              <span style={{ flex: 1, textAlign: "left" }}>{d.label}</span>
              <span className="ds-count">{fmtNum(d.rows)}</span>
            </button>
          ))}
        </div>
      </Panel>
      {selected ? <DatasetTable key={selected} dataset={selected} onChanged={onChanged} goImport={goImport} /> : <Panel><div className="empty">Select a dataset.</div></Panel>}
    </div>
  );
}

function DatasetTable({ dataset, onChanged, goImport }) {
  const LIMIT = 25;
  const [offset, setOffset] = React.useState(0);
  const [sort, setSort] = React.useState(null);
  const [dir, setDir] = React.useState("asc");
  const [q, setQ] = React.useState("");
  const [qLive, setQLive] = React.useState("");
  const [sel, setSel] = React.useState(() => new Set());
  const [editing, setEditing] = React.useState(null);
  const [editVals, setEditVals] = React.useState({});
  const [busy, setBusy] = React.useState(false);
  const [msg, setMsg] = React.useState(null);
  const [key, setKey] = React.useState(0);

  const state = useApi(() => api.rows(dataset, { limit: LIMIT, offset, sort, direction: dir, q }),
    [dataset, offset, sort, dir, q, key]);

  React.useEffect(() => { setOffset(0); setSel(new Set()); setEditing(null); }, [dataset]);

  const reload = () => { setKey((k) => k + 1); onChanged?.(); };
  const data = state.data;
  const cols = data?.columns || [];
  const rows = data?.rows || [];
  const total = data?.total || 0;

  const toggleSort = (c) => {
    if (sort === c) setDir(dir === "asc" ? "desc" : "asc");
    else { setSort(c); setDir("asc"); }
  };
  const toggleSel = (id) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allOnPage = rows.length > 0 && rows.every((r) => sel.has(r.id));
  const toggleAll = () => setSel((s) => {
    const n = new Set(s);
    if (allOnPage) rows.forEach((r) => n.delete(r.id)); else rows.forEach((r) => n.add(r.id));
    return n;
  });

  const doDeleteSelected = async () => {
    if (!sel.size || !confirm(`Delete ${sel.size} selected row(s) from ${dataset}?`)) return;
    setBusy(true); setMsg(null);
    try { const r = await api.deleteRows(dataset, [...sel]); setMsg({ t: "success", m: `Deleted ${r.deleted} rows.` }); setSel(new Set()); reload(); }
    catch (e) { setMsg({ t: "error", m: e.message }); } finally { setBusy(false); }
  };
  const doTruncate = async () => {
    if (!confirm(`Delete ALL rows in ${dataset}? This cannot be undone.`)) return;
    setBusy(true); setMsg(null);
    try { const r = await api.truncate(dataset); setMsg({ t: "success", m: `Cleared ${r.deleted} rows.` }); setSel(new Set()); reload(); }
    catch (e) { setMsg({ t: "error", m: e.message }); } finally { setBusy(false); }
  };
  const startEdit = (r) => { setEditing(r.id); setEditVals({ ...r }); };
  const saveEdit = async () => {
    setBusy(true); setMsg(null);
    try {
      const vals = {};
      cols.filter((c) => c.editable).forEach((c) => { vals[c.name] = editVals[c.name]; });
      await api.updateRow(dataset, editing, vals);
      setEditing(null); setMsg({ t: "success", m: "Row updated." }); reload();
    } catch (e) { setMsg({ t: "error", m: e.message }); } finally { setBusy(false); }
  };

  const iconBtn = (icon, label, onClick, cls = "ghost") => (
    <button className={`btn ${cls}`} onClick={onClick} disabled={busy} title={label}>
      <Icon name={icon} size={15} /> {label}
    </button>
  );

  return (
    <Panel>
      <div className="ws-toolbar">
        <div className="ws-search">
          <Icon name="search" size={15} />
          <input placeholder={`Search ${dataset}…`} value={qLive}
            onChange={(e) => setQLive(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { setQ(qLive); setOffset(0); } }} />
        </div>
        <span className="muted" style={{ fontSize: 12 }}>{fmtNum(total)} rows</span>
        <span className="spacer" style={{ flex: 1 }} />
        {iconBtn("plus", "Append", goImport)}
        {iconBtn("merge", "Merge", goImport)}
        {iconBtn("excel", "Excel", () => downloadExport(dataset, "xlsx"))}
        {iconBtn("csv", "CSV", () => downloadExport(dataset, "csv"))}
        {iconBtn("json", "JSON", () => downloadExport(dataset, "json"))}
        {iconBtn("trash", `Delete (${sel.size})`, doDeleteSelected, sel.size ? "blue" : "ghost")}
        {iconBtn("x", "Clear all", doTruncate)}
      </div>

      {msg && <div className={`alert ${msg.t}`}>{msg.m}</div>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ width: 30 }}><input type="checkbox" checked={allOnPage} onChange={toggleAll} /></th>
              {cols.filter((c) => c.name !== "id").map((c) => (
                <th key={c.name} onClick={() => toggleSort(c.name)} style={{ cursor: "pointer" }}>
                  {c.name} {sort === c.name ? (dir === "asc" ? "▲" : "▼") : ""}
                </th>
              ))}
              <th style={{ width: 90 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><input type="checkbox" checked={sel.has(r.id)} onChange={() => toggleSel(r.id)} /></td>
                {cols.filter((c) => c.name !== "id").map((c) => (
                  <td key={c.name} className={isNum(c.type) ? "num" : ""}>
                    {editing === r.id && c.editable ? (
                      <input className="cell-edit" value={editVals[c.name] ?? ""}
                        onChange={(e) => setEditVals((v) => ({ ...v, [c.name]: e.target.value }))} />
                    ) : (fmtCell(r[c.name]))}
                  </td>
                ))}
                <td>
                  {editing === r.id ? (
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="icon-btn ok" onClick={saveEdit} title="Save"><Icon name="check" size={15} /></button>
                      <button className="icon-btn" onClick={() => setEditing(null)} title="Cancel"><Icon name="x" size={15} /></button>
                    </div>
                  ) : (
                    <button className="icon-btn" onClick={() => startEdit(r)} title="Edit row"><Icon name="edit" size={15} /></button>
                  )}
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={cols.length + 1}><div className="empty">No rows.</div></td></tr>}
          </tbody>
        </table>
      </div>

      <div className="pager">
        <button className="btn ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
          <Icon name="arrowLeft" size={15} /> Prev
        </button>
        <span className="muted">{total ? offset + 1 : 0}–{Math.min(offset + LIMIT, total)} of {fmtNum(total)}</span>
        <button className="btn ghost" disabled={offset + LIMIT >= total} onClick={() => setOffset(offset + LIMIT)}>
          Next <Icon name="arrowRight" size={15} />
        </button>
      </div>
    </Panel>
  );
}

/* ============================ Link (join) ============================ */
function LinkView({ datasets }) {
  const [left, setLeft] = React.useState("");
  const [right, setRight] = React.useState("");
  const [leftOn, setLeftOn] = React.useState("");
  const [rightOn, setRightOn] = React.useState("");
  const [how, setHow] = React.useState("inner");
  const [res, setRes] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);

  React.useEffect(() => {
    if (!left && datasets.length) setLeft(datasets[0].key);
    if (!right && datasets.length > 1) setRight(datasets[1].key);
  }, [datasets]);

  const colsOf = (k) => (datasets.find((d) => d.key === k)?.columns || []).map((c) => c.name).filter((n) => n !== "id");
  React.useEffect(() => { const c = colsOf(left); if (c.length && !c.includes(leftOn)) setLeftOn(guessKey(c)); }, [left, datasets]);
  React.useEffect(() => { const c = colsOf(right); if (c.length && !c.includes(rightOn)) setRightOn(guessKey(c)); }, [right, datasets]);

  const run = async () => {
    setBusy(true); setErr(null); setRes(null);
    try { setRes(await api.join({ left, right, left_on: leftOn, right_on: rightOn, how, limit: 100 })); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <>
      <Panel title="Link Two Tables (column → column join)">
        <div className="link-grid">
          <Field label="Left table" icon="database"><select value={left} onChange={(e) => setLeft(e.target.value)}>{datasets.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}</select></Field>
          <Field label="Left column (key)" icon="key"><select value={leftOn} onChange={(e) => setLeftOn(e.target.value)}>{colsOf(left).map((c) => <option key={c} value={c}>{c}</option>)}</select></Field>
          <Field label="Join type" icon="merge">
            <select value={how} onChange={(e) => setHow(e.target.value)}>
              <option value="inner">Inner (matches only)</option>
              <option value="left">Left (all left + matches)</option>
              <option value="right">Right (all right + matches)</option>
              <option value="outer">Outer (everything)</option>
            </select>
          </Field>
          <Field label="Right table" icon="database"><select value={right} onChange={(e) => setRight(e.target.value)}>{datasets.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}</select></Field>
          <Field label="Right column (key)" icon="key"><select value={rightOn} onChange={(e) => setRightOn(e.target.value)}>{colsOf(right).map((c) => <option key={c} value={c}>{c}</option>)}</select></Field>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="btn blue" onClick={run} disabled={busy} style={{ width: "100%", justifyContent: "center" }}>
              <Icon name="link" size={15} /> {busy ? "Linking…" : "Run Link"}
            </button>
          </div>
        </div>
        {err && <div className="alert error">{err}</div>}
      </Panel>

      {res && (
        <Panel title="Linked Result" hint={`${fmtNum(res.total)} rows · ${res.left_rows} left × ${res.right_rows} right`}>
          <div className="table-wrap">
            <table>
              <thead><tr>{res.columns.map((c) => <th key={c.name}>{c.name}</th>)}</tr></thead>
              <tbody>
                {res.rows.slice(0, 50).map((r, i) => (
                  <tr key={i}>{res.columns.map((c) => <td key={c.name}>{fmtCell(r[c.name])}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
          {res.total > 50 && <div className="muted" style={{ marginTop: 10, fontSize: 12 }}>Showing first 50 of {fmtNum(res.total)} rows.</div>}
        </Panel>
      )}
    </>
  );
}

/* ============================ Import (file + DB + SAP) ============================ */
function ImportView({ datasets, onDone }) {
  const [mode, setMode] = React.useState("file");
  const dumpTypes = useApi(() => api.dumpTypes(), []);
  const sourceTypes = useApi(() => api.sourceTypes(), []);
  const dumps = dumpTypes.data || [];
  const sources = (sourceTypes.data || []).filter((s) => s.key !== "file");

  return (
    <>
      <div className="seg">
        <button className={mode === "file" ? "on" : ""} onClick={() => setMode("file")} style={sx}><Icon name="excel" size={15} /> File (Excel / CSV / JSON)</button>
        <button className={mode === "db" ? "on" : ""} onClick={() => setMode("db")} style={sx}><Icon name="server" size={15} /> Database &amp; Connectors</button>
      </div>
      {mode === "file" ? <FileImport dumps={dumps} onDone={onDone} /> : <DbImport dumps={dumps} sources={sources} onDone={onDone} />}
    </>
  );
}
const sx = { display: "inline-flex", alignItems: "center", gap: 7 };

function FileImport({ dumps, onDone }) {
  const [dumpType, setDumpType] = React.useState("");
  const [mode, setMode] = React.useState("replace");
  const [mergeKeys, setMergeKeys] = React.useState("");
  const [sheet, setSheet] = React.useState("");
  const [file, setFile] = React.useState(null);
  const [preview, setPreview] = React.useState(null);
  const [result, setResult] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => { if (!dumpType && dumps.length) setDumpType(dumps[0].key); }, [dumps, dumpType]);

  const build = () => { const fd = new FormData(); fd.append("dump_type", dumpType); fd.append("mode", mode); if (mergeKeys) fd.append("merge_keys", mergeKeys); if (sheet) fd.append("sheet_name", sheet); if (file) fd.append("file", file); return fd; };
  const doPreview = async () => { if (!file) return; setBusy(true); setResult(null); setPreview(null); try { setPreview(await api.previewFile(build())); } catch (e) { setResult({ error: e.message }); } finally { setBusy(false); } };
  const doUpload = async () => { if (!file) return; setBusy(true); setResult(null); try { setResult(await api.uploadFile(build())); setPreview(null); onDone(); } catch (e) { setResult({ error: e.message }); } finally { setBusy(false); } };

  return (
    <Panel title="Import from File" hint=".xlsx · .xls · .csv · .tsv · .json">
      <div className="connector-strip">
        <span className="conn-chip on" style={{ cursor: "default" }}><Icon name="excel" size={16} /> Excel (.xlsx/.xls)</span>
        <span className="conn-chip on" style={{ cursor: "default" }}><Icon name="csv" size={16} /> CSV / TSV</span>
        <span className="conn-chip on" style={{ cursor: "default" }}><Icon name="json" size={16} /> JSON</span>
        <span className="muted" style={{ marginLeft: 6, fontSize: 12.5 }}>Every dataset can be exported back to these formats — see Export below.</span>
      </div>
      <div className="form-grid">
        <Field label="Target dataset" icon="database"><select value={dumpType} onChange={(e) => setDumpType(e.target.value)}>{dumps.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}</select></Field>
        <Field label="Load mode" icon="merge">
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="replace">Replace (overwrite)</option>
            <option value="append">Append (add rows)</option>
            <option value="merge">Merge (upsert on key)</option>
          </select>
        </Field>
        <Field label="File" icon="upload"><input type="file" accept=".xlsx,.xls,.csv,.tsv,.txt,.json" onChange={(e) => setFile(e.target.files[0])} /></Field>
        {mode === "merge"
          ? <Field label="Merge key column(s), comma-separated" icon="key"><input value={mergeKeys} onChange={(e) => setMergeKeys(e.target.value)} placeholder="material_code" /></Field>
          : <Field label="Excel sheet (optional)" icon="columns"><input value={sheet} onChange={(e) => setSheet(e.target.value)} placeholder="0" /></Field>}
      </div>
      <div className="controls">
        <button className="btn ghost" onClick={doPreview} disabled={!file || busy}><Icon name="eye" size={15} /> Preview mapping</button>
        <button className="btn blue" onClick={doUpload} disabled={!file || busy}><Icon name="upload" size={15} /> {busy ? "Working…" : "Import"}</button>
      </div>
      <PreviewBox preview={preview} />
      <ResultBox result={result} />
      <FieldHints dumps={dumps} dumpType={dumpType} />
    </Panel>
  );
}

function DbImport({ dumps, sources, onDone }) {
  const [cfg, setCfg] = React.useState({ source_type: "postgres", host: "", port: "", database: "", username: "", password: "", odbc_driver: "", dsn: "", file_path: "", table: "", query: "", dump_type: "", mode: "replace", merge_keys: "" });
  const [msg, setMsg] = React.useState(null);
  const [preview, setPreview] = React.useState(null);
  const [result, setResult] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => { if (!cfg.dump_type && dumps.length) set("dump_type", dumps[0].key); }, [dumps]);
  const set = (k, v) => setCfg((c) => ({ ...c, [k]: v }));
  const payload = () => ({ ...cfg, port: cfg.port ? Number(cfg.port) : undefined, merge_keys: cfg.merge_keys ? cfg.merge_keys.split(",").map((s) => s.trim()) : undefined, limit: 100000 });
  const wrap = (fn, ok) => async () => { setBusy(true); setMsg(null); setResult(null); setPreview(null); try { await ok(await fn(payload())); } catch (e) { setMsg({ type: "error", text: e.message }); } finally { setBusy(false); } };
  const doTest = wrap(api.testDb, (r) => setMsg({ type: "success", text: r.message }));
  const doPreview = wrap(api.previewDb, (r) => setPreview(r));
  const doIngest = wrap(api.ingestDb, (r) => { setResult(r); onDone(); });

  const st = cfg.source_type, isAccess = st === "access", isDsn = st === "odbc" || st === "sap_odbc" || st === "knime", isHana = st === "sap_hana";

  return (
    <Panel title="Import from Database / Connector" hint="SQL Server · MySQL Workbench · PostgreSQL · MS Access · ODBC · SAP HANA (Live) · KNIME">
      <div className="connector-strip">
        {sources.map((s) => (
          <button key={s.key} className={`conn-chip ${st === s.key ? "on" : ""}`} onClick={() => set("source_type", s.key)}>
            <Icon name={iconForSource(s.key)} size={16} /> {s.label}
          </button>
        ))}
      </div>
      <div className="form-grid">
        <Field label="Target dataset" icon="database"><select value={cfg.dump_type} onChange={(e) => set("dump_type", e.target.value)}>{dumps.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}</select></Field>
        <Field label="Load mode" icon="merge">
          <select value={cfg.mode} onChange={(e) => set("mode", e.target.value)}>
            <option value="replace">Replace</option><option value="append">Append</option><option value="merge">Merge (upsert)</option>
          </select>
        </Field>
        {isAccess ? (
          <Field label="Access file path (.accdb/.mdb)" icon="database"><input value={cfg.file_path} onChange={(e) => set("file_path", e.target.value)} placeholder="C:\\data\\scm.accdb" /></Field>
        ) : isDsn ? (
          <Field label="DSN" icon="odbc"><input value={cfg.dsn} onChange={(e) => set("dsn", e.target.value)} placeholder="MyOdbcDsn" /></Field>
        ) : (
          <>
            <Field label="Host" icon="server"><input value={cfg.host} onChange={(e) => set("host", e.target.value)} placeholder={isHana ? "hana.corp.local" : "localhost"} /></Field>
            <Field label="Port" icon="server"><input value={cfg.port} onChange={(e) => set("port", e.target.value)} placeholder={isHana ? "30015" : "(default)"} /></Field>
            {!isHana && <Field label="Database" icon="database"><input value={cfg.database} onChange={(e) => set("database", e.target.value)} /></Field>}
          </>
        )}
        {!isAccess && (<>
          <Field label="Username" icon="key"><input value={cfg.username} onChange={(e) => set("username", e.target.value)} /></Field>
          <Field label="Password" icon="key"><input type="password" value={cfg.password} onChange={(e) => set("password", e.target.value)} /></Field>
        </>)}
        {(st === "sqlserver" || st === "odbc" || st === "sap_odbc" || st === "knime") && (
          <Field label="ODBC driver" icon="odbc"><input value={cfg.odbc_driver} onChange={(e) => set("odbc_driver", e.target.value)} placeholder="ODBC Driver 17 for SQL Server" /></Field>
        )}
        <Field label="Table" icon="columns"><input value={cfg.table} onChange={(e) => set("table", e.target.value)} placeholder="dbo.open_pos" /></Field>
        {cfg.mode === "merge" && <Field label="Merge key(s)" icon="key"><input value={cfg.merge_keys} onChange={(e) => set("merge_keys", e.target.value)} placeholder="material_code" /></Field>}
      </div>
      <Field label="SQL query (optional — overrides table)" icon="search"><textarea rows={3} value={cfg.query} onChange={(e) => set("query", e.target.value)} placeholder="SELECT * FROM open_pos WHERE open_qty > 0" /></Field>
      <div className="controls">
        <button className="btn ghost" onClick={doTest} disabled={busy}><Icon name="check" size={15} /> Test</button>
        <button className="btn ghost" onClick={doPreview} disabled={busy}><Icon name="eye" size={15} /> Preview</button>
        <button className="btn blue" onClick={doIngest} disabled={busy}><Icon name="download" size={15} /> {busy ? "Working…" : "Pull & Load"}</button>
      </div>
      {msg && <div className={`alert ${msg.type}`}>{msg.text}</div>}
      {preview && <div className="alert info"><b>{fmtNum(preview.rows)}</b> rows · {(preview.source_columns || []).map((c) => <span className="tag" key={c}>{c}</span>)}</div>}
      <ResultBox result={result} />
      <div className="alert info">Drivers load lazily — install what a connector needs in the backend:
        <span className="tag">psycopg2-binary</span><span className="tag">PyMySQL</span><span className="tag">pyodbc</span><span className="tag">sqlalchemy-hana</span>
      </div>
    </Panel>
  );
}

/* ============================ Data quality ============================ */
function QualityView({ datasets, selected, setSelected }) {
  const ds = selected || datasets[0]?.key;
  const state = useApi(() => ds ? api.profile(ds) : Promise.resolve(null), [ds]);
  const p = state.data;
  return (
    <Panel title="Data Quality & Modeling Report">
      <div className="controls" style={{ marginBottom: 14 }}>
        <Field label="Dataset" icon="report">
          <select value={ds} onChange={(e) => setSelected(e.target.value)}>{datasets.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}</select>
        </Field>
      </div>
      {!p ? <div className="empty">Loading…</div> : (
        <>
          <div className="muted" style={{ marginBottom: 12 }}>{fmtNum(p.rows)} rows · {p.columns.length} columns</div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Column</th><th className="num">Non-null</th><th className="num">Nulls</th><th className="num">Null %</th><th className="num">Distinct</th><th className="num">Min</th><th className="num">Max</th><th className="num">Mean</th></tr></thead>
              <tbody>
                {p.columns.map((c) => (
                  <tr key={c.column}>
                    <td className="strong mono">{c.column}</td>
                    <td className="num">{fmtNum(c.non_null)}</td>
                    <td className="num">{fmtNum(c.nulls)}</td>
                    <td className="num">{c.null_pct > 0 ? <span className={`badge ${c.null_pct > 20 ? "b-red" : "b-amber"}`}>{c.null_pct}%</span> : <span className="badge b-green">0%</span>}</td>
                    <td className="num">{fmtNum(c.distinct)}</td>
                    <td className="num">{c.min ?? "—"}</td>
                    <td className="num">{c.max ?? "—"}</td>
                    <td className="num">{c.mean ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  );
}

/* ============================ shared bits ============================ */
function Field({ label, icon, children }) {
  return (
    <div className="field">
      <label style={{ display: "flex", alignItems: "center", gap: 6 }}>{icon && <Icon name={icon} size={13} />}{label}</label>
      {children}
    </div>
  );
}
function PreviewBox({ preview }) {
  if (!preview) return null;
  const missing = preview.missing_required || [];
  return (
    <div className={`alert ${missing.length ? "error" : "info"}`}>
      <b>{fmtNum(preview.rows)}</b> rows · {(preview.source_columns || []).length} columns
      {preview.column_map && <div style={{ marginTop: 6 }}>{Object.entries(preview.column_map).map(([s, d]) => <span className="tag" key={s}>{s} → {d}</span>)}</div>}
      {missing.length > 0 && <div style={{ marginTop: 6 }}>⚠ Missing required: <b>{missing.join(", ")}</b></div>}
    </div>
  );
}
function ResultBox({ result }) {
  if (!result) return null;
  if (result.error) return <div className="alert error">{result.error}</div>;
  const r = result.report || result;
  return <div className="alert success">✓ {r.updated !== undefined ? `Merged — ${fmtNum(r.inserted)} inserted, ${fmtNum(r.updated)} updated.` : `Loaded ${fmtNum(r.rows_ingested ?? 0)} rows.`}</div>;
}
function FieldHints({ dumps, dumpType }) {
  const dump = dumps.find((d) => d.key === dumpType);
  if (!dump) return null;
  return (
    <div className="alert info">
      <b>{dump.label}</b> — {dump.description}
      <div style={{ marginTop: 6 }}>{dump.fields.map((f) => <span className="tag" key={f.name}>{f.name}{f.required ? " *" : ""}</span>)}</div>
      <div className="muted" style={{ marginTop: 4 }}>* required · columns matched flexibly (aliases, case, spacing).</div>
    </div>
  );
}

/* ---- helpers ---- */
function downloadExport(dataset, format) {
  const a = document.createElement("a");
  a.href = api.exportUrl(dataset, format);
  a.download = `${dataset}.${format}`;
  document.body.appendChild(a); a.click(); a.remove();
}
const isNum = (t) => /int|float|numeric|real|double|decimal/.test(t || "");
function fmtCell(v) {
  if (v === null || v === undefined || v === "") return <span className="muted">—</span>;
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return v.toLocaleString();
  const s = String(v);
  if (/^\d{4}-\d{2}-\d{2}T/.test(s)) return s.slice(0, 10);
  return s;
}
function guessKey(cols) {
  return cols.find((c) => /material|code|supplier|po_number|id/.test(c)) || cols[0];
}
function iconForDataset(k) {
  return ({ materials: "cube", suppliers: "handshake", stock: "box", warehouse_stock: "layers", open_pos: "truck", receipts: "clipboard", demand: "chart", bom: "layers", production_plan: "factory" }[k]) || "database";
}
function iconForSource(k) {
  return ({ sqlserver: "server", mysql: "database", postgres: "database", access: "database", odbc: "odbc", sap_hana: "sap", sap_odbc: "sap", knime: "knime" }[k]) || "server";
}
