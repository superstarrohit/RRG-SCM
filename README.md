# RRG-SCM — Supply Chain Analytics Platform

A Python + React application for **SCM analytics, material planning, sourcing,
costing and finished-goods planning**. Users upload their daily dumps — stocks,
open POs, receipts, warehouse stock, BOMs, demand — from **Excel, CSV, JSON,
SQL Server, MySQL / MySQL Workbench, PostgreSQL, MS Access, generic ODBC, SAP
HANA (live) / SAP ERP-BW, or KNIME (via its ODBC/JDBC bridge)**, and the app
does the analysis. Values are shown in **₹ (INR)**, matching an India-based
operation.

> **Status:** Foundation + the **Incoming Materials Analysis** module built
> end-to-end. Material Planning (MRP), Sourcing, Costing, FG Planning and the
> Overall SCM dashboard are implemented and wired through the API and UI, ready
> to extend.

---

## Architecture

```
RRG-SCM/
├── backend/                 FastAPI + SQLAlchemy + pandas
│   ├── app/
│   │   ├── connectors/      Data-source connectors (file + databases)
│   │   ├── ingestion/       Dump-type schemas, column mapping, loader
│   │   ├── models/          ORM data model (staging store)
│   │   ├── analytics/       Analysis modules (incoming, MRP, sourcing, …)
│   │   ├── api/             REST endpoints
│   │   ├── config.py        Settings (.env)
│   │   ├── database.py      App database (SQLite by default)
│   │   └── main.py          FastAPI app
│   ├── sample_data/         Generated sample dumps (CSV)
│   ├── scripts/seed.py      Generate + load sample data
│   └── tests/               pytest suite
└── frontend/                React (Vite) SPA
    └── src/
        ├── api/             Fetch client
        ├── components/      Layout + shared UI (cards, tables, charts)
        └── pages/           Dashboard, Incoming, Planning, Sourcing, …
```

**Data flow:** external source → *connector* → pandas DataFrame → *mapper*
(flexible column matching + type coercion + validation) → *loader* → app
database (staging) → *analytics module* → JSON API → React UI.

The app's own store defaults to a local **SQLite** file; point `APP_DATABASE_URL`
at PostgreSQL for a shared deployment. External databases are treated as *sources*
to pull from, not as the app store.

---

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Generate + load sample data (optional but recommended for a first look)
python -m scripts.seed

# Run the API (http://localhost:8000, docs at /docs)
uvicorn app.main:app --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

The Vite dev server proxies `/api` to the backend on `:8000`, so just open
<http://localhost:5173>.

---

## Data ingestion

Everything is driven by **dump types** (see `backend/app/ingestion/dump_types.py`):

| Dump type          | What it is                              | Required columns              |
|--------------------|-----------------------------------------|-------------------------------|
| `materials`        | Item master + planning parameters       | `material_code`               |
| `suppliers`        | Vendor master                           | `supplier_code`               |
| `stock`            | On-hand stock snapshot                   | `material_code`, `qty_on_hand`|
| `warehouse_stock`  | Stock by warehouse/location             | `warehouse_code`, `material_code`, `qty` |
| `open_pos`         | Open purchase-order lines (incoming)    | `po_number`, `material_code`  |
| `receipts`         | Goods receipts (GRN)                     | `material_code`, `qty`        |
| `demand`           | Forecast / requirements                  | `material_code`, `qty`        |
| `inventory_snapshots` | Dated stock history (qty + value)     | `material_code`, `snapshot_date` |
| `movements`        | Goods movements (GRN/issue/transfer)     | `material_code`, `qty`        |
| `forecast`         | Rolling monthly forecast (M1/M2/M3)      | `material_code`               |
| `bom`              | Bill of materials                        | `parent_material`, `component_material` |
| `production_plan`  | Planned FG production                     | `material_code`, `planned_qty`|

The `materials` master also carries **commodity**, **buyer**, **refill_level**
and **max_level** — the sourcing/planning dimensions used across the reports
(modelled on a real Power BI SCM report: Incoming, SCM Planning, Inventory
Monitoring, Vendor Receipts, Movements, FG Planning and Stock Monitoring).

**Flexible column mapping:** headers are matched case-insensitively with common
aliases and separators normalised, so `PO No`, `Material`, `Vendor`, `ETA` map to
`po_number`, `material_code`, `supplier_code`, `expected_date` automatically. Use
the **Preview** action in the UI to see the mapping before loading, or pass
`column_overrides` to the API.

### Ingestion API

| Endpoint                     | Purpose                                    |
|------------------------------|--------------------------------------------|
| `POST /api/ingest/file/preview` | Preview a file's column mapping          |
| `POST /api/ingest/file`         | Upload an Excel/CSV/JSON file and load it (replace/append/merge) |
| `POST /api/ingest/db/test`      | Test a database connection               |
| `POST /api/ingest/db/preview`   | Preview a query/table from a database    |
| `POST /api/ingest/db`           | Pull from a database and load it         |
| `GET  /api/ingest/log`          | Recent ingestion history                 |

### Data Workspace API

A full data-management surface over the staged datasets (the **Data** tab):

