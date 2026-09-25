# Data Integration — Ingestion Pipeline

The current app's Data Workspace → Import tab lets a user upload a file (or
pull from a database/connector) against one of 9 "dump types," each with
flexible column aliases, into one of three load modes. This document
specifies the Power Automate equivalent, one flow per dump type (they can
share a single parameterized flow with a "dump type" input if preferred —
listed separately here for clarity).

## Load modes (apply to every dump type)

| Mode | Backend behavior | Power Automate equivalent |
|---|---|---|
| **Replace** | Truncate the target table, then bulk-insert the parsed rows | `Delete rows` (Dataverse "Delete a row" in a loop, or a bulk `Bulk Delete` job) then `Add a new row` per parsed row (or `Send a Dataverse request` with `CreateMultiple` for large volumes) |
| **Append** | Insert the parsed rows as-is, no dedup | `Add a new row` per parsed row |
| **Merge** | Upsert on one or more key columns: match existing rows by key, update them, insert the rest | For each parsed row: `List rows` filtered by the key column(s) → if found, `Update a row`; else `Add a new row`. For large files, prefer `Upsert a row` (Dataverse's native upsert action keyed on an **Alternate Key** — set the key columns listed in §`01-data-model.md` as Alternate Keys specifically so this works natively) |

For the two high-volume daily dumps (`open_pos`, `warehouse_stock`), always
default to **Replace** or a date-scoped **Append** (never re-upsert the
whole history) — matches how those are actually used today (a fresh daily
snapshot, not a correction to history).

## Common flow shape (every dump type)

1. **Trigger**: "When a file is created" (SharePoint/OneDrive connector) or
   manual trigger from the Canvas app's Import screen (`PowerAutomate.Run()`
   passing the uploaded file as a parameter — Power Apps can pass a file
   directly to a flow since attachments are supported as flow inputs).
2. **Parse**: Excel connector's "List rows present in a table" (for
   `.xlsx`), or `Parse CSV`/`Compose` + `split()` expressions (for
   `.csv`/`.tsv`), or `Parse JSON` (for `.json`) against a schema built from
   the dump type's field list.
3. **Header alias resolution**: for each target field, check the parsed
   file's header row against that field's alias list (case-insensitive,
   whitespace/underscore-insensitive — mirrors `FieldSpec.aliases`) and map
   the matching source column to the target column. Implement as a `Select`
   action with per-field `coalesce(header["exact"], header["alias1"],
   header["alias2"], ...)` expressions, or precompute the mapping in a
   `Compose` step the same way the current backend's preview endpoint
   reports `column_map` back to the user before import.
4. **Required-field check**: if any `required: true` field has no resolved
   source column, stop and surface the same "Missing required: X, Y" message
   the current `/import/preview` response returns — don't silently import a
   file with a missing required column.
5. **Type coercion**: `float`/`int` fields → `float()`/`int()` expressions
   with a fallback to 0 on parse failure (mirrors `pd.to_numeric(...,
   errors="coerce").fillna(0)`); `date` fields → `formatDateTime(...,
   'yyyy-MM-dd')` with a fallback to blank on parse failure.
6. **Load**: apply the Replace/Append/Merge action from the table above.
7. **Report back**: return `{rows_ingested, inserted, updated}` (mirrors the
   current upload response) to the Canvas app so `ResultBox` can show it.

## Per-dump-type flow specs

Each row below is one Power Automate flow (or one branch of a shared
parameterized flow) targeting the Dataverse table from `01-data-model.md`.
The alias lists are copied verbatim from `app/ingestion/dump_types.py` so
the mapping step is a faithful port, not a re-guess.

