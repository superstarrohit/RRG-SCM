import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, Loading, ErrorState, useApi, fmtNum, fmtMoneyM,
} from "../components/ui.jsx";
import { DrillBars, VBars, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

// Ribbon values are large ₹ amounts — label the axis in ₹ millions. Rounding
// to whole millions made distinct buyer/supplier totals in the ₹0.3M-1.5M
// range all display as the same "₹1M", so allow one decimal (trimmed when
// the value doesn't need it) to keep close-but-different bars distinguishable.
const axisM = (v) => "₹" + Number(v / 1e6).toLocaleString("en-IN", { maximumFractionDigits: 1 }) + "M";
// Quantity trends have no currency and a much smaller scale — a plain count.
const axisQty = (v) => Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });

// Power BI–style hierarchy: each level shows every period at that granularity.
const HIER = ["yearly", "quarterly", "monthly", "daily"];
const LEVEL_NAME = { yearly: "Year", quarterly: "Quarter", monthly: "Month", daily: "Day" };

// Value over time with a granularity switcher (Year / Quarter / Month / Day).
// Unlike a Power BI-style "drill into this one bar" hierarchy — which narrows
// the chart down to a single branch and hides every other period — clicking
// a bar (or a level tab) re-renders the WHOLE chart at the next granularity,
// so every period at that level stays visible at once. Respects the global
// slicers. `apiFn` fetches {points, pending?} for the current level;
// `emptyMessage` covers both "no data in this window" and (via `pending`)
// "not wired up yet" cases — e.g. incoming receipts before a movements file
// is loaded.
function TrendDrilldown({ f, title, apiFn, color, emptyMessage, hint, valueFormat = axisM }) {
  const [grain, setGrain] = React.useState("yearly");
  const grainIdx = HIER.indexOf(grain);
  const nextLevel = HIER[grainIdx + 1] || null;

  // Reset to the coarsest level whenever the global filters change.
  React.useEffect(() => { setGrain("yearly"); }, [f.key]);

  const { loading, data, error } = useApi(
    () => apiFn({ ...f.params, grain }),
    [f.key, grain],
  );
  const points = data?.points || [];
  const pending = !!data?.pending;

  const drillDown = () => { if (nextLevel) setGrain(nextLevel); };

  return (
    <Panel title={title} hint={pending ? (hint || "") : ""}>
      <div className="drill-bar">
        <nav className="crumbs" aria-label="Granularity">
          {HIER.map((lvl, i) => (
            <React.Fragment key={lvl}>
              {i > 0 && <span className="crumb-sep">›</span>}
              <button className={`crumb${lvl === grain ? " active" : ""}`}
                      onClick={() => setGrain(lvl)}>{LEVEL_NAME[lvl]}</button>
            </React.Fragment>
          ))}
        </nav>
        <span className="drill-level">
          {nextLevel && <span className="drill-hint"> · click a bar (or a level above) to see every {LEVEL_NAME[nextLevel].toLowerCase()}</span>}
        </span>
      </div>
      {error
        ? <ErrorState error={error} />
        : loading
          ? <div className="empty">Loading trend…</div>
          : !points.length
            ? <div className="empty">{emptyMessage}</div>
            : <DrillBars data={points} valueFormat={valueFormat} color={color}
                         onBar={drillDown} clickable={!!nextLevel} />}
    </Panel>
  );
}

// Quantity counterparts of the value timeseries — same endpoints, metric=qty.
const inventoryQtyTimeseries = (p) => api.inventoryTimeseries({ ...p, metric: "qty" });
const incomingQtyTimeseries = (p) => api.incomingTimeseries({ ...p, metric: "qty" });

export default function Dashboard() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.overview(f.params), [f.key]);
  if (loading) return <Loading kpis={4} />;
  if (error) return <ErrorState error={error} />;

  const k = data.kpis;
  const invByBuyer = (data.inventory_by_buyer || []).map((r) => ({ label: r.name || "Unassigned", value: r.value }));
  const incomingByBuyer = (data.incoming_by_buyer || []).map((r) => ({ label: r.name || "Unassigned", value: r.value }));
  const incomingBySupplier = (data.incoming_by_supplier || []).map((r) => ({ label: r.name || "Unassigned", value: r.value }));

  return (
    <div>
      <PageHeader
        title="Overall SCM Dashboard"
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

      {/* Value over time with Power BI-style click-to-drill. */}
      <TrendDrilldown f={f} title="Inventory Value Trend" apiFn={api.inventoryTimeseries}
                      color={PALETTE.cyan} emptyMessage="No inventory history in this period." />
      <TrendDrilldown f={f} title="Incoming Receipts Trend" apiFn={api.incomingTimeseries}
                      color={PALETTE.blue} hint="awaiting movements upload"
                      emptyMessage="Upload a movements file to see incoming receipts over time." />

      {/* Quantity counterparts — kept as separate single-axis charts rather
          than a second scale on the value trends above. */}
      <TrendDrilldown f={f} title="Stock Quantity Trend" apiFn={inventoryQtyTimeseries}
                      color={PALETTE.cyan} valueFormat={axisQty}
                      emptyMessage="No inventory history in this period." />
      <TrendDrilldown f={f} title="Receipts Quantity Trend" apiFn={incomingQtyTimeseries}
                      color={PALETTE.blue} valueFormat={axisQty} hint="awaiting movements upload"
                      emptyMessage="Upload a movements file to see incoming receipts over time." />

      {/* Latest (as-on-today) inventory value per buyer — buyers on X. */}
      <Panel title="Latest Inventory Value by Buyer">
        {invByBuyer.length
          ? <VBars data={invByBuyer} valueFormat={axisM} color={PALETTE.green} showValues />
          : <div className="empty">No inventory to chart yet.</div>}
      </Panel>

      <Panel title="Incoming Value by Buyer" hint={data.incoming_pending ? "awaiting movements data" : ""}>
        {incomingByBuyer.length
          ? <VBars data={incomingByBuyer} valueFormat={axisM} color={PALETTE.blue} showValues />
          : <div className="empty">
              {data.incoming_pending
                ? "Upload a movements file to see incoming value by buyer."
                : "No incoming receipts this month."}
            </div>}
      </Panel>

      <Panel title="Incoming Value by Supplier" hint={data.incoming_pending ? "awaiting movements data" : ""}>
        {incomingBySupplier.length
          ? <VBars data={incomingBySupplier} valueFormat={axisM} color={PALETTE.purple} showValues />
          : <div className="empty">
              {data.incoming_pending
                ? "Upload a movements file to see incoming value by supplier."
                : "No incoming receipts this month."}
            </div>}
      </Panel>
    </div>
  );
}
