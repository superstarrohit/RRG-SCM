import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, Loading, ErrorState, useApi, fmtNum, fmtMoneyM,
} from "../components/ui.jsx";
import { Donut3D, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

// Stable-ish colour per buyer donut slice, cycling the theme palette.
const SLICE = [PALETTE.purple, PALETTE.blue, PALETTE.cyan, PALETTE.green, PALETTE.amber, PALETTE.red, "var(--primary-2)"];
const toSegs = (rows) => (rows || []).map((r, i) => ({
  label: r.name || "Unassigned", value: r.value, color: SLICE[i % SLICE.length],
}));

export default function Dashboard() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.overview(f.params), [f.key]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const k = data.kpis;
  const invSegs = toSegs(data.inventory_by_buyer);
  const incSegs = toSegs(data.incoming_by_buyer);

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

      <div className="panel-grid">
        <Panel title="Inventory Value by Buyer">
          <Donut3D segments={invSegs} centerValue={fmtMoneyM(k.inventory_value)} centerLabel="inventory" />
        </Panel>
        <Panel title="Incoming Value by Buyer" hint={data.incoming_pending ? "awaiting movements data" : ""}>
          {incSegs.length
            ? <Donut3D segments={incSegs} centerValue={fmtMoneyM(k.incoming_receipts_value)} centerLabel="incoming" />
            : <div className="empty">Upload a movements file to see incoming value by buyer.</div>}
        </Panel>
      </div>
    </div>
  );
}
