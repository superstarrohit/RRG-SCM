# Build Plan

## Phase 0 — Environment & ALM setup

1. Provision a Dataverse environment (Dev), plus Test/Prod if this is going
   beyond a pilot. Set the solution publisher prefix (`rrg_` throughout this
   spec — change consistently if a different prefix is preferred).
2. Create one **unmanaged solution** (`RRGSupplyChain`) containing every
   table, flow, and the Canvas app — never build directly in the default
   solution.
3. Set up source control for the solution (Power Platform's solution
   export/`pac solution` tooling, or the Power Platform Pipelines ALM
   accelerator) so the Canvas app + flows can be versioned alongside this
   repo, mirroring how the existing FastAPI/React code is versioned here.
4. Decide Dev/Test/Prod promotion via **Power Platform Pipelines** (or
   manual solution export/import) before building screens — retrofitting
   ALM after the fact is far more painful than starting with it.

## Phase 1 — Data model

1. Create all 9 confirmed tables from `01-data-model.md` §1–9, with their
   Alternate Keys (§`04-data-integration.md`'s Merge-key column per table)
   and the two Lookup relationships that matter most for delegation:
   `rrg_purchaseorder.rrg_materialcode` → `rrg_material`,
   `rrg_movement.rrg_materialcode` → `rrg_material`,
   `rrg_warehousestock.rrg_materialcode` → `rrg_material`,
   `rrg_inventorysnapshot.rrg_materialcode` → `rrg_material`,
   `rrg_sobmaster.rrg_material` → `rrg_material`,
   `rrg_bomline.rrg_fgmaterial` / `rrg_rmmaterial` → `rrg_material`.
2. Create the recommended composite indexes called out in
   `01-data-model.md` (`rrg_purchaseorder` on po+item+snapshot date,
   `rrg_warehousestock` on plant+storage_location+material+date,
   `rrg_movement` on material+date).
3. Create the 5 pending-upstream tables from `01-data-model.md` §10 (even if
   left empty at first) so screen-building in Phase 3 isn't blocked waiting
   on the real backend to add them.
4. Create the staging tables the recursive/server-side formulas write into:
   `rrg_latestopenpo`, `rrg_latestwarehousestock`, `rrg_costrollup`,
   `rrg_componentrequirement`, `rrg_fgfeasibility`, `rrg_statuscolor`
   (seed this one immediately with the badge table from `03-formulas.md`).

## Phase 2 — Ingestion

1. Build `flowApplyDumpTypeMapping` (the shared child flow) first, since
   every dump-specific flow calls it.
2. Build the 9 confirmed per-dump-type flows from `04-data-integration.md`,
   file-upload triggered from the Canvas app's Import screen.
3. Build `flowLatestOpenPoRollup` and `flowLatestWarehouseStockRollup`
   (refresh the two "latest" staging tables) and wire them to run after
   their respective import flow completes.
4. Load a realistic volume of test data through this pipeline **before**
   building any screen — every downstream formula in `03-formulas.md` was
   designed against the shapes this ingestion produces, and it's much
   cheaper to find an aliasing/type-coercion bug here than after 12 screens
   are built against wrong data.

## Phase 3 — Component library

Build the shared components from `02-screens.md`'s table
(`cmpKpiCard`, `cmpPanel`, `cmpDataTable`, `cmpSortableTable`, `cmpBadge`,
`cmpDonut`, `cmpVBars`, `cmpLineChart`, `cmpGlobalFilterBar`) in a dedicated
**Component Library** app, published and added as a dependency to the main
Canvas app. Building these once, well, is what makes 12 screens tractable —
resist building any KPI card or table inline on a screen once the component
exists.

## Phase 4 — Screens, in dependency order

Build in this order so each screen's data is already trustworthy by the
time it's built (screens with pending-upstream tables come last, since
they'll show empty states until those tables have real ingestion):

1. Dashboard (validates the global filter bar + drilldown chart pattern
   everything else reuses)
2. Incoming Materials
3. Stock Monitoring
4. Inventory Monitoring
5. Movements
6. Material Planning (the most complex screen — build last among the
   "confirmed data" screens, once the team is comfortable with the
   component library and the As-Of resolution pattern)
7. FG Planning (needs the BOM roll-up flow from Phase 5 first — build the
   flow, then the screen)
8. Costing (same dependency)
9. Vendor Receipts, Forecasting, Sourcing (pending-upstream tables — build
   the screen now, wire real data in once ingestion exists)
10. Data Workspace (last — it's the least like the others and depends on
    every dump-type flow already existing)

## Phase 5 — Server-side computation (flows)

Build alongside Phase 4, gated by that phase's dependencies:
- `flowBomRollup` (§`03-formulas.md` §"BOM cost roll-up & BOM explosion") —
  before FG Planning and Costing screens.
- `flowIncomingAbcClassification` (§"ABC classification") — before the
  Incoming screen's ABC panel, or accept a simplified client-side version
  capped to whatever row count is actually being classified (Incoming's ABC
  table groups by material first, which is usually a much smaller set than
  raw PO lines — check whether that grouped size is small enough for a
  client-side running-sum before building the flow).
- `flowSourcingAggregates` (on-time %, price benchmark, single-source risk,
  supplier spend) — before the Sourcing screen, once `rrg_receipt` exists.

## Delegation & performance notes

- **Delegable data sources**: Dataverse delegates most standard operators
  (`=`, `<`, `>`, `And`, `Or`, `StartsWith`, `in` on choice columns) but
  **not** `GroupBy` with a running total, nested `LookUp`s inside
  `AddColumns` at scale, or anything requiring more than one pass over a
  table larger than the delegation limit (default 2000 rows, configurable up
  to Dataverse's actual cap). Every formula in `03-formulas.md` marked
  **⚠ server-side** exists because of this — don't try to "just increase the
  row limit" as a substitute for the staging-table pattern; it degrades
  silently (truncated results, not an error) well before it becomes visibly
  slow.
- **`rrg_purchaseorder`** and **`rrg_warehousestock`** are the two tables
  that will actually hit hundreds of thousands of rows in production
  (mirrors the Python backend's own comment that materializing these
  wholesale into pandas took "15s+ per call" before it was rewritten to a
  SQL-side `ROW_NUMBER()`). Never bind a screen directly to either table —
  always go through their "latest" staging table.
- **Material Planning's per-row `ForAll`** recompute (on every Stock-As-Of
  date change) is proportional to material count, not snapshot-day count —
  fine into the low thousands of materials; if the material master grows
  past that, consider moving the M1-M4 rollup into the same staging-table
  flow pattern as costing, keyed by (material, stock_date).
- **Column-width/filter persistence**: `SaveData`/`LoadData` is local to the
  device (mirrors the current app's `localStorage`, which is also
  per-browser) — if "the setting a user's layout" should roam across
  devices, use a small per-user Dataverse table (`rrg_userlayoutpref`:
  `user` lookup, `screenkey`, `layoutjson`) instead, which is a *behavior
  change* from the current app, not strict parity — confirm with the
  business which is wanted before building it.

## Parity checklist

Use this to confirm the Power Apps build matches the current web app before
calling any screen "done":

- [ ] Every screen's KPI values match the FastAPI JSON response for the same
      filters, to the same rounding (`safe_round`, 2 decimals unless noted).
- [ ] Every "As of" label shows the same resolved date as the Python
      `as_of` field — never `Today()`.
- [ ] Every empty-state message matches the Python `_empty()` message text
      verbatim.
- [ ] Status badge colors match `03-formulas.md`'s lookup table exactly
      (a badge's color must never come from cycling through a generic
      palette).
- [ ] Material Planning: numeric columns are red-if-negative *except* the
      four Forecast columns, which are red-if-positive; the Vendor column
      lists every SOB vendor by descending share, not just the top one.
- [ ] Material Planning: changing Stock As Of recomputes stock, receipts,
      status, reach days, open PO and the entire M1-M4 rollup — not just the
      stock number.
- [ ] Movements: mvt 301/311 (transfers) count toward neither inflow nor
      outflow, but still appear in the type summary and recent-movements
      table.
- [ ] Dashboard/Incoming/Vendor Receipts drilldown charts re-render the
      *whole* chart at the next granularity on tap — never narrow to a
      single selected branch.
- [ ] Supplier/Location filters that don't apply to a given screen (e.g.
      Location on Incoming, Sourcing, Costing, FG Planning's plan itself)
      are still present in the filter bar for consistency but confirmed to
      be no-ops there, matching the Python comments explaining why.
