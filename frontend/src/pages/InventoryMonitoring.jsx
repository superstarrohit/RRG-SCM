import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader,
  Loading, ErrorState, EmptyState, useApi, fmtMoney, fmtNum,
} from "../components/ui.jsx";
import { LineChart, VBars, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

export default function InventoryMonitoring() {
  const flt = useFilters();
  const [metric, setMetric] = React.useState("value");
  const { loading, data, error } = useApi(
    () => api.inventoryMonitoring({ ...flt.params, top_n: 12 }),
    [flt.key]
  );
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Inventory Monitoring"
      subtitle="Stock value & quantity trends over time, with breakdowns by commodity, location and buyer."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  const k = data.kpis;
  const isVal = metric === "value";
  const line = data.timeline.map((t) => ({ label: t.label, value: isVal ? t.value : t.qty }));
  const commBars = data.by_commodity.map((r) => ({ label: r.name, value: r.value }));
  const locBars = data.by_location.map((r) => ({ label: r.name, value: r.value }));
  const buyerBars = data.by_buyer.map((r) => ({ label: r.name, value: r.value }));

  return (
    <div>
      {head}
      <div className="kpi-grid">
        <KpiCard label="Inventory Value" value={fmtMoney(k.inventory_value)} icon="dollar" tone="green"
          delta={{ value: `${fmtNum(Math.abs(k.mom_change_pct), 1)}% MoM`, dir: k.mom_change_pct >= 0 ? "up" : "down" }} />
        <KpiCard label="Inventory Qty" value={fmtNum(k.inventory_qty)} icon="cube" tone="blue" />
        <KpiCard label="Materials" value={fmtNum(k.materials)} icon="box" tone="purple" />
        <KpiCard label="Locations" value={fmtNum(k.locations)} icon="database" tone="cyan" />
        <KpiCard label="Commodities" value={fmtNum(k.commodities)} icon="layers" tone="amber" />
        <KpiCard label="Latest Snapshot" value={k.as_of_snapshot || "—"} icon="trend" tone="purple" />
      </div>

      <Panel title="Inventory Trend"
        hint={undefined}>
        <div className="controls" style={{ justifyContent: "flex-end", marginTop: -6, marginBottom: 10 }}>
          <div className="seg" style={{ marginBottom: 0 }}>
            <button className={isVal ? "on" : ""} onClick={() => setMetric("value")}>Value</button>
            <button className={!isVal ? "on" : ""} onClick={() => setMetric("qty")}>Quantity</button>
          </div>
        </div>
        <LineChart data={line} valueFormat={isVal ? (v) => "$" + fmtNum(v / 1000) + "k" : (v) => fmtNum(v)} color={isVal ? PALETTE.cyan : PALETTE.green} />
      </Panel>

      <div className="panel-grid">
        <Panel title="Inventory Value by Commodity">
          <VBars data={commBars} valueFormat={(v) => "$" + fmtNum(v / 1000) + "k"} color={PALETTE.purple} />
        </Panel>
        <Panel title="Inventory Value by Location">
          <VBars data={locBars} valueFormat={(v) => "$" + fmtNum(v / 1000) + "k"} color={PALETTE.blue} />
        </Panel>
      </div>

      <Panel title="Inventory Value by Buyer">
        <VBars data={buyerBars} valueFormat={(v) => "$" + fmtNum(v / 1000) + "k"} color={PALETTE.cyan} />
      </Panel>
    </div>
  );
}
