# Power Fx Formula Translations

Conventions used below:
- `ThisFilter()` stands in for the standard filter predicate every screen
  applies first — see §"Standard filter predicate" — so individual formulas
  aren't repeated three times over.
- Anything marked **⚠ server-side** does not delegate (or cannot recurse) in
  client-side Power Fx and must be precomputed by a **Power Automate flow**
  or a **Dataflow**, materialized into a staging Dataverse table that the
  screen then just reads with a plain `Filter()`/`Sort()`. This mirrors what
  the Python backend already does in SQL/pandas on the server rather than in
  the browser — the Power Apps build should keep that same split, not try to
  force server-shaped work onto the Power Fx client.

---

## As-of resolution

Every "latest as of a date" concept in the app resolves the same way: find
the newest snapshot date **at or before** the cutoff, not just the newest
date overall (so an arbitrary picked date still resolves to what was true
then). Python's version is a SQL `ROW_NUMBER() OVER (PARTITION BY <key>
ORDER BY <date> DESC)` filtered to `rn = 1`; Power Fx has no window
functions, so use a **group-then-match** pattern:

```powerfx
// Latest snapshot_date at-or-before `cutoff` for a given material_code
// (mirrors latest_inventory_stock()'s per-(material,location) partition —
// do the same grouping key here, just material shown for brevity).
With(
    {_scoped: Filter(rrg_inventorysnapshot, rrg_snapshotdate <= cutoff)},
    With(
        {_latestPerMaterial:
            GroupBy(_scoped, "rrg_materialcode", "_rows")
        },
        ForAll(_latestPerMaterial,
            With({_maxDate: Max(_rows, rrg_snapshotdate)},
                LookUp(_rows, rrg_snapshotdate = _maxDate)
            )
        )
    )
)
```

For the two **high-volume** tables (`rrg_purchaseorder`, `rrg_warehousestock`
— hundreds of thousands of rows), this grouping pattern does **not**
delegate to Dataverse and will silently truncate at the 500/2000-row local
limit. **⚠ server-side**: precompute "latest open PO per (po,item)" and
"latest warehouse stock per (plant,storage_location,material)" as a
**scheduled Power Automate flow** (or a Dataverse view backed by a SQL
computed/indexed view if using Dataverse-in-Fabric) that writes into two
staging tables — `rrg_latestopenpo` and `rrg_latestwarehousestock` — refreshed
on every ingestion run (§`04-data-integration.md`). Every screen then reads
those staging tables directly, exactly like the Python backend reads the
result of its own `ROW_NUMBER()` query instead of the raw daily-history
table.

The **Material Planning** screen's Stock As Of picker means this resolution
must support an **arbitrary user-picked cutoff**, not just "today" — the
staging-table approach above still works, just parameterize the flow (or
keep the full history queryable via a secondary Dataflow/warehouse for that
one screen, since "any past date" can't be fully pre-materialized the way
"latest" can).

---

## Standard filter predicate

Every analytics screen applies the same shape of filter before doing
anything else — Commodity / Buyer / Material / Supplier / Location / free
text, all optional (blank = no restriction):

```powerfx
Filter(
    <source>,
    (gFilterCommodity = "" || rrg_commodity = gFilterCommodity) &&
    (gFilterBuyer = "" || rrg_buyer = gFilterBuyer) &&
    (gFilterMaterial = "" || rrg_materialcode = gFilterMaterial) &&
    (gFilterLocation = "" || <location-col> = gFilterLocation) &&
    (gFilterSearch = "" ||
        <material_code> in gFilterSearch ||          // substring, not equality —
        <description> in gFilterSearch                // see note below
    )
)
```

Power Fx's `in` operator on text does substring containment already, but is
**case-sensitive**; match the Python backend's case-insensitive substring
search with `IsMatch(Lower(<field>), Lower(gFilterSearch))` or
`Find(Lower(gFilterSearch), Lower(<field>)) > 0` if `in` proves
case-sensitive in your target Power Apps version — confirm against the
current runtime, since this has changed across Power Fx versions.

**Supplier** doesn't filter every table directly (POs/receipts have a
`supplier_code` column; Material Planning and FG Planning instead intersect
against `rrg_sobmaster` — see next section) — apply it per-screen the way
each Python module does, not as a blanket predicate.

### Supplier → material codes (via SOB Master)

```powerfx
// Set of material codes sourced from the selected vendor — mirrors
// supplier_material_codes(). Returns all materials when no supplier picked.
Set(varSupplierMaterials,
    If(gFilterSupplier = "",
        Blank(),  // "no restriction" sentinel — check for Blank() before using
        AddColumns(
            Filter(rrg_sobmaster, rrg_vendorcode = gFilterSupplier),
            "code", rrg_material.rrg_materialcode
        )
    )
)
```

---

## Vendors by material (Material Planning's Vendor column)

All vendors sourcing a material, **highest sourcing share first**,
comma-joined — mirrors `_vendors_by_material()`:

```powerfx
// For one material_code `m`:
Concat(
    Sort(
        Filter(rrg_sobmaster, rrg_material.rrg_materialcode = m),
        rrg_share,
        Descending
    ),
    Coalesce(rrg_vendorname, rrg_vendorcode, "Unassigned"),
    ", "
)
```

Note: the Python version also de-duplicates by vendor **name** (two SOB rows
for the same material with the same resolved name collapse to one entry) —
if a material can have two SOB rows sharing a display name, wrap the above
in a `Distinct()` over the name before `Concat`-ing, keeping the
highest-share row's position for each distinct name.

---

## Material Planning rollup (the per-row MRP calculation)

This is the single most important formula in the app — it runs once per row
every time the Stock As Of date, or any global filter, changes.

**Status classification** (worst-first order: Stockout > Risk > Alarm >
Safe/Excess):

```powerfx
Switch(true,
    currentStock <= 0, "Stockout",
    currentStock < safetyStock, "Risk",
    refillLevel <> 0 && currentStock < refillLevel, "Alarm",
    maxLevel <> 0 && currentStock > maxLevel, "Excess",
    "Safe"
)
```

**Receipts for the month-to-date through the picked date** (GR − reversal −
return-to-vendor, mirrors `_receipts_qty_by_material()`):

```powerfx
// periodStart = first day of the month containing `asOfDate`; asOfDate = the
// picked Stock As Of date, or Today() when cleared.
With({_rows: Filter(rrg_movement,
        rrg_materialcode.rrg_materialcode = m &&
        rrg_movementdate >= periodStart && rrg_movementdate <= asOfDate &&
        rrg_mvt in ["101","102","501"]
     )},
    Sum(Filter(_rows, rrg_mvt = "101"), rrg_qty)
    - Sum(Filter(_rows, rrg_mvt = "102"), rrg_qty)
    - Sum(Filter(_rows, rrg_mvt = "501"), rrg_qty)
)
```

**M1–M4 net-requirement / balance rollup** — this is a genuine 4-step
sequential recurrence (`Bal[n]` feeds `Forecast[n+1]`), which Power Fx can
express as 4 unrolled steps (there are always exactly 4 months, so no true
recursion is needed — unlike the BOM roll-up/explosion below):

```powerfx
With(
    {
        _bal0: currentStock,
        _ss:   safetyStock
    },
    With({_fc1: Max(0, m1Demand + _ss - _bal0)},
    With({_bal1: (_fc1 + _bal0) - (m1Demand + _ss)},
    With({_fc2: Max(0, m2Demand + _ss - _bal1)},
    With({_bal2: (_fc2 + _bal1) - (m2Demand + _ss)},
    With({_fc3: Max(0, m3Demand + _ss - _bal2)},
    With({_bal3: (_fc3 + _bal2) - (m3Demand + _ss)},
    With({_fc4: Max(0, m4Demand + _ss - _bal3)},
    With({_bal4: (_fc4 + _bal3) - (m4Demand + _ss)},
        {
            m1_forecast: _fc1, m1_bal: _bal1,
            m2_forecast: _fc2, m2_bal: _bal2,
            m3_forecast: _fc3, m3_bal: _bal3,
            m4_forecast: _fc4, m4_bal: _bal4
        }
    ))))))))
)
```

`Forecast[n] = max(0, Demand[n] + Safety − Bal[n-1])`,
`Bal[n] = (Forecast[n] + Bal[n-1]) − (Demand[n] + Safety)`, `Bal[0] =
current stock` — identical semantics to `material_planning.py`'s loop over
`MONTHS`.

**Reach days**: `If(m1Demand / 20 > 0, currentStock / (m1Demand / 20),
Blank())` — 20 working days/month, matches `WORKING_DAYS_PER_MONTH`.

Wrap all of the above in `ForAll(<filtered materials>, ...)` writing into a
collection (`colPlanningRows`) that the `cmpSortableTable` then binds to,
re-running the `ForAll` in the Stock-As-Of date picker's `OnChange` and in
the global filter bar's `OnChange`. For datasets in the thousands of
materials this is fine client-side (unlike the two high-volume tables
above) since it's one row per **material**, not per snapshot-day.

---

## Stock health classification (Stock Monitoring)

Different label set and order from Material Planning's, despite similar
inputs — keep them as two distinct Switch()es, don't try to share one:

```powerfx
Switch(true,
    sapStock <= 0, "stockout",
    sapStock < safetyStock, "critical",
    refillLevel <> 0 && sapStock < refillLevel, "low",
    maxLevel <> 0 && sapStock > maxLevel, "overstock",
    "healthy"
)
```

`at_risk = status in ["stockout","critical","low"] || projected < 0`, where
`projected = sapStock + openPO - demand`. `cover_days = If(demand/90 > 0,
sapStock / (demand/90), Blank())` (demand here is a 90-day total, not
monthly — different divisor from Material Planning's reach-days, don't
conflate).

---

## Forecast gap & status

```powerfx
total3m: m1Qty + m2Qty + m3Qty,
available: stock + incoming,
gap3m: Max(0, total3m - available),
status: Switch(true,
    gap3m > 0, "short",
    available > total3m * 1.5, "excess",
    "ok"
)
```

---

## ABC classification (cumulative value share)

Classic 80/15/5 rule by cumulative share of total value, **not** a fixed
per-item threshold — mirrors `abc_classify()`:

```powerfx
// `items` = a table with a `value` column, already the population to classify.
With(
    {_total: Sum(items, value)},
    With(
        {_sorted: AddColumns(Sort(items, value, Descending), "rn", RandBetween(1,1))}, // placeholder — see note
        // Power Fx has no native running-sum window function either.
        // ⚠ server-side for tables above a few hundred rows: compute the
        // cumulative sum in a Power Automate flow (Do Until, or an Apply-to-
        // each with a running total variable) or in a Dataflow, writing
        // `cum_share` back as a column. For small in-memory tables (a
        // filtered subset), a client-side running total can be built with
        // `Sort()` + `AddColumns()` + a helper column via `Index` and a
        // recursive `Sum(FirstN(_sorted, Index), value)`, but this is O(n²)
        // and should be capped to a few hundred rows.
        {}
    )
)
```

In practice: run ABC classification **server-side** (a Power Automate flow
or Dataflow step) whenever the underlying value population changes (new PO
snapshot, new BOM cost), and store the resulting class (`A`/`B`/`C`)
directly on the row (e.g. a `rrg_abcclass` column on a
`rrg_incomingabcstaging` table for the Incoming screen's "ABC of Incoming
Value" panel). Don't attempt a live client-side cumulative-sum in Power Fx
— there's no delegable running-total primitive.

---

## BOM cost roll-up & BOM explosion — ⚠ server-side (recursive)

Both `costing.py::_roll_up()` and `fg_planning.py::_explode()` are
**recursive graph walks** over the BOM (a parent can have sub-assemblies
that are themselves parents, with a cycle guard). Classic Power Fx canvas
formulas **cannot recurse** (no user-defined recursive functions in the
canvas formula language as of this writing) — this must be done
server-side:

**Recommended approach**: a Power Automate flow (`flowBomRollup`), triggered
whenever `rrg_bomline` or `rrg_material.rrg_map` changes (or on a schedule),
that:
1. Loads the whole BOM into a flow variable as an adjacency list
   (`{parent → [(component, qty), ...]}`).
2. For **costing**: walks every FG bottom-up with a `Do Until` loop —
   process components with no unresolved sub-assembly first, accumulate
   `rolled_up_cost[parent] = Σ qty × (cost[component] or rolled_up_cost[component])`,
   using a "seen" set per top-level parent to guard cycles exactly like the
   Python `seen` set.
3. For **FG explosion**: for each row in `rrg_productionplan`, walks
   top-down accumulating gross requirement per leaf component
   (`gross[component] += qty_needed × qty_per`), recursing into
   sub-assemblies the same way `_explode()` does.
4. Writes results into two staging tables the Costing/FG Planning screens
   read directly:
   - `rrg_costrollup`: `fg_material` (lookup), `components` (count),
     `rolled_up_cost`, `standard_cost`, `variance`, `variance_pct`.
   - `rrg_componentrequirement`: `component` (lookup), `required`,
     `on_hand`, `incoming`, `available`, `shortage`, `status` — plus a
     `rrg_fgfeasibility` table (`fg_material`, `planned_qty`,
     `component_count`, `at_risk`, `constraining_components` as a
     semicolon-joined text list).

Both the Costing and FG Planning **screens themselves** then contain no
recursion at all — they just `Filter()`/`Sort()` these two staging tables,
exactly as fast and exactly as delegable as any other screen. This mirrors
the Python architecture too: the recursion already happens once per request
on the FastAPI server, not in the React browser — Power Apps just moves that
"server" role to a flow instead of to Python.

If your Power Platform tier has **Dataverse plugins** or **Power Fx code
components (PCF)** available, a custom plugin/PCF component doing the same
recursion in C#/TypeScript on save of `rrg_bomline` is an equally valid
(and lower-latency) alternative to the flow above — pick whichever fits the
team's existing tooling.

---

## On-time delivery (Sourcing)

Match each receipt to its PO by PO number, compare dates:

```powerfx
// Per supplier, needs rrg_receipt (pending-upstream) joined to rrg_purchaseorder on po number.
With(
    {_matched: AddColumns(
        Filter(rrg_receipt, !IsBlank(rrg_ponumber)),
        "expected", LookUp(rrg_purchaseorder, rrg_po = rrg_receipt[@rrg_ponumber]).rrg_deliverydate
    )},
    With({_withExpected: Filter(_matched, !IsBlank(expected))},
        AddColumns(_withExpected, "onTime", rrg_receiptdate <= expected)
    )
)
// Then GroupBy supplier_code: deliveries = CountRows, on_time = Sum(onTime as 1/0),
// on_time_pct = 100 * on_time / deliveries.
```

`LookUp` inside `AddColumns` over a large PO table doesn't delegate well —
prefer a **Dataverse relationship** (`rrg_receipt.rrg_ponumber` as an actual
Lookup column to `rrg_purchaseorder`) so this becomes a delegable
`ShowColumns`/relationship traversal instead of a per-row `LookUp` scan, or
push this aggregation into the same staging-table flow pattern used for the
BOM roll-ups if receipt volume is large.

---

## Price benchmark (Sourcing)

Per material, across every PO line **and** receipt line with a positive
price, from ≥2 distinct suppliers:

```powerfx
With({_prices: Filter(
        Table(
            AddColumns(Filter(rrg_purchaseorder, rrg_netprice > 0), "price", rrg_netprice),
            AddColumns(Filter(rrg_receipt, rrg_unitprice > 0), "price", rrg_unitprice)
        ),
        true
    )},
    // GroupBy material_code: suppliers = distinct supplier_code count,
    // min/max/avg(price); keep only suppliers > 1;
    // spread_pct = 100 * (max-min) / min
    _prices
)
```

---

## Single-source risk (Sourcing)

Materials appearing in POs+receipts with exactly one distinct
`supplier_code` across both:

```powerfx
With(
    {_pairs: Distinct(
        Table(
            ShowColumns(rrg_purchaseorder, "rrg_materialcode", "rrg_suppliercode"),
            ShowColumns(rrg_receipt, "rrg_materialcode", "rrg_suppliercode")
        ),
        rrg_materialcode & "|" & rrg_suppliercode
    )},
    // GroupBy material_code, keep groups where CountRows = 1
    _pairs
)
```

---

## Period bucketing (Dashboard drilldown charts)

The Year→Quarter→Month→Day hierarchy buckets a date the same way at every
level — `_bucket()` in `overview.py`:

```powerfx
Switch(varGrain,
    "yearly",    {key: Text(Year(d)), label: Text(Year(d)), periodStart: Date(Year(d),1,1), periodEnd: Date(Year(d),12,31)},
    "quarterly", With({_q: RoundUp(Month(d)/3, 0)},
                    {key: Year(d) & "-Q" & _q, label: "Q" & _q & " " & Year(d),
                     periodStart: Date(Year(d), (_q-1)*3+1, 1),
                     periodEnd: DateAdd(DateAdd(Date(Year(d), (_q-1)*3+1, 1), 3, Months), -1, Days)}),
    "monthly",   {key: Text(d, "yyyy-mm"), label: Text(d, "mmm yyyy"),
                  periodStart: Date(Year(d), Month(d), 1),
                  periodEnd: DateAdd(DateAdd(Date(Year(d), Month(d), 1), 1, Months), -1, Days)},
    // "daily"
    {key: Text(d, "yyyy-mm-dd"), label: Text(d, "dd mmm yyyy"), periodStart: d, periodEnd: d}
)
```

Inventory (a **stock**) buckets to the period's **last** snapshot value;
incoming receipts (a **flow**) buckets to the period's **sum**. Keep that
distinction — don't sum inventory value across a period or you'll double
count.

Re-render the *whole* chart at the next granularity on tap (never narrow to
a single branch) by re-running the bucketing `GroupBy` over `varGrain`; reset
`varGrain` to `"yearly"` in the global filter bar's `OnChange`.

---

## Top-N with "Other"

```powerfx
With({_ranked: Sort(grouped, value, Descending)},
    With({_head: FirstN(_ranked, n), _tail: Skip(_ranked, n)},
        If(CountRows(_tail) > 0,
            Table(_head, {name: "Other", value: Sum(_tail, value)}),
            _head
        )
    )
)
```

---

## Badge color lookup

One shared lookup table drives every status badge across every screen —
avoids re-deriving colors per screen the way the React app's per-page
`STATUS_COLOR`/`STATUS_BADGE` maps do, but consolidated:

| Status value | Badge color | Used on |
|---|---|---|
| `Stockout` / `stockout` | red | Planning, Stock Monitoring |
| `Risk` / `critical` | red | Planning, Stock Monitoring |
| `Alarm` / `low` | amber | Planning, Stock Monitoring |
| `Safe` / `healthy` / `ok` | green | Planning, Stock Monitoring, FG Planning, Forecasting |
| `Excess` / `overstock` / `excess` | purple | Planning, Stock Monitoring, Forecasting |
| `short` | red | FG Planning, Forecasting |
| `overdue` | red | Incoming |
| `due_this_week` | amber | Incoming |
| `due_this_month` | blue | Incoming |
| `future` | green | Incoming |
| `no_date` | grey | Incoming |
| `A` / `B` / `C` (ABC) | green / blue / grey | Incoming |

Store this as a small static Dataverse table (`rrg_statuscolor`: `status`,
`colorhex`) or a Power Fx `Table()` constant in an app-level named formula,
and have `cmpBadge` do a single `LookUp` against it.

---

## Supplier options (global filter dropdown)

```powerfx
// Mirrors supplier_options_db(): distinct vendor_code + a representative name.
AddColumns(
    GroupBy(rrg_sobmaster, "rrg_vendorcode", "_rows"),
    "name", Coalesce(First(_rows).rrg_vendorname, "")
)
```

## Location options (global filter dropdown)

```powerfx
// Mirrors location_options_db(): union of InventorySnapshot.location and
// WarehouseStock.plant (the *site*-level column, not storage_location).
Distinct(
    Table(
        ShowColumns(rrg_inventorysnapshot, "rrg_location") As _l,
        ShowColumns(rrg_warehousestock, "rrg_plant") As _p
    ),
    Coalesce(_l.rrg_location, _p.rrg_plant)
)
```
