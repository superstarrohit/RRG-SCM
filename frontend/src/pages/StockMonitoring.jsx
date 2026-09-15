import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtMoney, fmtNum,
} from "../components/ui.jsx";
import { Donut, PALETTE } from "../components/charts.jsx";

const STATUS_COLOR = {
  stockout: PALETTE.red, critical: PALETTE.amber, low: PALETTE.blue,
  healthy: PALETTE.green, overstock: PALETTE.purple,
};
const STATUS_BADGE = { stockout: "short", critical: "short", low: "due_this_month", healthy: "ok", overstock: "excess" };

export default function StockMonitoring() {
  const [commodity, setCommodity] = React.useState("");
  const [buyer, setBuyer] = React.useState("");
  const { loading, data, error } = useApi(
    () => api.stockMonitoring({ commodity, buyer, top_n: 200 }),
    [commodity, buyer]
  );
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const f = data.filters || { commodity: [], buyer: [] };
  const head = (
    <PageHeader
      title="Stock Monitoring"
      subtitle="Stock health & stockout risk — current stock vs safety / refill / max levels, incoming POs and demand."
      asOf={data.as_of}
      right={
        <Filters f={f} commodity={commodity} buyer={buyer} setCommodity={setCommodity} setBuyer={setBuyer} />
      }
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  const k = data.kpis;
  const segs = data.status_distribution.map((s) => ({ label: s.label, value: s.count, color: STATUS_COLOR[s.status] || PALETTE.grey }));

  return (
    <div>
      {head}
      <div className="kpi-grid">
        <KpiCard label="Materials" value={fmtNum(k.materials)} icon="cube" tone="blue" />
        <KpiCard label="Stockouts" value={fmtNum(k.stockout)} icon="alert" tone={k.stockout ? "red" : "green"} />
        <KpiCard label="Critical (< safety)" value={fmtNum(k.critical)} icon="gauge" tone={k.critical ? "red" : "green"} />
        <KpiCard label="Low (< refill)" value={fmtNum(k.low)} icon="clock" tone={k.low ? "amber" : "green"} />
        <KpiCard label="Overstock (> max)" value={fmtNum(k.overstock)} icon="layers" tone={k.overstock ? "purple" : "green"} />
        <KpiCard label="At Risk" value={fmtNum(k.at_risk)} icon="pulse" tone={k.at_risk ? "red" : "green"} />
        <KpiCard label="Stock Value" value={fmtMoney(k.stock_value)} icon="dollar" tone="green" />
      </div>

      <div className="panel-grid">
        <Panel title="Stock Health Distribution">
          <Donut segments={segs} centerValue={fmtNum(k.materials)} centerLabel="materials" />
        </Panel>
        <Panel title="Risk Summary" hint="counts by severity">
          <div className="hbar-list">
            {data.status_distribution.map((s) => (
              <div className="hbar" key={s.status}>
                <div className="hbar-fill" style={{ width: `${(s.count / Math.max(1, k.materials)) * 100}%`, background: STATUS_COLOR[s.status] }} />
                <div className="hbar-left"><span className="hbar-dot" style={{ background: STATUS_COLOR[s.status] }} />{s.label}</div>
                <span className="hbar-val">{fmtNum(s.count)}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="⚠ Stockout Risk — Action List" hint={`${data.risk_items.length} items`}>
        <DataTable
          columns={[
            { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
            { key: "description", label: "Description" },
            { key: "commodity", label: "Commodity" },
            { key: "buyer", label: "Buyer" },
            { key: "sap_stock", label: "Stock", num: true, render: (v) => fmtNum(v) },
            { key: "safety_stock", label: "Safety", num: true, render: (v) => fmtNum(v) },
            { key: "refill_level", label: "Refill", num: true, render: (v) => fmtNum(v) },
            { key: "open_po", label: "Incoming", num: true, render: (v) => fmtNum(v) },
            { key: "demand", label: "Demand", num: true, render: (v) => fmtNum(v) },
            { key: "cover_days", label: "Cover (d)", num: true, render: (v) => v == null ? "—" : fmtNum(v, 1) },
            { key: "status", label: "Status", render: (v) => <Badge value={STATUS_BADGE[v] || v} /> },
          ]}
          rows={data.risk_items}
        />
      </Panel>
    </div>
  );
}

function Filters({ f, commodity, buyer, setCommodity, setBuyer }) {
  return (
    <div className="controls">
      <select value={commodity} onChange={(e) => setCommodity(e.target.value)} title="Commodity">
        <option value="">All commodities</option>
        {f.commodity.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
      <select value={buyer} onChange={(e) => setBuyer(e.target.value)} title="Buyer">
        <option value="">All buyers</option>
        {f.buyer.map((b) => <option key={b} value={b}>{b}</option>)}
      </select>
    </div>
  );
}
