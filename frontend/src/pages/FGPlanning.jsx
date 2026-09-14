import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard,
  Panel,
  DataTable,
  Badge,
  Loading,
  ErrorState,
  EmptyState,
  useApi,
  fmtNum,
} from "../components/ui.jsx";

export default function FGPlanning() {
  const { loading, data, error } = useApi(() => api.fgPlanning({ top_n: 50 }), []);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const header = (
    <div className="page-header">
      <div>
        <h1>Finished-Goods Planning</h1>
        <p>Production plan exploded through BOM · component availability & feasibility{data.as_of ? ` · as of ${data.as_of}` : ""}</p>
      </div>
    </div>
  );

  if (data.empty)
    return (
      <div>
        {header}
        <EmptyState message={data.message} />
      </div>
    );

  const k = data.kpis;
  return (
    <div>
      {header}
      <div className="kpi-grid">
        <KpiCard label="FG Planned" value={fmtNum(k.fg_planned)} />
        <KpiCard label="FG At Risk" value={fmtNum(k.fg_at_risk)} accent={k.fg_at_risk ? "red" : "green"} />
        <KpiCard label="Components Required" value={fmtNum(k.components_required)} />
        <KpiCard label="Components Short" value={fmtNum(k.components_short)} accent={k.components_short ? "red" : "green"} />
      </div>

      <Panel title="FG Feasibility">
        <DataTable
          columns={[
            { key: "material_code", label: "Finished Good" },
            { key: "description", label: "Description" },
            { key: "planned_qty", label: "Planned Qty", num: true, render: (v) => fmtNum(v) },
            { key: "component_count", label: "Components", num: true },
            {
              key: "at_risk",
              label: "Status",
              render: (v) => <Badge value={v ? "short" : "ok"} />,
            },
            {
              key: "constraining_components",
              label: "Constraining",
              render: (v) => (v && v.length ? v.map((c) => <span className="tag" key={c} style={{ marginRight: 4 }}>{c}</span>) : "—"),
            },
          ]}
          rows={data.fg_feasibility}
        />
      </Panel>

      <Panel title="Component Requirements vs Availability">
        <DataTable
          columns={[
            { key: "component", label: "Component" },
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
