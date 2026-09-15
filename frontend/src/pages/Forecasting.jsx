import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtMoney, fmtNum,
} from "../components/ui.jsx";
import { VBars, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

export default function Forecasting() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.forecasting(f.params), [f.key]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Forecasting (M1 / M2 / M3)"
      subtitle="Rolling three-month forecast vs current supply (stock + incoming) — where coverage falls short."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  const k = data.kpis;
  const monthly = data.monthly.map((m) => ({ label: m.label, value: m.value }));
  const commBars = data.by_commodity.map((r) => ({ label: r.name, value: r.value }));

  return (
    <div>
      {head}
      <div className="kpi-grid">
        <KpiCard label="Materials Forecast" value={fmtNum(k.materials)} icon="cube" tone="blue" />
        <KpiCard label="M1 Forecast" value={fmtNum(k.m1_qty)} icon="target" tone="purple" />
        <KpiCard label="M2 Forecast" value={fmtNum(k.m2_qty)} icon="target" tone="cyan" />
        <KpiCard label="M3 Forecast" value={fmtNum(k.m3_qty)} icon="target" tone="amber" />
        <KpiCard label="3-Month Value" value={fmtMoney(k.forecast_value_3m)} icon="dollar" tone="green" />
        <KpiCard label="Short Items" value={fmtNum(k.short_items)} icon="alert" tone={k.short_items ? "red" : "green"} />
      </div>

      <div className="panel-grid">
        <Panel title="Forecast by Month">
          <VBars data={monthly} valueFormat={(v) => fmtNum(v)} color={PALETTE.purple} />
        </Panel>
        <Panel title="3-Month Forecast by Commodity">
          <VBars data={commBars} valueFormat={(v) => fmtNum(v)} color={PALETTE.cyan} />
        </Panel>
      </div>

      <Panel title="Forecast vs Supply — Coverage Gaps">
        <DataTable
          columns={[
            { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
            { key: "description", label: "Description" },
            { key: "commodity", label: "Commodity" },
            { key: "buyer", label: "Buyer" },
            { key: "stock", label: "Stock", num: true, render: (v) => fmtNum(v) },
            { key: "incoming", label: "Incoming", num: true, render: (v) => fmtNum(v) },
            { key: "m1_qty", label: "M1", num: true, render: (v) => fmtNum(v) },
            { key: "m2_qty", label: "M2", num: true, render: (v) => fmtNum(v) },
            { key: "m3_qty", label: "M3", num: true, render: (v) => fmtNum(v) },
            { key: "total_3m", label: "Total 3M", num: true, render: (v) => fmtNum(v) },
            { key: "gap_3m", label: "Gap", num: true, render: (v) => v > 0 ? <span style={{ color: "var(--red)" }}>{fmtNum(v)}</span> : fmtNum(v) },
            { key: "status", label: "Status", render: (v) => <Badge value={v === "short" ? "short" : v === "excess" ? "excess" : "ok"} /> },
          ]}
          rows={data.rows}
        />
      </Panel>
    </div>
  );
}
