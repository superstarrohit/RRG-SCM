# RRG-SCM on Power Apps — Build Blueprint

This folder is a complete, implementation-ready spec for rebuilding RRG-SCM
(the FastAPI + React supply-chain analytics app in this repo) as a
**Microsoft Power Platform** solution: Dataverse tables, a Canvas app with
one screen per existing page, Power Fx formulas that reproduce the Python
analytics exactly, and Power Automate / Dataflow ingestion that reproduces
the "dump upload" pipeline. No `.msapp`/`.pa.yaml` files or CLI scaffolding
are included here — this is the design document a maker (or Copilot Studio /
`pac` tooling) builds from.

## Why this shape

The existing app is:
- **Backend**: FastAPI + SQLAlchemy ORM (SQLite/Postgres) + pandas analytics
  modules, one per report page, each returning a JSON payload of KPIs +
  chart series + table rows.
- **Frontend**: React (Vite), one page per analytics module, built from a
  small shared component kit (`KpiCard`, `Panel`, `DataTable`/`SortableTable`,
  `Donut`/`VBars`/`LineChart`, a global filter bar).
- **Ingestion**: daily "dump" file uploads (Excel/CSV/JSON) mapped by
  flexible column aliases onto 9 tables, with replace/append/merge modes.

The Power Platform equivalents map 1:1 onto that shape:

| RRG-SCM concept | Power Platform equivalent |
|---|---|
| SQLAlchemy model / table | Dataverse table |
| FastAPI analytics endpoint (`/analytics/*`) | Power Fx formulas + collections computed in-app (or a Power Automate cloud flow / Dataverse calculated column for anything too heavy for the client) |
| React page | Canvas app screen |
| React component (`KpiCard`, `Panel`, `DataTable`) | A reusable **component** in a Component Library |
| Global filter bar (`useFilters`) | A set of screen-level/global variables + a shared filter-bar component |
| Dump upload (Excel/CSV/JSON, alias mapping, replace/append/merge) | Power Automate flow (Excel/CSV connector → parse → alias-map → Dataverse upsert) or a Dataflow, per dump type |
| `localStorage` column-width/filter persistence | Power Apps `SaveData`/`LoadData` (local) or a per-user Dataverse "User Preference" table (roaming) |

## Documents in this folder

| File | Contents |
|---|---|
| [`01-data-model.md`](01-data-model.md) | Every Dataverse table: columns, types, keys, and the exact mapping back to each SQLAlchemy model / uploaded dump column (including the friendly-name aliasing `materials_df()` does today). |
| [`02-screens.md`](02-screens.md) | Screen-by-screen UI spec for all 12 report screens + the Data Workspace, mirroring each React page's layout, controls and data bindings. |
| [`03-formulas.md`](03-formulas.md) | Power Fx translations of every piece of business logic: MRP rollup, stock-status classification, receipts calculation, BOM cost roll-up, FG explosion, forecasting gap/status, ABC classification, on-time %, single-source risk, etc. |
| [`04-data-integration.md`](04-data-integration.md) | The ingestion pipeline: per-dump-type Power Automate flow spec, the full alias/field-mapping table, and replace/append/merge semantics. |
| [`05-build-plan.md`](05-build-plan.md) | A phased build order, environment/ALM setup, delegation & performance notes, and a parity checklist against the current app. |

## Scope notes

- **Sourcing** and **Costing** exist today only as backend analytics modules
  with no React page yet (`/analytics/sourcing`, `/analytics/costing`) — this
  spec still gives them full screens (§`02-screens.md`) since the backend
  contract already exists and a Power Apps build should have parity with the
  API, not just the current UI.
- Five analytics modules (`sourcing`, `vendor_receipts`, `forecasting`,
  `fg_planning`, `costing`) read from tables (`suppliers`, `receipts`,
  `forecast`, `production_plan`, `stock`) that **are not yet real Dataverse
  tables** in this spec — in the current backend they're referenced by
  `load_df(db, "...")` but aren't registered in `_MODEL_BY_NAME` /
  `DUMP_TYPES` yet, so those calls resolve to an empty frame today. §`01-data-model.md`
  defines Dataverse tables for all of them anyway (marked **pending upstream**)
  so the Power Apps build doesn't have to leave those screens broken; wire
  them up first if/when the backend gains real ingestion for them.
