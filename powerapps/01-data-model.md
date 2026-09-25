# Dataverse Data Model

Naming convention: every custom table/column uses the `rrg_` publisher
prefix (swap for your own solution publisher prefix throughout). Each table
lists its Dataverse column, type, and — where it comes from an upload — the
raw source-file header aliases the current Python ingestion (`app/ingestion/dump_types.py`)
already accepts, so the Power Automate mapping in `04-data-integration.md`
stays consistent with what users already upload today.

Every table gets Dataverse's standard columns for free (`createdon`,
`modifiedon`, `ownerid`, the table's auto `rrg_<table>id` GUID primary key) —
these aren't listed below unless they replace a bespoke `id`/timestamp
column the SQLAlchemy model had (`TimestampMixin` → `createdon`/`modifiedon`,
so it needs no dedicated column).

---

## 1. `rrg_material` — Item Master

Source: `app/models/master.py::Material` (table `materials`). One row per
material/SKU. This is the hub table nearly everything else looks up against.

| Dataverse column | Type | Source column | Aliases accepted on upload | Notes |
|---|---|---|---|---|
| `rrg_materialcode` (primary name) | Text (64), **Alternate Key**, unique | `rm_material_code` | `material_code`, `material`, `item`, `sku`, `part_no`, `material no` | Required |
| `rrg_commodity` | Text (128) | `commodity` | `commodity group`, `sourcing group` | Choice column candidate if the commodity list is stable |
| `rrg_buyer` | Text (128) | `buyer` | `purchaser`, `planner`, `buyer name` | |
| `rrg_rough` | Text (64) | `rough` | `rough code`, `rgh` | |
| `rrg_description` | Text (255) | `material_description` | `description`, `desc`, `name` | Maps to internal `description` |
| `rrg_m1` … `rrg_m12` | Decimal | `m1` … `m12` | — | 12-month demand history |
| `rrg_average` | Decimal | `average` | `avg` | |
| `rrg_map` | Currency/Decimal | `map` | `moving average price`, `unit_cost`, `cost`, `price` | Maps to internal `unit_cost` |
| `rrg_abc` | Whole Number (or Choice A/B/C) | `abc` | — | 1/2/3 → mapped to A/B/C for display (`abc_class`) |
| `rrg_xyz` | Whole Number | `xyz` | — | |
| `rrg_abcxyz` | Whole Number | `abcxyz` | — | |
| `rrg_nofdeliveries` | Whole Number | `no_of_deliveries` | `deliveries` | |
| `rrg_leadtime` | Whole Number | `leadtime` | `lead time` | |
| `rrg_transittime` | Whole Number | `transit_time` | — | |
| `rrg_totalleadtime` | Whole Number | `total_leadtime` | `total lead time` | Maps to internal `lead_time_days` |
| `rrg_maxleadtime` | Decimal | `max_leadtime` | `max lead time` | |
| `rrg_sku` | Whole Number | `sku` | — | |
| `rrg_supplier` | Text (255) | `supplier` | `vendor`, `supplier name` | Free-text supplier name on the material record itself (distinct from the SOB Master's structured vendor split — see §4) |
| `rrg_lastmonthopening` | Decimal | `last_month_opening` | `opening` | |
| `rrg_demand` | Decimal | `demand` | — | **M1** demand |
| `rrg_demand2` | Decimal | `demand_2` | — | **M2** demand |
| `rrg_demand3` | Decimal | `demand_3` | — | **M3** demand |
| `rrg_demand4` | Decimal | `demand_4` | — | **M4** demand |
| `rrg_safetystock` | Decimal | `safety_stock` | `ss`, `safety` | |
| `rrg_refilllevel` | Decimal | `refill_level` | `refill`, `refill level`, `reorder level` | Maps to internal `reorder_point` when not set explicitly |
| `rrg_maxlevel` | Decimal | `max_level` | `max`, `max level`, `maximum` | |

**Derived-at-runtime fields** (computed in Power Fx / a view, not stored —
mirrors `materials_df()`'s aliasing in `common.py`): `category` (falls back
to `rrg_commodity` when absent), `reorder_point` (falls back to
`rrg_refilllevel`), `min_order_qty` (defaults to 0 — no source column exists
yet), `abc_class` (`1→A, 2→B, 3→C` lookup on `rrg_abc`).

---

## 2. `rrg_locationmaster` — Location Master

Source: `LocationMaster` (table `location_master`).

| Dataverse column | Type | Source | Aliases | Notes |
|---|---|---|---|---|
| `rrg_storagelocation` (primary name) | Text (64), Alternate Key, unique | `storage_location` | `location_code`, `storage loc`, `sloc` | Required |
| `rrg_locationname` | Text (255) | `location` | `location name`, `name`, `description` | |

---

## 3. `rrg_movementmaster` — Movement Type Master

Source: `MovementMaster` (table `movement_master`).

| Dataverse column | Type | Source | Aliases | Notes |
|---|---|---|---|---|
| `rrg_mvt` (primary name) | Text (16) | `mvt` | `movement type`, `movement`, `mvt type`, `mvt_type` | Required. **Not unique** in the source model — Dataverse table should allow duplicates or dedupe on load |
| `rrg_description` | Text (255) | `description` | `desc`, `movement description`, `name` | |

Reference values baked into every downstream formula (from `movements.py`
and `overview.py` — keep these as the canonical code list even though the
master table is freely editable):

| Code | Meaning | Direction |
|---|---|---|
| `101` | Goods Receipt – Purchase Order | Inflow (+), counts as "incoming receipt" |
| `102` | Reversal of Goods Receipt | Outflow (−), subtracted from incoming receipts |
| `201` | Issue to Production | Outflow (−) |
| `301` / `311` | Plant/storage transfer | Neither (nets to zero company-wide) |
| `501` | Return to Vendor | Outflow (−), subtracted from incoming receipts |
| `551` | Scrap | Outflow (−) |
| `601` | Delivery to Customer | Outflow (−) |

---

## 4. `rrg_sobmaster` — Source of Business Master

Source: `SOBMaster` (table `sob_master`). Many-to-many: one material can be
split across several vendors.

| Dataverse column | Type | Source | Aliases | Notes |
|---|---|---|---|---|
| `rrg_vendorcode` | Text (64) | `vendor_code` | `supplier_code`, `vendor no` | Required |
| `rrg_vendor` | Text (64) | `vendor` | `vendor short`, `vendor abbr` | |
| `rrg_vendorname` | Text (255) | `vendor_name` | `supplier name`, `name` | |
| `rrg_share` | Decimal (%) | `share` | `split`, `percent`, `%`, `sob` | Percent of spend for this vendor+material |
| `rrg_material` (Lookup → `rrg_material`) | Lookup | `material` | `material_code`, `rm_material_code`, `sku` | Required |
| `rrg_mat` | Text (128) | `mat` | `commodity`, `category` | |
| `rrg_description` | Text (255) | `description` | `material description`, `desc` | |

Primary name column: a calculated `rrg_vendorcode` + `rrg_material` concat,
since there's no natural single-field name.

---

## 5. `rrg_bomline` — Bill of Materials

Source: `BOMLine` (table `bom_lines`).

| Dataverse column | Type | Source | Aliases | Notes |
|---|---|---|---|---|
| `rrg_product` | Text (120) | `product` | `product family`, `product group`, `product name` | |
| `rrg_fgmaterial` (Lookup → `rrg_material`) | Lookup | `fg_material` | `fg_material_code`, `fg`, `finished good`, `parent`, `parent_material`, `assembly` | Required. Parent (finished good or sub-assembly) |
| `rrg_description` | Text (255) | `description` | `fg description`, `fg_description`, `product description` | FG's own description — used as a fallback display name when the FG isn't in `rrg_material` yet |
| `rrg_rmmaterial` (Lookup → `rrg_material`) | Lookup | `rm_material` | `rm_material_code`, `rm`, `component`, `component_material`, `child` | Required. Component consumed |
| `rrg_rmdescription` | Text (255) | `rm_description` | `component description`, `rm description`, `material description` | Fallback display name for the component |
| `rrg_qty` | Decimal | `qty` | `qty_per`, `quantity`, `usage`, `per` | Qty of component per 1 unit of parent |

Note: a BOM is a graph, not a tree — `rrg_fgmaterial` can itself appear as
someone else's `rrg_rmmaterial` (multi-level sub-assemblies). §`03-formulas.md`'s
roll-up/explosion formulas must recurse through this, with a cycle guard.

---

## 6. `rrg_purchaseorder` — Open Purchase Orders (daily snapshot)

Source: `PurchaseOrder` (table `purchase_orders`). **High volume**: one row
per PO line *per day* it stays open (can run into hundreds of thousands of
rows) — see the delegation/performance notes in `05-build-plan.md`.

| Dataverse column | Type | Source | Aliases | Notes |
|---|---|---|---|---|
| `rrg_snapshotdate` | Date only | `snapshot_date` | `date`, `as of`, `snapshot` | Indexed — every "latest state" query filters/partitions on this |
| `rrg_po` | Text (64) | `po` | `po_number`, `po no`, `order`, `purchase order` | Required. Renamed to `po_number` internally |
| `rrg_suppliername` | Text (255) | `name` | `supplier name`, `vendor name` | Renamed to `supplier_name` internally |
| `rrg_materialcode` (Lookup → `rrg_material`) | Lookup | `material` | `material_code`, `sku`, `part_no` | Required |
| `rrg_description` | Text (255) | `description` | `item description`, `material description` | |
| `rrg_poqty` | Decimal | `po_qty` | `order_qty`, `qty`, `quantity`, `ordered`, `po qty` | Renamed to `order_qty` |
| `rrg_povalue` | Currency | `po_value` | `order value`, `amount`, `line value` | |
| `rrg_deliverydate` | Date only | `delivery_date` | `expected_date`, `delivery date`, `eta`, `due date`, `expected`, `promised date` | Renamed to `expected_date` |
| `rrg_item` | Text (32) | `item` | `po_line`, `line`, `po item` | Renamed to `po_line` |
| `rrg_podate` | Date only | `po_date` | `order_date`, `po date`, `created`, `order dt` | Renamed to `order_date` |
| `rrg_openqty` | Decimal | `open_qty` | `open`, `balance`, `outstanding`, `remaining` | If blank, derive as `max(order_qty - received_qty, 0)` |
| `rrg_netprice` | Currency | `net_price` | `unit_price`, `price`, `unit cost`, `rate` | Renamed to `unit_price` |
| `rrg_suppliercode` | Text (64) | `supplier_code` | `supplier`, `vendor`, `vendor code` | |
| `rrg_shipping` | Text (32) | `shipping` | `shipping mode`, `mode of transport`, `incoterm` | |
| `rrg_tax` | Text (32) | `tax` | `tax code`, `gst` | |
| `rrg_createdby` | Text (120) | `created_by` | `buyer`, `requested by`, `raised by` | |

**Derived at read time** (`received_qty = order_qty − open_qty`, floored at
0; `currency` defaults `"INR"` when absent) — compute these in the Power Fx
formula/view that reads this table (§`03-formulas.md` §"Latest Open POs"),
don't store them.

Recommended Dataverse index: composite on (`rrg_po`, `rrg_item`,
`rrg_snapshotdate`) — mirrors `ix_purchase_orders_po_item_snapshot`.

---

## 7. `rrg_inventorysnapshot` — Inventory History

Source: `InventorySnapshot` (table `inventory_snapshots`). Daily
qty+value snapshot per material × location — the "current inventory value"
KPI on the Dashboard is the latest date's sum of `rrg_value`.

| Dataverse column | Type | Source | Aliases | Notes |
|---|---|---|---|---|
| `rrg_materialcode` (Lookup → `rrg_material`) | Lookup | `material_code` | `material`, `sku`, `rm_material_code` | Required |
| `rrg_location` | Text (64) | `location` | `plant`, `warehouse`, `site` | |
| `rrg_snapshotdate` | Date only | `snapshot_date` | `date`, `month`, `period`, `snapshot`, `stock_date` | Required, indexed |
| `rrg_qty` | Decimal | `qty` | `stock`, `quantity`, `on hand`, `soh` | |
| `rrg_value` | Currency | `value` | `stock value`, `amount`, `inventory value` | |

---

## 8. `rrg_movement` — Material Movements

Source: `Movement` (table `movements`). Transactional feed — receipts,
issues, transfers, returns, scrap.

| Dataverse column | Type | Source | Aliases | Notes |
|---|---|---|---|---|
| `rrg_movementdate` | Date only | `movement_date` | `date`, `posting date`, `mvt date` | Required, indexed |
| `rrg_materialcode` (Lookup → `rrg_material`) | Lookup | `material_code` | `rm_material_code`, `material`, `sku` | Required |
| `rrg_description` | Text (255) | `description` | `material_description`, `item description` | |
| `rrg_mvt` | Text (16) | `mvt` | `movement_type`, `mvt code`, `mvt no` | Required — join key to `rrg_movementmaster.rrg_mvt` |
| `rrg_mvttype` | Text (255) | `mvt_type` | `mvt_description`, `movement description`, `mvt desc` | Human label, already inline in the upload |
| `rrg_qty` | Decimal | `qty` | `quantity` | Signed |
| `rrg_value` | Currency | `value` | `amount`, `movement value` | Signed |
| `rrg_fromlocation` | Text (64) | `from_location` | `from`, `source location`, `issuing plant` | |
| `rrg_tolocation` | Text (64) | `to_location` | `to`, `destination location`, `receiving plant` | |
| `rrg_documentno` | Text (64) | `document_no` | `document`, `doc no`, `reference` | |

Recommended index: composite on (`rrg_materialcode`, `rrg_movementdate`) —
mirrors `ix_movements_material_date`.

---

## 9. `rrg_warehousestock` — Warehouse Stock (daily, per plant × sloc × material)

Source: `WarehouseStock` (table `warehouse_stock`). **High volume** — daily,
~360k rows in production. This is the "Location" slicer's data source
company-wide.

| Dataverse column | Type | Source | Aliases | Notes |
|---|---|---|---|---|
| `rrg_stockdate` | Date only | `stock_date` | `date`, `snapshot`, `as of` | Indexed |
| `rrg_plant` | Text (64) | `plant` | `warehouse`, `warehouse_code`, `site`, `wh` | Required. Renamed to `warehouse_code` internally — **this is the "Location" slicer's value**, not `rrg_storagelocation` below |
| `rrg_storagelocation` | Text (64) | `storage_location` | `sloc`, `bin`, `location_code`, `location` | Finer bin/shelf granularity — not the Location slicer |
| `rrg_materialcode` (Lookup → `rrg_material`) | Lookup | `material` | `material_code`, `sku`, `rm_material_code` | Required |
| `rrg_stock` | Decimal | `stock` | `qty`, `quantity`, `on hand`, `soh` | Renamed to `qty` internally |
| `rrg_value` | Currency | `value` | `stock value`, `amount`, `inventory value` | |

Recommended index: composite on (`rrg_plant`, `rrg_storagelocation`,
`rrg_materialcode`, `rrg_stockdate`) — mirrors
`ix_warehouse_stock_key_date`.

---

## 10. Pending-upstream tables (analytics modules already expect these)

These aren't wired into the current backend's `_MODEL_BY_NAME` /
`DUMP_TYPES`, so `load_df(db, "...")` for them returns an empty frame today
— but `sourcing.py`, `vendor_receipts.py`, `forecasting.py`, `fg_planning.py`,
`costing.py`, and `stock_monitoring.py` are already written against them. If
the backend later adds real ingestion for these, or if the Power Apps build
wants to get ahead of it, use this shape (inferred from how each analytics
module reads the corresponding DataFrame):

| Table | Purpose | Key columns (inferred) |
|---|---|---|
| `rrg_supplier` | Supplier master (name per code) | `supplier_code` (key), `name` |
| `rrg_receipt` | Goods-receipt (GRN) line detail — used by Sourcing (on-time %, price benchmark) and Vendor Receipts | `po_number`, `material_code`, `supplier_code`, `receipt_date`, `qty`, `unit_price`, `receipt_id` |
| `rrg_forecastline` | Per-material M1/M2/M3 forecast (distinct from `rrg_material`'s own `demand`/`demand_2..4` — Forecasting reads a **separate** `forecast` table, not the material master's demand columns) | `material_code`, `m1_qty`, `m2_qty`, `m3_qty` |
| `rrg_productionplan` | Planned FG production quantities, exploded through the BOM in FG Planning | `material_code` (the FG), `planned_qty` |
| `rrg_stock` | Legacy company-wide on-hand qty, used only as a **fallback** when `rrg_warehousestock` has no rows for a material (`stock_by_material()`'s fallback path) | `material_code`, `qty_on_hand` |

Until these exist, the Sourcing, Vendor Receipts, Forecasting, FG Planning
and Costing screens should render the same "upload X to see this report"
empty state the current backend already returns (see each module's `_empty()`
message in the Python source) — carry those exact messages into the Canvas
app's empty-state text so behavior matches.
