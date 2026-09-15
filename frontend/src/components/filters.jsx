// Global slicer context: commodity + buyer, shared across all report pages.
import React from "react";
import { api } from "../api/client.js";
import Icon from "./icons.jsx";

const FiltersContext = React.createContext(null);

const load = (k) => { try { return localStorage.getItem(k) || ""; } catch { return ""; } };
const save = (k, v) => { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch { /* ignore */ } };

export function FiltersProvider({ children }) {
  const [commodity, setCommodity] = React.useState(() => load("scm.commodity"));
  const [buyer, setBuyer] = React.useState(() => load("scm.buyer"));
  const [options, setOptions] = React.useState({ commodity: [], buyer: [] });

  React.useEffect(() => {
    api.slicers().then(setOptions).catch(() => {});
  }, []);
  React.useEffect(() => save("scm.commodity", commodity), [commodity]);
  React.useEffect(() => save("scm.buyer", buyer), [buyer]);

  // Only send non-empty params.
  const params = {};
  if (commodity) params.commodity = commodity;
  if (buyer) params.buyer = buyer;

  const value = {
    commodity, buyer, setCommodity, setBuyer, options, setOptions, params,
    active: !!(commodity || buyer),
    key: `${commodity}|${buyer}`, // handy for effect deps
    clear: () => { setCommodity(""); setBuyer(""); },
  };
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters() {
  return React.useContext(FiltersContext);
}

// The global slicer bar rendered under the top nav.
export function FilterBar() {
  const f = useFilters();
  if (!f) return null;
  return (
    <div className="filterbar">
      <span className="fb-label"><Icon name="filter" size={14} /> Filters</span>
      <select value={f.commodity} onChange={(e) => f.setCommodity(e.target.value)} title="Commodity">
        <option value="">All commodities</option>
        {f.options.commodity.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
      <select value={f.buyer} onChange={(e) => f.setBuyer(e.target.value)} title="Buyer">
        <option value="">All buyers</option>
        {f.options.buyer.map((b) => <option key={b} value={b}>{b}</option>)}
      </select>
      {f.active && (
        <button className="btn ghost" onClick={f.clear} style={{ padding: "7px 12px", fontSize: 12.5 }}>
          <Icon name="x" size={14} /> Clear
        </button>
      )}
      <span className="fb-hint muted">Applies across all report pages</span>
    </div>
  );
}
