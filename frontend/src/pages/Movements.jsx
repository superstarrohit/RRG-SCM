import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtMoney, fmtNum,
} from "../components/ui.jsx";
import { VBars, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";
import Icon from "../components/icons.jsx";

const MVT_BADGE = { GRN: "ok", Issue: "short", Transfer: "due_this_month", Adjustment: "excess" };

export default function Movements() {
  const f = useFilters();
  // Movement Type is a page-specific slicer (matches the reference report's
  // "Mvt Master" slicer, which only appears on this page) — kept local
  // rather than in the shared filter context.
  const [mvtType, setMvtType] = React.useState("");
  const params = React.useMemo(
    () => (mvtType ? { ...f.params, mvt_type: mvtType } : f.params),
    [f.params, mvtType]
  );
  const { loading, data, error } = useApi(() => api.movements(params), [f.key, mvtType]);
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

  const mvtTypeOptions = data.filters?.mvt_type || [];
  const k = data.kpis;
  const typeBars = data.by_type.map((t) => ({ label: t.mvt_type, value: Math.abs(t.value) }));

  return (
    <div>
      {head}
      <div className="fb-row" style={{ marginBottom: 14 }}>
        <span className="fb-label"><Icon name="flow" size={14} /> Mvt Master</span>
        <div className="fb-field">
          <span className="fb-field-label">Movement Type</span>
          <select value={mvtType} onChange={(e) => setMvtType(e.target.value)}>
            <option value="">All movement types</option>
            {mvtTypeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        {mvtType && (
          <button className="btn ghost" onClick={() => setMvtType("")} style={{ padding: "7px 12px", fontSize: 12.5 }}>
            <Icon name="x" size={14} /> Clear
          </button>
        )}
      </div>
      <div className="kpi-grid">
        <KpiCard label="Movements" value={fmtNum(k.movements)} icon="flow" tone="blue" />
        <KpiCard label="Inflow Qty" value={fmtNum(k.inflow_qty)} icon="download" tone="green" />
        <KpiCard label="Outflow Qty" value={fmtNum(k.outflow_qty)} icon="upload" tone="red" />
        <KpiCard label="Net Qty" value={fmtNum(k.net_qty)} icon="merge" tone={k.net_qty >= 0 ? "green" : "red"} />
        <KpiCard label="Movement Types" value={fmtNum(k.movement_types)} icon="layers" tone="purple" />
      </div>

      <div className="panel-grid">
        <Panel title="Movement Value by Type">
          <VBars data={typeBars} valueFormat={(v) => "₹" + fmtNum(v)} color={PALETTE.purple} />
        </Panel>
        <Panel title="Movement Type Summary">
          <DataTable
            columns={[
              { key: "mvt_type", label: "Type", render: (v) => <Badge value={MVT_BADGE[v]} label={v} /> },
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
            { key: "mvt_type", label: "Type", render: (v) => <Badge value={MVT_BADGE[v]} label={v} /> },
            { key: "qty", label: "Qty", num: true, render: (v) => <span style={{ color: v < 0 ? "var(--red)" : "var(--green)" }}>{fmtNum(v)}</span> },
            { key: "value", label: "Value", num: true, render: fmtMoney },
          ]}
          rows={data.recent}
        />
      </Panel>
    </div>
  );
}