| Endpoint                              | Purpose                                     |
|---------------------------------------|---------------------------------------------|
| `GET  /api/data/datasets`             | List datasets with row counts + columns     |
| `GET  /api/data/{ds}/rows`            | Paginated, searchable, sortable rows        |
| `POST /api/data/{ds}/update-row`      | Inline-edit a row's editable fields         |
| `POST /api/data/{ds}/delete-rows`     | Delete selected rows by id                  |
| `DELETE /api/data/{ds}`               | Clear all rows in a dataset                 |
| `POST /api/data/join`                 | Column→column link (join) two datasets      |
| `GET  /api/data/{ds}/profile`         | Data-quality / modeling report              |
| `GET  /api/data/{ds}/export`          | Export as `csv` \| `json` \| `xlsx`         |

Load modes on import: **replace** (overwrite), **append** (add), **merge**
(upsert on key columns). Merge and delete let you reconcile daily dumps in place.

### Connectors & drivers (optional)

Import from files (**Excel, CSV, TSV, JSON**) or live databases. DB drivers are
imported lazily — the app runs without them and only errors if you use that
source. Install what you need:

```bash
pip install psycopg2-binary   # PostgreSQL
pip install PyMySQL           # MySQL / MySQL Workbench
pip install pyodbc            # SQL Server, MS Access, generic ODBC, SAP (ODBC), KNIME
pip install sqlalchemy-hana hdbcli   # SAP HANA (Live)
```

Supported source types: `file` (Excel/CSV/JSON), `sqlserver`, `mysql`,
`postgres`, `access`, `odbc`, `sap_hana`, `sap_odbc`, `knime`. All of these are
**importable**; every staged dataset is **exportable** back out as
Excel/CSV/JSON via `GET /api/data/{ds}/export`. KNIME has no native database
wire protocol, so it's reached the same way SAP's ERP/BW is: through an
ODBC/JDBC bridge DSN that a KNIME Server workflow publishes its output table
to.

---

## Analytics modules

| Module               | Endpoint                     | Highlights |
|----------------------|------------------------------|------------|
| **Incoming Materials** *(full)* | `GET /api/analytics/incoming` | Open-PO pipeline, arrivals timeline, overdue/delay analysis, supplier & category breakdown, ABC of incoming, incoming-vs-stock coverage |
| Material Planning (MRP) | `GET /api/analytics/planning` | Net requirements, shortages/excess, reorder alerts, suggested orders (MOQ-aware), coverage days |
| Sourcing             | `GET /api/analytics/sourcing` | Supplier spend, on-time (OTIF) performance, price benchmarking, single-source risk |
| Costing              | `GET /api/analytics/costing`  | Multi-level BOM cost roll-up vs standard cost |
| FG Planning          | `GET /api/analytics/fg-planning` | Production plan exploded through BOM, component availability, feasibility |
| Stock Monitoring     | `GET /api/analytics/stock-monitoring` | Stock health & stockout risk: current stock vs safety/refill/max + incoming + demand, classified (stockout/critical/low/healthy/overstock); commodity & buyer filters |
| Inventory Monitoring | `GET /api/analytics/inventory-monitoring` | Inventory value & qty trends over time (from history snapshots) with commodity/location/buyer breakdowns and MoM change |
| Vendor Receipts      | `GET /api/analytics/vendor-receipts` | Inbound GRN trends by supplier & commodity over time |
| Movements            | `GET /api/analytics/movements` | Goods movements by type (GRN/issue/transfer/adjustment), inflow/outflow, recent activity |
| Forecasting          | `GET /api/analytics/forecasting` | Rolling M1/M2/M3 forecast vs current supply (stock + incoming); coverage gaps |
| Overall SCM          | `GET /api/analytics/overview` | Cross-module executive dashboard + data freshness |

**Global slicers:** every report endpoint accepts `commodity`, `buyer`,
`material`, `supplier`, `location` and a free-text `q` query param (options
from `GET /api/meta/slicers`, which also returns the distinct warehouse/site
`location` values from Warehouse Stock and Inventory Snapshots). `location`
sources on-hand quantities from that warehouse instead of the company-wide
total, so it genuinely changes stock-based figures (Stock Monitoring, FG
Planning, Forecasting, Overview). `q` does a case-insensitive substring search
across each page's key text columns (material, description, PO number,
supplier, etc.), matching the reference report's per-page search boxes. The
time-series endpoints (inventory-monitoring, vendor-receipts, movements) also
accept a `start`/`end` date range. Movements additionally accepts `mvt_type`
— a page-specific slicer (the reference report's "Mvt Master") rather than a
global one. The web app's global filter bar under the top nav covers
commodity/buyer/material/supplier/location/search/date-range across every
report page; the Movements page adds its own Movement Type dropdown.

All accept an optional `as_of=YYYY-MM-DD` query parameter.

---

## Testing

```bash
cd backend
source .venv/bin/activate
pytest
```

The suite covers column-alias mapping, type coercion/validation, and the
ingestion → analytics flow end-to-end against an in-memory database.

---

## Configuration

Copy `backend/.env.example` to `backend/.env` to override defaults
(`APP_DATABASE_URL`, `CORS_ORIGINS`, `UPLOAD_DIR`, `DEFAULT_AS_OF_DATE`), and
`frontend/.env.example` to `frontend/.env` to set `VITE_API_BASE` for a
separately hosted API.

---

## Roadmap

- Deepen MRP: time-phased/bucketed netting, planned-order firming, pegging.
- Sourcing: award scenarios, savings tracking, supplier scorecards.
- Costing: labour/overhead components, landed cost, currency conversion.
- FG Planning: capacity constraints, ATP/CTP, multi-period scheduling.
- Multi-user auth, saved DB connection profiles, scheduled auto-refresh.
- Excel/PDF export of every analysis view.
```
