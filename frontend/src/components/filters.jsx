// Global slicer context: commodity, buyer, material, supplier, location, a
// free-text search box and a date range — the full filter panel from the
// reference report — shared across every report page via localStorage.
import React from "react";
import { api } from "../api/client.js";
import Icon from "./icons.jsx";

const FiltersContext = React.createContext(null);

const load = (k) => { try { return localStorage.getItem(k) || ""; } catch { return ""; } };
const save = (k, v) => { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch { /* ignore */ } };

export function FiltersProvider({ children }) {
  const [commodity, setCommodity] = React.useState(() => load("scm.commodity"));
  const [buyer, setBuyer] = React.useState(() => load("scm.buyer"));
  const [material, setMaterial] = React.useState(() => load("scm.material"));
  const [supplier, setSupplier] = React.useState(() => load("scm.supplier"));
  const [location, setLocation] = React.useState(() => load("scm.location"));
  const [q, setQ] = React.useState(() => load("scm.q"));
  const [start, setStart] = React.useState(() => load("scm.start"));
  const [end, setEnd] = React.useState(() => load("scm.end"));
  const [options, setOptions] = React.useState({ commodity: [], buyer: [], material: [], supplier: [], location: [] });

  React.useEffect(() => {
    api.slicers().then(setOptions).catch(() => {});
  }, []);
  React.useEffect(() => save("scm.commodity", commodity), [commodity]);
  React.useEffect(() => save("scm.buyer", buyer), [buyer]);
  React.useEffect(() => save("scm.material", material), [material]);
  React.useEffect(() => save("scm.supplier", supplier), [supplier]);
  React.useEffect(() => save("scm.location", location), [location]);
  React.useEffect(() => save("scm.q", q), [q]);
  React.useEffect(() => save("scm.start", start), [start]);
  React.useEffect(() => save("scm.end", end), [end]);

  // Only send non-empty params.
  const params = {};
  if (commodity) params.commodity = commodity;
  if (buyer) params.buyer = buyer;
  if (material) params.material = material;
  if (supplier) params.supplier = supplier;
  if (location) params.location = location;
  if (q) params.q = q;
  if (start) params.start = start;
  if (end) params.end = end;

  const count = [commodity, buyer, material, supplier, location, q, start, end].filter(Boolean).length;

  const value = {
    commodity, buyer, material, supplier, location, q, start, end,
    setCommodity, setBuyer, setMaterial, setSupplier, setLocation, setQ, setStart, setEnd,
    options, setOptions, params, count,
    active: count > 0,
    key: `${commodity}|${buyer}|${material}|${supplier}|${location}|${q}|${start}|${end}`, // effect deps
    clear: () => {
      setCommodity(""); setBuyer(""); setMaterial(""); setSupplier("");
      setLocation(""); setQ(""); setStart(""); setEnd("");
    },
  };
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters() {
  return React.useContext(FiltersContext);
}

const CHIP_META = {
  commodity: { icon: "layers", label: "Commodity" },
  buyer: { icon: "users", label: "Buyer" },
  material: { icon: "cube", label: "Material" },
  supplier: { icon: "handshake", label: "Supplier" },
  location: { icon: "database", label: "Location" },
  q: { icon: "search", label: "Search" },
  start: { icon: "clock", label: "From" },
  end: { icon: "clock", label: "To" },
};
const SETTER = {
  commodity: "setCommodity", buyer: "setBuyer", material: "setMaterial",
  supplier: "setSupplier", location: "setLocation", q: "setQ",
  start: "setStart", end: "setEnd",
};

function labelFor(f, key, value) {
  if (!value) return "";
  if (key === "material") {
    const m = f.options.material.find((o) => o.code === value);
    return m ? m.label : value;
  }
  if (key === "supplier") {
    const s = f.options.supplier.find((o) => o.code === value);
    return s ? s.label : value;
  }
  if (key === "q") return `"${value}"`;
  return value;
}

// Debounced free-text search box — waits for a pause in typing before
// pushing into the shared filter state (and thus firing API calls).
function SearchField({ f }) {
  const [local, setLocal] = React.useState(f.q);
  React.useEffect(() => setLocal(f.q), [f.q]);
  React.useEffect(() => {
    const t = setTimeout(() => { if (local !== f.q) f.setQ(local); }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local]);
  return (
    <div className="fb-field" style={{ minWidth: 200 }}>
      <span className="fb-field-label">Search</span>
      <span className="ws-search" style={{ minWidth: 0 }}>
        <Icon name="search" size={14} />
        <input
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          placeholder="Material, description, PO, supplier…"
        />
      </span>
    </div>
  );
}

// The global slicer bar rendered under the top nav — collapsible on mobile.
export function FilterBar() {
  const f = useFilters();
  const [open, setOpen] = React.useState(false);
  if (!f) return null;

  const chipKeys = ["commodity", "buyer", "material", "supplier", "location", "q", "start", "end"];
  const activeChips = chipKeys.filter((k) => f[k]);

  return (
    <div className={`filterbar${open ? " open" : ""}`}>
      <div className="fb-head">
        <button className="fb-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <Icon name="filter" size={14} />
          Filters
          {f.count > 0 && <span className="fb-count">{f.count}</span>}
          <Icon name="chevronDown" size={14} className={`fb-chevron${open ? " open" : ""}`} />
        </button>
      </div>

      <div className="fb-row">
        <span className="fb-label"><Icon name="filter" size={14} /> Filters</span>

        <SearchField f={f} />

        <div className="fb-field">
          <span className="fb-field-label">Commodity</span>
          <select value={f.commodity} onChange={(e) => f.setCommodity(e.target.value)}>
            <option value="">All commodities</option>
            {f.options.commodity.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div className="fb-field">
          <span className="fb-field-label">Buyer</span>
          <select value={f.buyer} onChange={(e) => f.setBuyer(e.target.value)}>
            <option value="">All buyers</option>
            {f.options.buyer.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>

        <div className="fb-field">
          <span className="fb-field-label">Material</span>
          <select value={f.material} onChange={(e) => f.setMaterial(e.target.value)}>
            <option value="">All materials</option>
            {f.options.material.map((m) => <option key={m.code} value={m.code}>{m.label}</option>)}
          </select>
        </div>

        <div className="fb-field">
          <span className="fb-field-label">Supplier</span>
          <select value={f.supplier} onChange={(e) => f.setSupplier(e.target.value)}>
            <option value="">All suppliers</option>
            {f.options.supplier.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
          </select>
        </div>

        <div className="fb-field">
          <span className="fb-field-label">Location</span>
          <select value={f.location} onChange={(e) => f.setLocation(e.target.value)}>
            <option value="">All locations</option>
            {f.options.location.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>

        <div className="fb-field">
          <span className="fb-field-label">Date Range</span>
          <span className="fb-date" title="Date range (time-series pages)">
            <Icon name="clock" size={13} />
            <input type="date" value={f.start} onChange={(e) => f.setStart(e.target.value)} aria-label="From date" />
            <span className="fb-dash">→</span>
            <input type="date" value={f.end} onChange={(e) => f.setEnd(e.target.value)} aria-label="To date" />
          </span>
        </div>

        <span className="fb-spacer" />
        {f.active && (
          <button className="btn ghost" onClick={f.clear} style={{ padding: "7px 12px", fontSize: 12.5 }}>
            <Icon name="x" size={14} /> Clear all
          </button>
        )}
        <span className="fb-hint">Applies across all report pages</span>
      </div>

      {activeChips.length > 0 && (
        <div className="fb-chips">
          {activeChips.map((k) => (
            <span className="fb-chip" key={k}>
              <Icon name={CHIP_META[k].icon} size={12} />
              {CHIP_META[k].label}: {labelFor(f, k, f[k])}
              <button onClick={() => f[SETTER[k]]("")} aria-label={`Remove ${CHIP_META[k].label} filter`}>
                <Icon name="x" size={10} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
