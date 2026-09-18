import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, Loading, ErrorState, useApi, fmtNum, fmtMoneyM,
} from "../components/ui.jsx";
import { RibbonChart, LineChart, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

// Ribbon values are large ₹ amounts — label the axis in ₹ millions.
const axisM = (v) => "₹" + Number(v / 1e6).toLocaleString("en-IN", { maximumFractionDigits: 0 }) + "M";

const GRAINS = [
  { key: "daily", label: "Daily" },
  { key: "weekly", label: "Weekly" },
  { key: "monthly", label: "Monthly" },
  { key: "quarterly", label: "Quarterly" },
  { key: "yearly", label: "Yearly" },
];

// Inventory value over time, with a daily→yearly drilldown toggle. Fetches
// its own series (respecting the global slicers) whenever the grain changes.
function InventoryTrend({ f }) {
  const [grain, setGrain] = React.useState("monthly");
  const { loading, data, error } = useApi(
    () => api.inventoryTimeseries({ ...f.params, grain }),
    [f.key, grain],
  );
  const points = (data?.points || []).map((p) => ({ label: p.label, value: p.value }));

  return (
    <Panel title="Inventory Value Trend">
      <div className="seg-toggle" role="tablist" aria-label="Time granularity">
        {GRAINS.map((g) => (
          <button
            key={g.key}
            role="tab"
            aria-selected={grain === g.key}
            className={`seg-btn${grain === g.key ? " active" : ""}`}
            onClick={() => setGrain(g.key)}
          >
            {g.label}
          </button>
        ))}
      </div>
      {error
        ? <ErrorState error={error} />
        : loading
          ? <div className="empty">Loading trend…</div>
          : points.length < 2
            ? <div className="empty">Not enough history at this granularity.</div>
            : <LineChart data={points} valueFormat={axisM} color={PALETTE.cyan} />}
    </Panel>
  );
}

export default function Dashboard() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.overview(f.params), [f.key]);
  if (loading) return <Loading kpis={4} />;
  if (error) return <ErrorState error={error} />;

  const k = data.kpis;
  const invRibbon = data.inventory_ribbon || { months: [], series: [] };
  const incRibbon = data.incoming_ribbon || { months: [], series: [] };

  return (
    <div>
      <PageHeader
        title="Overall SCM Dashboard"
        subtitle="Inventory value as on today and this month's incoming receipts, with supplier and material counts."
        asOf={data.as_of}
      />

      <div className="kpi-grid">
        <KpiCard label="Inventory Value (as on today)" value={fmtMoneyM(k.inventory_value)} icon="dollar" tone="green" />
        <KpiCard
          label="Incoming Receipts (this month)"
          value={fmtMoneyM(k.incoming_receipts_value)}
          sub={data.incoming_pending ? "awaiting movements upload" : undefined}
          icon="truck" tone="blue"
        />
        <KpiCard label="Suppliers" value={fmtNum(k.suppliers)} icon="handshake" tone="purple" />
        <KpiCard label="Materials" value={fmtNum(k.materials)} icon="cube" tone="cyan" />
      </div>

      {/* Inventory value over time with daily→yearly drilldown. */}
      <InventoryTrend f={f} />

      {/* Ribbon charts need the full page width for their time axis, so each
          sits in its own full-width row rather than a two-up grid. */}
      <Panel title="Inventory Value by Buyer">
        {invRibbon.series && invRibbon.series.length
          ? <RibbonChart series={invRibbon.series} months={invRibbon.months} valueFormat={axisM} />
          : <div className="empty">No inventory history to chart yet.</div>}
      </Panel>
      <Panel title="Incoming Value by Buyer" hint={data.incoming_pending ? "awaiting movements data" : ""}>
        {incRibbon.series && incRibbon.series.length
          ? <RibbonChart series={incRibbon.series} months={incRibbon.months} valueFormat={axisM} />
          : <div className="empty">Upload a movements file to see incoming value by buyer.</div>}
      </Panel>
    </div>
  );
}
