import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtNum,
} from "../components/ui.jsx";
import { VBars, PALETTE } from "../components/charts.jsx";

export default function FGPlanning() {
  const { loading, data, error } = useApi(() => api.fgPlanning({ top_n: 50 }), []);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Finished-Goods Planning"
      subtitle="Production plan exploded through the BOM, checked against component availability."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  const k = data.kpis;
  const reqBars = data.component_requirements.slice(0, 8).map((r) => ({
    label: r.component, value: r.required,
  }));

  return (
    <div>
      {head}
      <div className="kpi-grid">
        <KpiCard label="FG Planned" value={fmtNum(k.fg_planned)} icon="factory" tone="blue" />
        <KpiCard label="FG At Risk" value={fmtNum(k.fg_at_risk)} icon="alert" tone={k.fg_at_risk ? "red" : "green"} />
        <KpiCard label="Components Required" value={fmtNum(k.components_required)} icon="cube" tone="purple" />
        <KpiCard label="Components Short" value={fmtNum(k.components_short)} icon="alert" tone={k.components_short ? "red" : "green"} />
      </div>

      <Panel title="Top Component Requirements" hint="gross, across the plan">
        <VBars data={reqBars} valueFormat={(v) => fmtNum(v)} color={PALETTE.green} />
      </Panel>

      <Panel title="FG Feasibility">
        <DataTable
          columns={[
            { key: "material_code", label: "Finished Good", render: (v) => <span className="mono strong">{v}</span> },
            { key: "description", label: "Description" },
            { key: "planned_qty", label: "Planned Qty", num: true, render: (v) => fmtNum(v) },
            { key: "component_count", label: "Components", num: true },
            { key: "at_risk", label: "Status", render: (v) => <Badge value={v ? "short" : "ok"} /> },
            { key: "constraining_components", label: "Constraining", render: (v) => v && v.length ? v.map((c) => <span className="tag" key={c}>{c}</span>) : <span className="muted">—</span> },
          ]}
          rows={data.fg_feasibility}
        />
      </Panel>

      <Panel title="Component Requirements vs Availability">
        <DataTable
          columns={[
            { key: "component", label: "Component", render: (v) => <span className="mono strong">{v}</span> },
            { key: "description", label: "Description" },
            { key: "required", label: "Required", num: true, render: (v) => fmtNum(v) },
            { key: "on_hand", label: "On Hand", num: true, render: (v) => fmtNum(v) },
            { key: "incoming", label: "Incoming", num: true, render: (v) => fmtNum(v) },
            { key: "available", label: "Available", num: true, render: (v) => fmtNum(v) },
            { key: "shortage", label: "Shortage", num: true, render: (v) => fmtNum(v) },
            { key: "status", label: "Status", render: (v) => <Badge value={v} /> },
          ]}
          rows={data.component_requirements}
        />
      </Panel>
    </div>
  );
}
