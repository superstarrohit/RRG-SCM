import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtMoney, fmtNum,
} from "../components/ui.jsx";
import { VBars, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

const MVT_BADGE = { GRN: "ok", Issue: "short", Transfer: "due_this_month", Adjustment: "excess" };

export default function Movements() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.movements(f.params), [f.key]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Material Movements"
      subtitle="Goods movements — receipts, issues, transfers and adjustments — by type and over time."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  const k = data.kpis;
  const typeBars = data.by_type.map((t) => ({ label: t.mvt_type, value: Math.abs(t.value) }));

  return (
    <div>
      {head}
      <div className="kpi-grid">
        <KpiCard label="Movements" value={fmtNum(k.movements)} icon="flow" tone="blue" />
        <KpiCard label="Inflow Qty" value={fmtNum(k.inflow_qty)} icon="download" tone="green" />
        <KpiCard label="Outflow Qty" value={fmtNum(k.outflow_qty)} icon="upload" tone="red" />
        <KpiCard label="Net Qty" value={fmtNum(k.net_qty)} icon="merge" tone={k.net_qty >= 0 ? "green" : "red"} />
        <KpiCard label="Movement Types" value={fmtNum(k.movement_types)} icon="layers" tone="purple" />
      </div>

      <div className="panel-grid">
        <Panel title="Movement Value by Type">
          <VBars data={typeBars} valueFormat={(v) => "$" + fmtNum(v)} color={PALETTE.purple} />
        </Panel>
        <Panel title="Movement Type Summary">
          <DataTable
            columns={[
              { key: "mvt_type", label: "Type", render: (v) => <Badge value={MVT_BADGE[v] || v} /> },
              { key: "count", label: "Count", num: true },
              { key: "qty", label: "Net Qty", num: true, render: (v) => fmtNum(v) },
              { key: "value", label: "Value", num: true, render: fmtMoney },
            ]}
            rows={data.by_type}
          />
        </Panel>
      </div>

      <Panel title="Recent Movements">
        <DataTable
          columns={[
            { key: "movement_date", label: "Date", render: (v) => <span className="mono">{v || "—"}</span> },
            { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
            { key: "description", label: "Description" },
            { key: "mvt_type", label: "Type", render: (v) => <Badge value={MVT_BADGE[v] || v} /> },
            { key: "qty", label: "Qty", num: true, render: (v) => <span style={{ color: v < 0 ? "var(--red)" : "var(--green)" }}>{fmtNum(v)}</span> },
            { key: "value", label: "Value", num: true, render: fmtMoney },
          ]}
          rows={data.recent}
        />
      </Panel>
    </div>
  );
}
