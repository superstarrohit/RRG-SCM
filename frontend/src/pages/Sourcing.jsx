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

export default function Sourcing() {
  const { loading, data, error } = useApi(() => api.sourcing({ top_n: 25 }), []);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const header = (
    <div className="page-header">
      <div>
        <h1>Sourcing Analysis</h1>
        <p>Supplier spend, on-time delivery, price benchmarking and single-source risk{data.as_of ? ` · as of ${data.as_of}` : ""}</p>
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
        <KpiCard label="Active Suppliers" value={fmtNum(k.active_suppliers)} />
        <KpiCard label="Committed Value" value={fmtMoney(k.total_committed_value)} />
        <KpiCard label="Single-Source Materials" value={fmtNum(k.single_source_materials)} accent={k.single_source_materials ? "amber" : "green"} />
        <KpiCard label="Avg On-Time %" value={`${fmtNum(k.avg_on_time_pct, 1)}%`} />
      </div>

      <div className="panel-grid">
        <Panel title="Supplier Spend">
          <DataTable
            columns={[
              { key: "supplier_code", label: "Code" },
              { key: "supplier_name", label: "Name" },
              { key: "open_lines", label: "Open Lines", num: true },
              { key: "open_value", label: "Open Value", num: true, render: fmtMoney },
              { key: "received_value", label: "Received", num: true, render: fmtMoney },
            ]}
            rows={data.supplier_spend}
          />
        </Panel>
        <Panel title="On-Time Delivery Performance">
          <DataTable
            columns={[
              { key: "supplier_code", label: "Supplier" },
              { key: "deliveries", label: "Deliveries", num: true },
              { key: "on_time", label: "On Time", num: true },
              { key: "on_time_pct", label: "OTIF %", num: true, render: (v) => `${fmtNum(v, 1)}%` },
            ]}
            rows={data.on_time_performance}
          />
        </Panel>
      </div>

      <div className="panel-grid">
        <Panel title="Price Benchmark (multi-source materials)">
          <DataTable
            columns={[
              { key: "material_code", label: "Material" },
              { key: "suppliers", label: "Suppliers", num: true },
              { key: "min_price", label: "Min", num: true, render: fmtMoney },
              { key: "max_price", label: "Max", num: true, render: fmtMoney },
              { key: "avg_price", label: "Avg", num: true, render: fmtMoney },
              { key: "spread_pct", label: "Spread %", num: true, render: (v) => `${fmtNum(v, 1)}%` },
            ]}
            rows={data.price_benchmark}
          />
        </Panel>
        <Panel title="Single-Source Risk">
          <DataTable
            columns={[
              { key: "material_code", label: "Material" },
              { key: "supplier_code", label: "Sole Supplier" },
              { key: "supplier_name", label: "Name" },
            ]}
            rows={data.single_source_risk}
          />
        </Panel>
      </div>
    </div>
  );
}
