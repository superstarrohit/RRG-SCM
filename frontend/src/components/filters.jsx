// Global slicer context: commodity, buyer, material, material description,
// supplier, location, and a date range — the full filter panel from the
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
  q: { icon: "search", label: "Description" },
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

// ---- Searchable combobox ----
// A text input that filters a long option list as you type and lets you
// pick exactly one (material, supplier) — used in place of a plain <select>
// once a list runs into the hundreds/thousands of entries. Closes on
// selection, blur-outside, or Escape; the current pick still shows once
// the menu is closed, and clearing goes back to "All".
function SearchSelect({ label, icon, value, onChange, options, getKey, getLabel, getSearch, placeholder, allLabel }) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const wrapRef = React.useRef(null);
  const selected = options.find((o) => getKey(o) === value);

  React.useEffect(() => {
    const onDoc = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const q = query.trim().toLowerCase();
  const filtered = (q ? options.filter((o) => getSearch(o).toLowerCase().includes(q)) : options).slice(0, 60);

  const pick = (code) => { onChange(code); setQuery(""); setOpen(false); };

  return (
    <div className="fp-field" ref={wrapRef}>
      <span className="fp-label">{label}</span>
      <div className={`fp-combo${open ? " open" : ""}`}>
        <Icon name={icon} size={14} />
        <input
          value={open ? query : (selected ? getLabel(selected) : "")}
          placeholder={placeholder}
          onFocus={() => setQuery("")}
          onClick={() => setOpen(true)}
          onChange={(e) => { setOpen(true); setQuery(e.target.value); }}
          onKeyDown={(e) => {
            if (e.key === "Escape") { setOpen(false); e.currentTarget.blur(); }
            if (e.key === "Enter" && filtered.length) pick(getKey(filtered[0]));
          }}
        />
        {value && (
          <button type="button" className="fp-combo-clear" onClick={() => pick("")} aria-label={`Clear ${label}`}>
            <Icon name="x" size={12} />
          </button>
        )}
      </div>
      {open && (
        <div className="fp-combo-menu" role="listbox">
          <div className="fp-combo-opt" onClick={() => pick("")}>{allLabel}</div>
          {filtered.map((o) => (
            <div
              key={getKey(o)}
              className={`fp-combo-opt${getKey(o) === value ? " active" : ""}`}
              onClick={() => pick(getKey(o))}
            >
              {getLabel(o)}
            </div>
          ))}
          {!filtered.length && <div className="fp-combo-empty">No matches</div>}
        </div>
      )}
    </div>
  );
}

// Debounced free-text search box — waits for a pause in typing before
// pushing into the shared filter state (and thus firing API calls). Matches
// material description (and, under the hood, code/PO/supplier too) across
// every report page.
function DescriptionSearch({ f }) {
  const [local, setLocal] = React.useState(f.q);
  React.useEffect(() => setLocal(f.q), [f.q]);
  React.useEffect(() => {
    const t = setTimeout(() => { if (local !== f.q) f.setQ(local); }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local]);
  return (
    <div className="fp-field">
      <span className="fp-label">Material Description</span>
      <div className="fp-combo">
        <Icon name="search" size={14} />
        <input
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          placeholder="Search by description…"
        />
        {local && (
          <button type="button" className="fp-combo-clear" onClick={() => setLocal("")} aria-label="Clear description search">
            <Icon name="x" size={12} />
          </button>
        )}
      </div>
    </div>
  );
}

// The global slicer panel — a persistent right-hand rail on desktop
// (collapsible to a slim icon rail), a slide-over drawer (behind a floating
// toggle) on narrow screens.
export function FiltersPanel() {
  const f = useFilters();
  const [open, setOpen] = React.useState(false);
  const [collapsed, setCollapsed] = React.useState(() => load("scm.filtersCollapsed") === "1");
  React.useEffect(() => save("scm.filtersCollapsed", collapsed ? "1" : ""), [collapsed]);
  if (!f) return null;

  const chipKeys = ["commodity", "buyer", "material", "supplier", "location", "q", "start", "end"];
  const activeChips = chipKeys.filter((k) => f[k]);

  // Collapsed is a desktop-only affordance (mobile already hides the panel
  // behind the drawer/FAB pair below) — render the slim rail in its place,
  // but keep the FAB/backdrop so mobile filter access is unaffected.
  const panel = collapsed ? (
    <aside className="filters-panel collapsed" aria-label="Filters (collapsed)">
      <button className="fp-expand" onClick={() => setCollapsed(false)} title="Show filters" aria-label="Show filters">
        <Icon name="filter" size={16} />
        {f.count > 0 && <span className="fp-count">{f.count}</span>}
        <Icon name="chevronDown" size={13} className="fp-expand-chev" />
      </button>
    </aside>
  ) : (
    <aside className={`filters-panel${open ? " open" : ""}`} aria-label="Filters">
      <div className="fp-head">
        <span className="fp-title"><Icon name="filter" size={15} /> Filters
          {f.count > 0 && <span className="fp-count">{f.count}</span>}
        </span>
        <button className="fp-collapse" onClick={() => setCollapsed(true)} title="Collapse filters" aria-label="Collapse filters">
          <Icon name="chevronDown" size={15} />
        </button>
        <button className="fp-close" onClick={() => setOpen(false)} aria-label="Close filters">
          <Icon name="x" size={15} />
        </button>
      </div>

      <div className="fp-body">
        <div className="fp-field">
          <span className="fp-label">Commodity</span>
          <select value={f.commodity} onChange={(e) => f.setCommodity(e.target.value)}>
            <option value="">All commodities</option>
            {f.options.commodity.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div className="fp-field">
          <span className="fp-label">Buyer</span>
          <select value={f.buyer} onChange={(e) => f.setBuyer(e.target.value)}>
            <option value="">All buyers</option>
            {f.options.buyer.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>

        <SearchSelect
          label="Material" icon="cube" placeholder="Search by material code…"
          value={f.material} onChange={f.setMaterial} options={f.options.material}
          getKey={(o) => o.code} getLabel={(o) => o.label} getSearch={(o) => o.code}
          allLabel="All materials"
        />

        <DescriptionSearch f={f} />

        <SearchSelect
          label="Supplier" icon="handshake" placeholder="Search by supplier name…"
          value={f.supplier} onChange={f.setSupplier} options={f.options.supplier}
          getKey={(o) => o.code} getLabel={(o) => o.label} getSearch={(o) => o.label}
          allLabel="All suppliers"
        />

        <div className="fp-field">
          <span className="fp-label">Location</span>
          <select value={f.location} onChange={(e) => f.setLocation(e.target.value)}>
            <option value="">All locations</option>
            {f.options.location.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>

        <div className="fp-field">
          <span className="fp-label">Date Range</span>
          <div className="fp-date-col">
            <span className="fp-date">
              <span className="fp-date-tag">From</span>
              <input type="date" value={f.start} onChange={(e) => f.setStart(e.target.value)} aria-label="From date" />
            </span>
            <span className="fp-date">
              <span className="fp-date-tag">To</span>
              <input type="date" value={f.end} onChange={(e) => f.setEnd(e.target.value)} aria-label="To date" />
            </span>
          </div>
        </div>

        {f.active && (
          <button className="btn ghost fp-clear" onClick={f.clear}>
            <Icon name="x" size={14} /> Clear all filters
          </button>
        )}

        {activeChips.length > 0 && (
          <div className="fp-chips">
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

        <p className="fp-hint">Applies across all report pages</p>
      </div>
    </aside>
  );

  return (
    <>
      {panel}
      <div className={`filters-backdrop${open ? " open" : ""}`} onClick={() => setOpen(false)} />
      <button className="filters-fab" onClick={() => setOpen(true)} aria-label="Open filters">
        <Icon name="filter" size={16} />
        {f.count > 0 && <span className="fp-count">{f.count}</span>}
      </button>
    </>
  );
}
