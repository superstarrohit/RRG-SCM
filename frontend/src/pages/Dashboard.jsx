import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, Loading, ErrorState, useApi, fmtNum, fmtMoneyM,
} from "../components/ui.jsx";
import { LineChart, DrillBars, VBars, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

// Ribbon values are large ₹ amounts — label the axis in ₹ millions.
const axisM = (v) => "₹" + Number(v / 1e6).toLocaleString("en-IN", { maximumFractionDigits: 0 }) + "M";

// Power BI–style hierarchy: each level drills into the next.
const HIER = ["yearly", "quarterly", "monthly", "daily"];
const LEVEL_NAME = { yearly: "Year", quarterly: "Quarter", monthly: "Month", daily: "Day" };

// Inventory value over time with a Power BI-style click-to-drill hierarchy
// (Year → Quarter → Month → Day). Clicking a bar drills into that period;
// the breadcrumb and ▲ button drill back up. Respects the global slicers.
function InventoryDrilldown({ f }) {
  // Each frame scopes one level to a parent period's date window.
  const [stack, setStack] = React.useState([{ level: "yearly", label: "All" }]);
  const [chart, setChart] = React.useState("bar");
  const cur = stack[stack.length - 1];
  const nextLevel = HIER[HIER.indexOf(cur.level) + 1] || null;

  // Reset the drill path whenever the global filters change.
  React.useEffect(() => { setStack([{ level: "yearly", label: "All" }]); }, [f.key]);

  // Drilling into a period pins the request to its exact calendar bounds;
  // at the top ("All") frame there's nothing to pin, so the global date-range
  // filter (already in f.params) is left to take effect on its own — setting
  // start/end here to undefined would instead erase it.
  const { loading, data, error } = useApi(
    () => api.inventoryTimeseries({
      ...f.params, grain: cur.level,
      ...(cur.start ? { start: cur.start, end: cur.end } : {}),
    }),
    [f.key, cur.level, cur.start, cur.end],
  );
  const points = data?.points || [];

  const drillInto = (p) => {
    if (!nextLevel) return;
    setStack((s) => [...s, { level: nextLevel, start: p.start, end: p.end, label: p.label }]);
  };
  const jumpTo = (i) => setStack((s) => s.slice(0, i + 1));
  const drillUp = () => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s));

  return (
    <Panel title="Inventory Value Trend">
      <div className="drill-bar">
        <button className="drill-up" onClick={drillUp} disabled={stack.length === 1}
                title="Drill up" aria-label="Drill up">▲</button>
        <nav className="crumbs" aria-label="Drilldown path">
          {stack.map((fr, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="crumb-sep">›</span>}
              <button className={`crumb${i === stack.length - 1 ? " active" : ""}`}
                      onClick={() => jumpTo(i)}>{fr.label}</button>
            </React.Fragment>
          ))}
        </nav>
        <span className="drill-level">
          by {LEVEL_NAME[cur.level]}
          {nextLevel && <span className="drill-hint"> · click a bar to drill into {LEVEL_NAME[nextLevel].toLowerCase()}s</span>}
        </span>
        <span style={{ flex: 1 }} />
        <div className="seg-toggle" role="tablist" aria-label="Chart type">
          {[["bar", "Bars"], ["line", "Line"]].map(([k, lbl]) => (
            <button key={k} role="tab" aria-selected={chart === k}
                    className={`seg-btn${chart === k ? " active" : ""}`}
                    onClick={() => setChart(k)}>{lbl}</button>
          ))}
        </div>
      </div>
      {error
        ? <ErrorState error={error} />
        : loading
          ? <div className="empty">Loading trend…</div>
          : !points.length
            ? <div className="empty">No inventory history in this period.</div>
            : chart === "bar"
              ? <DrillBars data={points} valueFormat={axisM} color={PALETTE.cyan}
                           onBar={drillInto} clickable={!!nextLevel} />
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
  const invByBuyer = (data.inventory_by_buyer || []).map((r) => ({ label: r.name || "Unassigned", value: r.value }));

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

      {/* Inventory value over time with Power BI-style click-to-drill. */}
      <InventoryDrilldown f={f} />

      {/* Latest (as-on-today) inventory value per buyer — buyers on X. */}
      <Panel title="Latest Inventory Value by Buyer">
        {invByBuyer.length
          ? <VBars data={invByBuyer} valueFormat={axisM} color={PALETTE.green} showValues />
          : <div className="empty">No inventory to chart yet.</div>}
      </Panel>

      <Panel title="Incoming Value by Buyer" hint={data.incoming_pending ? "awaiting movements data" : ""}>
        <div className="empty">Upload a movements file to see incoming value by buyer.</div>
      </Panel>
    </div>
  );
}
