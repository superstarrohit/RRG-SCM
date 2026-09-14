import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard,
  Panel,
  DataTable,
  Loading,
  ErrorState,
  EmptyState,
  useApi,
  fmtMoney,
  fmtNum,
} from "../components/ui.jsx";

export default function Costing() {
  const { loading, data, error } = useApi(() => api.costing({ top_n: 50 }), []);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const header = (
    <div className="page-header">
      <div>
        <h1>Costing</h1>
        <p>Multi-level BOM cost roll-up vs standard cost{data.as_of ? ` · as of ${data.as_of}` : ""}</p>
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
        <KpiCard label="Finished Goods Costed" value={fmtNum(k.finished_goods_costed)} />
        <KpiCard label="Avg Rolled-Up Cost" value={fmtMoney(k.avg_rolled_up_cost)} />
        <KpiCard label="Items with Variance" value={fmtNum(k.items_with_variance)} accent={k.items_with_variance ? "amber" : "green"} />
      </div>

      <Panel title="BOM Cost Roll-Up">
        <DataTable
          columns={[
            { key: "material_code", label: "Material" },
            { key: "description", label: "Description" },
            { key: "components", label: "Components", num: true },
            { key: "rolled_up_cost", label: "Rolled-Up Cost", num: true, render: fmtMoney },
            { key: "standard_cost", label: "Standard Cost", num: true, render: fmtMoney },
            { key: "variance", label: "Variance", num: true, render: fmtMoney },
            { key: "variance_pct", label: "Var %", num: true, render: (v) => (v === null ? "—" : `${fmtNum(v, 1)}%`) },
          ]}
          rows={data.cost_rollup}
        />
      </Panel>
    </div>
  );
}
