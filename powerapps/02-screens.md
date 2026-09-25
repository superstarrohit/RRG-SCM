# Canvas App — Screen-by-Screen Spec

A tablet-layout Canvas app with a left nav rail (matches the current React
app's sidebar) and 12 screens. Every screen except **Data Workspace** shares
one **Global Filter Bar** component (Commodity / Buyer / Material / Supplier
/ Location dropdowns + a free-text search box — see below) bound to five
global variables, plus an **"As of"** label sourced from each screen's own
data.

Shared component library to build first (mirrors `frontend/src/components/ui.jsx`
and `charts.jsx`):

| Component | Mirrors | Inputs |
|---|---|---|
| `cmpKpiCard` | `KpiCard` | Label, Value (text, pre-formatted), Icon, Tone (color), optional Delta text + direction |
| `cmpPanel` | `Panel` | Title, Hint text, slot for child content (Power Apps components can't truly "slot" — use a container region below it in each screen instead of true composition) |
| `cmpDataTable` | `DataTable` | Items (table), ColumnSpec (a nested table of `{key, label, isNumeric}`), per-cell formatting handled by the caller |
| `cmpSortableTable` | `SortableTable` | Same as above + persisted sort/filter/column-width state via `LoadData`/`SaveData` keyed by a `StorageKey` text input |
| `cmpBadge` | `Badge` | Value/status text → background+text color via a lookup table (see `03-formulas.md` §"Badge color lookup") |
| `cmpDonut`, `cmpVBars`, `cmpLineChart` | `Donut`/`VBars`/`LineChart` | A table of `{label, value}` (or `{label, value, color}` for the donut) — build as a Gallery of rectangles positioned by formula (native Power Apps has no built-in donut/bar primitive) or embed a Power BI-style chart control if licensed for it |
| `cmpGlobalFilterBar` | the filter bar in `useFilters` | Writes to 5 global variables (below) on change |

### Global filter variables (set by `cmpGlobalFilterBar`, read by every screen's data formulas)

```
Set(gFilterCommodity, "");   // "" = All
Set(gFilterBuyer, "");
Set(gFilterMaterial, "");
Set(gFilterSupplier, "");
Set(gFilterLocation, "");
Set(gFilterSearch, "");
```

Populate the dropdowns' `Items` from `Distinct(rrg_material, rrg_commodity)`
etc. (Commodity/Buyer/Material) and from `rrg_sobmaster` (Supplier — see
`03-formulas.md` §"Supplier options") and from the union of
`rrg_warehousestock.rrg_plant` + `rrg_inventorysnapshot.rrg_location`
(Location — mirrors `location_options_db()`).

A per-screen "page-specific" filter (the Material Planning **Stock As Of**
date, the Movements **Movement Type** dropdown) stays a **screen-level**
variable, not global — exactly like the React app keeps `stockDate` and
`mvtType` local to their own pages instead of in the shared filter context.

---

## Screen 1 — Dashboard (`scrDashboard`)

Mirrors `pages/Dashboard.jsx`. Executive summary — no page-specific filters,
just the global bar.

**Layout (top → bottom):**
1. Page header: "Overall SCM Dashboard" + "As of {date}" (from the overview
   query's resolved `as_of`, not `Today()` — see `03-formulas.md` §"As-of
   resolution").
2. KPI row (4 cards): Inventory Value (as on today), Incoming Receipts (this
   month) — with a "awaiting movements upload" sub-label when
   `rrg_movement` is empty, Suppliers (distinct `rrg_sobmaster.rrg_vendorcode`
   count), Materials (filtered count).
3. **Inventory Value Trend** — a drilldown bar chart with a Year/Quarter/Month/Day
   tab strip. Clicking a bar (or a tab) re-renders the *whole* chart at the
   next granularity (not a single-branch drill) — implement as a screen
   variable `varGrain` ("yearly" default) that a `Switch()` formula buckets
   `rrg_inventorysnapshot` by (see `03-formulas.md` §"Period bucketing").
   Reset `varGrain` to "yearly" whenever any global filter changes
   (`OnChange` of the filter bar sets it back).
4. **Incoming Receipts Trend** — same drilldown pattern, sourced from
   `rrg_movement` filtered to mvt ∈ {101, 102, 501}, net-summed per bucket.
   Shows a "pending" empty state when `rrg_movement` has 0 rows.
5. **Stock Quantity Trend** / **Receipts Quantity Trend** — same two charts,
   qty instead of value.
6. **Latest Inventory Value by Buyer** — horizontal/vertical bar, one bar per
   buyer, from the latest snapshot date's per-buyer sum.
7. **Incoming Value by Buyer** / **Incoming Value by Supplier** — same
   pattern from this month's net movement value, grouped by buyer / by
   primary (highest-share) SOB Master vendor. Supplier version keeps only
   the top 12 and folds the rest into "Other" (see `03-formulas.md` §"Top-N
   with Other").

---

## Screen 2 — Incoming Materials Analysis (`scrIncoming`)

Mirrors `pages/Incoming.jsx`, the "flagship module." Global filter bar only.

1. Header + subtitle ("Open-PO pipeline, arrivals timeline, delays, supplier
   & ABC breakdown, and stock coverage").
2. KPI row (6): Open PO Lines (+ materials/suppliers sub-label), Open Value
   (+ units sub-label), Overdue (red, + % of value), Arriving ≤7d, Arriving
   ≤30d, Avg Days to Arrival.
3. Two-panel row: **Pipeline by Status** donut (Overdue/red, Due this
   week/amber, Due this month/blue, Future/green, No ETA/grey) with a
   status-bar list underneath; **Expected Arrivals Timeline** line chart,
   value per week, 8-week horizon (first bucket sweeps up overdue, last
   sweeps up everything beyond the horizon).
4. **⚠ Overdue PO Lines** table: PO/Line, Material, Description, Supplier,
   Open Qty, Value, ETA, Days Late (red badge). Sorted by days-overdue desc
   then value desc, top 15.
5. Two-panel row: **Incoming by Supplier** bar chart (top 15 by value);
   **Incoming by Category** table (Lines, Qty, Value).
6. Two-panel row: **ABC of Incoming Value** table (Class badge, Materials,
   Value, % Value); **Incoming vs Current Stock** coverage table (On Hand,
   Incoming, Total Avail, Inc/Stock % — shows "no stock" when on-hand is 0).

Data source: `rrg_purchaseorder` collapsed to latest-per-(po,item) at-or-before
today (§`03-formulas.md` §"Latest Open POs"), joined to `rrg_material` and
`rrg_supplier`. Location filter is accepted on this screen for slicer
consistency but doesn't narrow anything (open POs have no location column).

---

## Screen 3 — Material Planning / MRP (`scrPlanning`)

Mirrors `pages/Planning.jsx` — the screen with the most bespoke behavior in
the app: a page-specific **Stock As Of** date picker that re-derives the
*entire* report (not just a stock column), a Vendor column, negative-red
formatting, and a persisted, user-resizable table.

1. Header: "Material Planning (MRP)" + subtitle + **Stock As Of** date
   picker (native Power Apps `DatePicker` control) in the header-right slot,
   with a small "×" to clear back to latest. Persist the picked date in
   `LoadData`/`SaveData` under key `"material-planning-stock-date"` so it
   survives app restarts, mirroring the React page's own `localStorage`
   persistence (`STOCK_DATE_KEY`).
2. `cmpSortableTable` (`StorageKey: "material-planning"`) with columns, in
   order: Material (mono/strong), Material Description, **Vendor** (all SOB
   vendors for that material, comma-joined, highest-share first — see
   `03-formulas.md` §"Vendors by material"), Demand (M1), Safety Stock,
   Current Stock, Warehouse Stock, **Receipts**, Reach (Days), Material
   Status (badge), Open PO, then M1 Forecast/Bal, M2 Demand/Forecast/Bal, M3
   Demand/Forecast/Bal, M4 Demand/Forecast/Bal.
   - Every numeric column except the 4 Forecast columns renders **red when
     negative**.
   - The 4 Forecast columns render **red when positive** (a positive
     Forecast means "you must procure this," which is the thing worth
     flagging — never negative by construction, since it's clipped at 0).
   - Material Status filter is a dropdown restricted to Stockout/Risk/Alarm/Safe/Excess.
   - Rows sorted by status severity (Stockout→Risk→Alarm→Safe→Excess) then
     material code, matching the backend's default order.
3. All of Current Stock / Warehouse Stock / Receipts / Open PO / Status /
   Reach Days / the whole M1-M4 rollup are **recomputed against the picked
   Stock As Of date**, not just re-filtered — see `03-formulas.md`
   §"Material Planning rollup" for the exact per-row formula, which must run
   for every row whenever the date changes.
4. Column widths: on first manual column-border drag, snapshot all current
   widths and switch the table from auto-sizing to fixed widths with text
   wrapping enabled (mirrors the React `SortableTable`'s progressive
   enhancement) — persist widths the same way as sort/filters, keyed by
   `StorageKey`. A "Reset column widths" button appears only once custom
   widths are active.

---

## Screen 4 — Finished-Goods Planning (`scrFGPlanning`)

Mirrors `pages/FGPlanning.jsx`.

1. Header + subtitle ("Production plan exploded through the BOM, checked
   against component availability").
2. KPI row (4): FG Planned, FG At Risk (red if >0), Components Required,
   Components Short (red if >0).
3. **Top Component Requirements** bar chart — top 8 components by gross
   requirement across the (filtered) plan.
4. **FG Feasibility** table: Finished Good, Description, Planned Qty,
   Components (count), Status (badge: "short"/"ok"), Constraining
   (tag-list of the specific short components blocking that FG, max 10,
   "—" if none).
5. **Component Requirements vs Availability** table: Component, Description,
   Required, On Hand, Incoming, Available, Shortage, Status badge.

Data: needs `rrg_productionplan` and `rrg_bomline` (empty-state message
"Load a production plan and BOM to run finished-goods planning" until both
exist). BOM explosion formula in `03-formulas.md` §"BOM explosion".

---

## Screen 5 — Stock Monitoring (`scrStockMonitoring`)

Mirrors `pages/StockMonitoring.jsx`.

1. Header + subtitle ("Stock health & stockout risk...").
2. KPI row (7): Materials, Stockouts (red if >0), Critical <safety (red),
   Low <refill (amber), Overstock >max (purple), At Risk (red), Stock Value.
3. Two-panel row: **Stock Health Distribution** donut (5 status colors);
   **Risk Summary** — horizontal bar-per-status list showing count and % of
   total materials.
4. **⚠ Stockout Risk — Action List** table (materials where
   `status ∈ {stockout, critical, low}` OR projected balance < 0), sorted by
   status then stock value desc: Material, Description, Commodity, Buyer,
   Stock, Safety, Refill, Incoming, Demand, Cover (Days), Status badge.

Status classification and cover-days formula: `03-formulas.md` §"Stock
health classification". Location filter genuinely re-sources on-hand qty
from that plant's `rrg_warehousestock` rows here.

---

## Screen 6 — Inventory Monitoring (`scrInventoryMonitoring`)

Mirrors `pages/InventoryMonitoring.jsx`.

1. Header + subtitle.
2. KPI row (6): Inventory Value (+ MoM % delta, colored by direction),
   Inventory Qty, Materials, Locations, Commodities, Latest Snapshot date.
3. **Inventory Trend** line chart with a Value/Quantity toggle (segmented
   control), sourced from `rrg_inventorysnapshot` grouped by
   `rrg_snapshotdate`.
4. Two-panel row: **by Commodity** / **by Location** bar charts (top 12 by
   value, latest snapshot only).
5. **by Buyer** bar chart (same, full width).

---

## Screen 7 — Vendor Receipts (`scrVendorReceipts`)

Mirrors `pages/VendorReceipts.jsx`. Needs `rrg_receipt` (pending-upstream,
§`01-data-model.md` §10) — empty-state "Load the Goods Receipts (GRN) dump..."
until it exists.

1. Header + subtitle.
2. KPI row (5): Received Value, Received Qty, Receipts (count), Suppliers,
   Materials.
3. **Receipts Trend** line chart, Value/Quantity toggle, grouped by month.
4. Two-panel row: **Received Value by Supplier** bar chart (top 12); **Received
   Value by Commodity** table (Qty, Value).
5. **Supplier Receipt Summary** table: Code, Supplier, Receipts, Qty, Value.

---

## Screen 8 — Material Movements (`scrMovements`)

Mirrors `pages/Movements.jsx`. Has its own page-specific slicer.

1. Header + subtitle.
2. **Mvt Master** filter row (page-local, not global): a "Movement Type"
   dropdown sourced from `Distinct(rrg_movement, rrg_mvttype)` + a "Clear"
   button. Keep this as screen variable `varMvtType`, not a global filter.
3. KPI row (5): Movements (count), Inflow Qty (green), Outflow Qty (red),
   Net Qty (green/red by sign), Movement Types (distinct count).
4. Two-panel row: **Movement Value by Type** bar chart (`abs(value)` per
   type); **Movement Type Summary** table (Type badge, Count, Net Qty,
   Value).
5. **Recent Movements** table: Date, Material, Description, Type badge, Qty
   (green if ≥0 / red if <0), Value. Top 20, most recent first.

Inflow/outflow classification: mvt 101 = inflow; mvt ∈
{102,201,501,551,601} = outflow; 301/311 (transfers) count toward neither.

---

## Screen 9 — Forecasting (`scrForecasting`)

Mirrors `pages/Forecasting.jsx`. Needs `rrg_forecastline`
(pending-upstream) — empty-state "Load the Forecast (M1/M2/M3) dump..."
until it exists. Note this is a **separate** forecast source from
`rrg_material`'s own `demand`/`demand_2..4` used on the Planning screen —
don't conflate the two.

1. Header + subtitle ("Rolling three-month forecast vs current supply...").
2. KPI row (6): Materials Forecast, M1/M2/M3 Forecast qty, 3-Month Value,
   Short Items (red if >0).
3. Two-panel row: **Forecast by Month** bar chart (M1/M2/M3 totals);
   **3-Month Forecast by Commodity** bar chart.
4. **Forecast vs Supply — Coverage Gaps** table: Material, Description,
   Commodity, Buyer, Stock, Incoming, M1, M2, M3, Total 3M, Gap (red if >0),
   Status badge (short/excess/ok). Sorted by gap desc, top 30.

Gap/status formula: `03-formulas.md` §"Forecast gap & status".

---

## Screen 10 — Sourcing (`scrSourcing`) — *new screen, API-ready*

No React page exists yet for `/analytics/sourcing`, but the backend contract
is fully built — give this parity. Needs `rrg_supplier` and `rrg_receipt`
(pending-upstream).

1. Header: "Sourcing" / subtitle: "Supplier spend, on-time delivery
   performance, price benchmarking, and single-source risk."
2. KPI row (4): Active Suppliers, Total Committed Value, Single-Source
   Materials, Avg On-Time %.
3. **Supplier Spend** table (top 20 by open value): Code, Name, Open Lines,
   Open Value, Received Value.
4. **On-Time Delivery Performance** table: Supplier, Deliveries, On Time
   (count), On-Time % — computed by matching each GRN's receipt date against
   its PO's expected date via PO number (`03-formulas.md` §"On-time
   delivery").
5. **Price Benchmark** table (materials sourced from >1 supplier, sorted by
   spread % desc): Material, Suppliers (count), Min/Max/Avg Price, Spread %.
6. **⚠ Single-Source Risk** list: every material sourced from exactly one
   supplier across POs+receipts — Material, Supplier Code, Supplier Name.

---

## Screen 11 — Costing (`scrCosting`) — *new screen, API-ready*

No React page exists yet for `/analytics/costing`; give this parity too.

1. Header: "Costing" / subtitle: "BOM cost roll-up vs standard cost, and
   variance."
2. KPI row (3): Finished Goods Costed, Avg Rolled-Up Cost, Items with
   Variance.
3. **Cost Roll-Up** table (top 25 by rolled-up cost desc): Finished Good,
   Description, Components (count), Rolled-Up Cost (sum of each component's
   standard cost × qty, recursive through sub-assemblies), Standard Cost
   (the FG's own `rrg_map`), Variance (standard − rolled-up), Variance % (—
   when rolled-up cost is 0).

Roll-up formula: `03-formulas.md` §"BOM cost roll-up" (same recursive
pattern as FG Planning's explosion, opposite direction: cost flows up from
leaves to root instead of quantity flowing down from root to leaves).

---

## Screen 12 — Data Workspace (`scrDataWorkspace`)

Mirrors `pages/DataWorkspace.jsx`. **No global filter bar** — this screen
manages the data itself. Four tabs (a `Gallery`/button strip driving a
screen variable `varWsTab`):

### Tab: Datasets (browse/edit/delete)
- Left rail: one button per Dataverse table (icon + label + row count),
  selecting sets `varSelectedTable`.
- Right panel: a searchable, sortable, paged grid (25/page) over the
  selected table with row checkboxes, a toolbar (Append → jumps to Import
  tab; Merge → same; Export as Excel/CSV/JSON via `Export()`/a flow; Delete
  Selected; Clear All with a confirm dialog), and inline row editing (tap a
  row's Edit icon → editable cells in place → Save/Cancel). Every
  destructive action (`Delete Selected`, `Clear All`) needs a confirm
  `Notify`/dialog, matching the React `confirm(...)` calls.

### Tab: Link Tables (ad-hoc join)
- Left/Right table pickers + Left/Right key-column pickers (auto-guess the
  key column by name match on `material|code|supplier|po_number|id`, same
  heuristic as `guessKey()`) + Join Type (Inner/Left/Right/Outer) + Run
  button.
- Result: a preview table (first 50 rows) built with `Table()`/`AddColumns()`
  joins in Power Fx, or delegate to a Power Automate flow for large tables
  (a client-side `LookUp` join doesn't delegate well past a few thousand
  rows on either side — see `05-build-plan.md` §"Delegation limits").

### Tab: Import (file + database/connector)
- **File** sub-mode: Target dataset picker (from the 9 dump types + the
  5 pending-upstream ones), Load Mode (Replace/Append/Merge — Merge needs a
  comma-separated key-column list), a native `Attachment`/file-upload
  control (.xlsx/.xls/.csv/.tsv/.json), Preview (shows detected
  columns→target mapping + any missing required fields) and Import buttons.
  This is the single most valuable flow to get right — see
  `04-data-integration.md` for the full per-dump-type Power Automate spec.
- **Database & Connector** sub-mode: a connector-type chip row (SQL Server,
  MySQL, PostgreSQL, MS Access, ODBC, SAP HANA, SAP ODBC, KNIME), then
  host/port/database/username/password (or DSN, or file path for Access)
  fields, table name or a raw SQL query override, Test/Preview/Pull&Load
  buttons. In Power Platform this is exactly what the native **SQL Server**,
  premium **ODBC**, and (with the SAP HANA / OData premium connectors) data
  source connections already do — a Power Automate flow (or a Dataflow for
  bulk/scheduled loads) per configured connection, writing into the target
  Dataverse table with the same Replace/Append/Merge semantics.

### Tab: Data Quality
- Dataset picker + a per-column profile table: Non-null, Nulls, Null % (red
  badge >20%, amber >0%, green =0%), Distinct, Min, Max, Mean. Compute via a
  Power Automate flow (or a Dataflow profiling step) rather than in-app
  Power Fx — full-table statistics don't delegate.

---

## Cross-screen conventions

- **"As of" resolution**: never `Today()`. Each screen resolves its own
  as-of the same way its Python module does (e.g. Dashboard uses the latest
  `rrg_inventorysnapshot` date at/before the active date-range end; Material
  Planning uses the latest snapshot at/before the picked Stock As Of date).
  See `03-formulas.md` §"As-of resolution" for the shared pattern.
- **Empty states**: every screen carries the exact `_empty()` message text
  from its Python module (e.g. "Load the material master (with
  safety/refill/max levels and demand) to run planning.") so the guidance a
  user sees is identical whether they're on the web app or Power Apps.
- **Badges**: a single shared color/label lookup table drives every status
  badge across every screen (see `03-formulas.md` §"Badge color lookup") —
  don't hardcode colors per screen.
