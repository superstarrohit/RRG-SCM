import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable,
  Loading, ErrorState, EmptyState, useApi, fmtMoney, fmtNum,
} from "../components/ui.jsx";
import { LineChart, VBars, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

export default function VendorReceipts() {
  const f = useFilters();
  const [metric, setMetric] = React.useState("value");
  const { loading, data, error } = useApi(() => api.vendorReceipts(f.params), [f.key]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Vendor Receipts"
      subtitle="Inbound goods-receipt (GRN) trends by supplier and commodity over time."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  const k = data.kpis;
  const isVal = metric === "value";
  const line = data.timeline.map((t) => ({ label: t.label, value: isVal ? t.value : t.qty }));
  const supBars = data.by_supplier.map((s) => ({ label: (s.supplier_name || s.supplier_code || "").split(" ")[0], value: s.value }));

  return (
    <div>
      {head}
      <div className="kpi-grid">
        <KpiCard label="Received Value" value={fmtMoney(k.total_value)} icon="receipt" tone="green" />
        <KpiCard label="Received Qty" value={fmtNum(k.total_qty)} icon="box" tone="blue" />
        <KpiCard label="Receipts" value={fmtNum(k.receipts)} icon="clipboard" tone="purple" />
        <KpiCard label="Suppliers" value={fmtNum(k.suppliers)} icon="handshake" tone="amber" />
        <KpiCard label="Materials" value={fmtNum(k.materials)} icon="cube" tone="cyan" />
      </div>

      <Panel title="Receipts Trend">
        <div className="controls" style={{ justifyContent: "flex-end", marginBottom: 10 }}>
          <div className="seg" style={{ marginBottom: 0 }}>
            <button className={isVal ? "on" : ""} onClick={() => setMetric("value")}>Value</button>
            <button className={!isVal ? "on" : ""} onClick={() => setMetric("qty")}>Quantity</button>
          </div>
        </div>
        <LineChart data={line} valueFormat={isVal ? (v) => "$" + fmtNum(v / 1000) + "k" : (v) => fmtNum(v)} color={PALETTE.cyan} />
      </Panel>

      <div className="panel-grid">
        <Panel title="Received Value by Supplier">
          <VBars data={supBars} valueFormat={(v) => "$" + fmtNum(v / 1000) + "k"} color={PALETTE.purple} />
        </Panel>
        <Panel title="Received Value by Commodity">
          <DataTable
            columns={[
              { key: "name", label: "Commodity" },
              { key: "qty", label: "Qty", num: true, render: (v) => fmtNum(v) },
              { key: "value", label: "Value", num: true, render: fmtMoney },
            ]}
            rows={data.by_commodity}
          />
        </Panel>
      </div>

      <Panel title="Supplier Receipt Summary">
        <DataTable
          columns={[
            { key: "supplier_code", label: "Code", render: (v) => <span className="mono">{v}</span> },
            { key: "supplier_name", label: "Supplier" },
            { key: "receipts", label: "Receipts", num: true },
            { key: "qty", label: "Qty", num: true, render: (v) => fmtNum(v) },
            { key: "value", label: "Value", num: true, render: fmtMoney },
          ]}
          rows={data.by_supplier}
        />
      </Panel>
    </div>
  );
}
