import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable,
  Loading, ErrorState, EmptyState, useApi, fmtMoney, fmtNum, fmtPct,
} from "../components/ui.jsx";
import { VBars, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

export default function Costing() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.costing({ top_n: 50, ...f.params }), [f.key]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Costing"
      subtitle="Multi-level BOM cost roll-up compared against standard cost."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  const k = data.kpis;
  const costBars = data.cost_rollup.slice(0, 8).map((r) => ({
    label: r.material_code, value: r.rolled_up_cost,
  }));

  return (
    <div>
      {head}
      <div className="kpi-grid">
        <KpiCard label="Finished Goods Costed" value={fmtNum(k.finished_goods_costed)} icon="factory" tone="blue" />
        <KpiCard label="Avg Rolled-Up Cost" value={fmtMoney(k.avg_rolled_up_cost)} icon="dollar" tone="green" />
        <KpiCard label="Items with Variance" value={fmtNum(k.items_with_variance)} icon="alert" tone="amber" />
      </div>

      <Panel title="Rolled-Up Cost by Finished Good">
        <VBars data={costBars} valueFormat={(v) => "₹" + fmtNum(v)} color={PALETTE.blue} />
      </Panel>

      <Panel title="BOM Cost Roll-Up">
        <DataTable
          columns={[
            { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
            { key: "description", label: "Description" },
            { key: "components", label: "Components", num: true },
            { key: "rolled_up_cost", label: "Rolled-Up Cost", num: true, render: fmtMoney },
            { key: "standard_cost", label: "Standard Cost", num: true, render: fmtMoney },
            { key: "variance", label: "Variance", num: true, render: (v) => <span style={{ color: v < 0 ? "var(--red)" : "var(--green)" }}>{fmtMoney(v)}</span> },
            { key: "variance_pct", label: "Var %", num: true, render: (v) => v == null ? "—" : fmtPct(v) },
          ]}
          rows={data.cost_rollup}
        />
      </Panel>
    </div>
  );
}