### `flowImportMaterials` → `rrg_material`
Required: `rm_material_code`. All other fields optional, aliases as listed
in `01-data-model.md` §1's source-column table. Recommended key for Merge:
`rm_material_code` (matches the model's own `unique=True` constraint) — set
this as the table's Alternate Key so `Upsert a row` works natively.

### `flowImportLocationMaster` → `rrg_locationmaster`
Required: `storage_location`. Key for Merge: `storage_location`.

### `flowImportMovementMaster` → `rrg_movementmaster`
Required: `mvt`. No uniqueness constraint upstream — Merge should still key
on `mvt` in practice (a movement code shouldn't have two descriptions), even
though the source model itself doesn't enforce it.

### `flowImportSobMaster` → `rrg_sobmaster`
Required: `vendor_code`, `material`. `material` resolves to a **Lookup** into
`rrg_material` — the flow must resolve `rm_material_code` → the material
record's GUID before writing (a `List rows` on `rrg_material` filtered by
code, or use the Alternate Key directly in the `Item` reference so Dataverse
resolves it for you). No natural single-column key for Merge — key on the
combination of `vendor_code` + `material`.

### `flowImportOpenPos` → `rrg_purchaseorder`
Required: `po`, `material`. `material` resolves to a Lookup the same way as
above. **Always Replace or same-day Append** — this is a daily snapshot
dump, not a corrections feed. After load, trigger `flowLatestOpenPoRollup`
(§`03-formulas.md`'s "As-of resolution" server-side note) to refresh the
`rrg_latestopenpo` staging table.

### `flowImportBom` → `rrg_bomline`
Required: `fg_material`, `rm_material`. Both resolve to Lookups into
`rrg_material` — note that `fg_material` for a sub-assembly will *also* need
to exist as its own `rrg_material` row (or the Lookup will fail) even though
sub-assemblies aren't independently "purchased" materials; if the source
file doesn't include sub-assembly codes in the material master, either relax
this to a plain text column instead of a Lookup, or auto-create stub
`rrg_material` rows for any `fg_material`/`rm_material` code not already
present. After load, trigger the BOM roll-up/explosion flows
(§`03-formulas.md` §"BOM cost roll-up & BOM explosion") since the graph
changed.

### `flowImportInventorySnapshots` → `rrg_inventorysnapshot`
Required: `material_code`, `snapshot_date`. Append-only in practice (each
upload adds a new date's snapshot); Replace only if reloading a corrected
history.

### `flowImportWarehouseStock` → `rrg_warehousestock`
Required: `plant`, `material`. Same daily-snapshot treatment as Open POs —
Replace or same-day Append, then refresh `rrg_latestwarehousestock`.

### `flowImportMovements` → `rrg_movement`
Required: `movement_date`, `material_code`, `mvt`. Append-only (a
transaction log, never replaced wholesale) unless explicitly reloading
history.

### Pending-upstream dump types (not in the current backend yet)

If/when these are added to the real backend's `DUMP_TYPES`, the same flow
pattern applies — provisional field lists (no confirmed aliases yet, since
no upload path exists today; use these as a starting point and confirm
against whatever file format the business actually has for each):

- `flowImportSuppliers` → `rrg_supplier` (`supplier_code` required, `name`).
- `flowImportReceipts` → `rrg_receipt` (`po_number`, `material_code`,
  `receipt_date`, `qty`, `unit_price`, `supplier_code`, `receipt_id`).
- `flowImportForecast` → `rrg_forecastline` (`material_code`, `m1_qty`,
  `m2_qty`, `m3_qty`).
- `flowImportProductionPlan` → `rrg_productionplan` (`material_code`,
  `planned_qty`).
- `flowImportStock` (legacy fallback) → `rrg_stock` (`material_code`,
  `qty_on_hand`).

## Database & connector import (Data Workspace's "DB Import" mode)

The current backend supports pulling directly from SQL Server, MySQL,
PostgreSQL, MS Access, generic ODBC, SAP HANA, SAP ODBC and KNIME, with a
table name or raw SQL override. In Power Platform, map each to:

| Source | Power Platform path |
|---|---|
| SQL Server | Native **SQL Server** connector (`Get rows`, or `Execute a SQL query` for the raw-query override) |
| PostgreSQL / MySQL | Premium **PostgreSQL** / **MySQL** connectors |
| SAP HANA | Premium **SAP HANA** connector, or Dataverse's **SAP** virtual tables if licensed |
| ODBC / SAP ODBC / KNIME / MS Access | Power Platform's **on-premises data gateway** + the generic **ODBC** connector (Access typically needs a gateway-hosted ODBC DSN, since there's no first-party Access connector) |

Every one of these still ends by feeding the same alias-resolution → load
pipeline above — the *source* connector changes, the *target* mapping logic
doesn't. Build the alias-mapping step as a shared **child flow**
(`flowApplyDumpTypeMapping`, parameterized by dump-type key) that every
source-specific flow calls, so the mapping table in `01-data-model.md` is
defined and maintained in exactly one place.

## Export

The current app exports any dataset back to Excel/CSV/JSON. In Power Apps:
`Export()` isn't a built-in canvas function for arbitrary tables, so either
(a) call a small Power Automate flow that builds the file (Excel connector's
"Create table"/CSV `Compose` + `Create file` in SharePoint/OneDrive) and
returns a download link, or (b) if the destination just needs to leave the
device, use `Notify`+`Download()`/`SaveData` for a CSV built client-side via
`Concat()` over the rows (fine for the same up-to-a-few-thousand-row scale
the current app's own export already targets).
