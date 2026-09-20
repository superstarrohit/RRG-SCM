"""Shared helpers for analytics modules."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BOMLine,
    InventorySnapshot,
    LocationMaster,
    Material,
    MovementMaster,
    PurchaseOrder,
    SOBMaster,
    WarehouseStock,
)

_MODEL_BY_NAME = {
    "materials": Material,
    "location_master": LocationMaster,
    "movement_master": MovementMaster,
    "sob_master": SOBMaster,
    "open_pos": PurchaseOrder,
    "warehouse_stock": WarehouseStock,
    "inventory_snapshots": InventorySnapshot,
    "bom": BOMLine,
}


def load_df(db: Session, name: str) -> pd.DataFrame:
    """Load a model table into a DataFrame (empty frame if no rows).

    Reads via the DBAPI cursor (pd.read_sql_query) rather than materializing
    ORM objects first — daily-snapshot dumps can run into the hundreds of
    thousands of rows, and hydrating each one into a mapped Python object
    before ever touching pandas made those loads an order of magnitude
    slower than they needed to be. Uses the session's own connection so it
    still sees whatever that session has written but not yet committed.
    """
    model = _MODEL_BY_NAME.get(name)
    if model is None:
        # A former demo table that has since been removed. Callers still ask
        # for it by name (stock, demand, forecast, …); hand back an empty
        # frame so their `.empty` guards trip instead of raising.
        return pd.DataFrame()
    cols = [c.name for c in model.__table__.columns]
    df = pd.read_sql_query(select(model), db.connection())
    if df.empty:
        return pd.DataFrame(columns=cols)
    return df[cols]


# The uploaded material_master stores each field under its own name (map,
# rm_material_code, material_description, total_leadtime, abc, refill_level,
# …). Analytics were written against friendlier internal names, so this maps
# the raw column -> the internal name the modules already read.
_MATERIAL_ALIASES = {
    "rm_material_code": "material_code",
    "material_description": "description",
    "map": "unit_cost",             # moving-average price
    "total_leadtime": "lead_time_days",
}


def materials_df(db: Session) -> pd.DataFrame:
    """Load the material master with the internal column names analytics expect.

    Keeps every raw uploaded column and *adds* the derived aliases
    (material_code, description, unit_cost, lead_time_days) plus a few fields
    the file doesn't carry directly: category (falls back to commodity),
    reorder_point (SAP reorder point ≈ refill_level here), min_order_qty
    (defaults to 0), and abc_class (the numeric abc 1/2/3 rendered A/B/C).
    Every analytics module goes through this instead of load_df(db,
    "materials"), so none of them need to know the raw schema's names.
    """
    df = load_df(db, "materials")
    if df.empty:
        # Give callers the derived columns too, so downstream selects/… don't
        # KeyError on an empty master.
        for extra in ("material_code", "description", "unit_cost", "lead_time_days",
                      "category", "reorder_point", "min_order_qty", "abc_class"):
            if extra not in df:
                df[extra] = pd.Series(dtype="object")
        return df
    for src, dst in _MATERIAL_ALIASES.items():
        if src in df and dst not in df:
            df[dst] = df[src]
    if "category" not in df:
        df["category"] = df.get("commodity")
    if "reorder_point" not in df:
        df["reorder_point"] = pd.to_numeric(df.get("refill_level"), errors="coerce").fillna(0.0)
    if "min_order_qty" not in df:
        df["min_order_qty"] = 0.0
    if "abc_class" not in df and "abc" in df:
        _abc = {1: "A", 2: "B", 3: "C", "1": "A", "2": "B", "3": "C"}
        df["abc_class"] = df["abc"].map(_abc)
    return df


def to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def abc_classify(values: pd.Series, a: float = 0.8, b: float = 0.95) -> pd.Series:
    """Classic ABC by cumulative value share (A=top 80%, B=next 15%, C=rest)."""
    if values.empty or values.fillna(0).sum() == 0:
        return pd.Series(["C"] * len(values), index=values.index)
    order = values.fillna(0).sort_values(ascending=False)
    cum = order.cumsum() / order.sum()
    cls = pd.Series(index=order.index, dtype="object")
    cls[cum <= a] = "A"
    cls[(cum > a) & (cum <= b)] = "B"
    cls[cum > b] = "C"
    return cls.reindex(values.index).fillna("C")


def safe_round(x, ndigits: int = 2):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return 0.0
    return round(float(x), ndigits)


def today(as_of: date | None = None) -> pd.Timestamp:
    return pd.Timestamp(as_of or date.today())


def allowed_codes(materials: pd.DataFrame, commodity=None, buyer=None, material=None):
    """Set of material_codes matching the commodity/buyer/material slicers, or None."""
    if materials.empty or not (commodity or buyer or material):
        return None
    df = materials
    if commodity and "commodity" in df:
        df = df[df["commodity"] == commodity]
    if buyer and "buyer" in df:
        df = df[df["buyer"] == buyer]
    codes = set(df["material_code"])
    if material:
        codes &= {material}
    return codes


def filter_codes(df: pd.DataFrame, codes) -> pd.DataFrame:
    """Restrict a frame to the allowed material_codes (no-op if codes is None)."""
    if codes is None or df.empty or "material_code" not in df:
        return df
    return df[df["material_code"].isin(codes)]


def filter_supplier(df: pd.DataFrame, supplier) -> pd.DataFrame:
    """Restrict a frame to one supplier (no-op if not given / no column)."""
    if not supplier or df.empty or "supplier_code" not in df:
        return df
    return df[df["supplier_code"] == supplier]


def filter_location(df: pd.DataFrame, location) -> pd.DataFrame:
    """Restrict a frame to one location/site (no-op if not given / no column).

    "Location" is site/warehouse-level throughout the app: WarehouseStock's
    ``warehouse_code`` (e.g. "WH-NORTH") and InventorySnapshot's ``location``
    both operate at that granularity — WarehouseStock's own ``location``
    field is a finer bin/shelf position and is not what the slicer means.
    """
    if not location or df.empty:
        return df
    col = "warehouse_code" if "warehouse_code" in df else "location" if "location" in df else None
    if col is None:
        return df
    return df[df[col] == location]


def apply_search(df: pd.DataFrame, q: str | None, columns: list[str]) -> pd.DataFrame:
    """Free-text search across the given columns (case-insensitive substring),
    matching the reference report's per-page search boxes.
    """
    if not q or df.empty:
        return df
    q_low = str(q).strip().lower()
    if not q_low:
        return df
    cols = [c for c in columns if c in df]
    if not cols:
        return df
    mask = pd.Series(False, index=df.index)
    for c in cols:
        mask = mask | df[c].astype(str).str.lower().str.contains(q_low, na=False, regex=False)
    return df[mask]


def stock_by_material(stock: pd.DataFrame, warehouse_stock: pd.DataFrame, location=None) -> dict:
    """On-hand qty per material_code.

    Warehouse Stock (latest daily snapshot) is the on-hand source: with no
    location selected it sums every plant/storage location, and with a
    location (plant) selected it sums only that plant — so the Location
    slicer genuinely changes the figures. Falls back to a legacy company-wide
    ``stock`` dump (qty_on_hand) only if no warehouse stock is present.
    """
    if not warehouse_stock.empty and "material_code" in warehouse_stock and "qty" in warehouse_stock:
        df = warehouse_stock
        if location and "warehouse_code" in df:
            df = df[df["warehouse_code"] == location]
        df = df.copy()
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0.0)
        return df.groupby("material_code")["qty"].sum().to_dict()
    if stock.empty or "qty_on_hand" not in stock:
        return {}
    s = stock.copy()
    s["qty_on_hand"] = pd.to_numeric(s["qty_on_hand"], errors="coerce").fillna(0.0)
    return s.groupby("material_code")["qty_on_hand"].sum().to_dict()


def latest_open_pos(db: Session) -> pd.DataFrame:
    """Load the *current* state of every open PO line.

    The ``open_pos`` dump is uploaded as one row per PO line *per day* it was
    open (up to ~400k rows) — open_qty depletes over the line's life until
    fully received. Materializing that whole table into pandas on every
    request (the generic ``load_df`` path) took 15s+ per call, so this filters
    to the latest ``snapshot_date`` per (po, item) in SQL instead, via a
    ROW_NUMBER() window, and only pulls that much smaller result set into
    Python. Columns are renamed to the internal names every analytics module
    already expects (po_number, po_line, material_code, order_qty,
    received_qty, unit_price, order_date, expected_date, supplier_name,
    currency), so nothing downstream needs to know about the raw upload's own
    column names.
    """
    rn = (
        func.row_number()
        .over(partition_by=(PurchaseOrder.po, PurchaseOrder.item), order_by=PurchaseOrder.snapshot_date.desc())
        .label("rn")
    )
    sub = select(PurchaseOrder, rn).subquery()
    rows = db.execute(select(sub).where(sub.c.rn == 1)).all()
    cols = [c.name for c in PurchaseOrder.__table__.columns]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame([dict(r._mapping) for r in rows])[cols]
    df = df.rename(columns={
        "po": "po_number", "item": "po_line", "material": "material_code",
        "po_qty": "order_qty", "net_price": "unit_price",
        "po_date": "order_date", "delivery_date": "expected_date",
        "name": "supplier_name",
    })
    order_qty = pd.to_numeric(df.get("order_qty"), errors="coerce").fillna(0.0)
    open_qty = pd.to_numeric(df.get("open_qty"), errors="coerce").fillna(0.0)
    df["received_qty"] = (order_qty - open_qty).clip(lower=0)
    if "currency" not in df:
        df["currency"] = "INR"
    return df


def latest_warehouse_stock(db: Session) -> pd.DataFrame:
    """Load the *current* on-hand per plant × storage location × material.

    The warehouse-stock dump is a daily history (~360k rows). This collapses
    it to the latest ``stock_date`` per (plant, storage_location, material)
    in SQL, then renames to the internal names the on-hand calculations use
    (material_code, warehouse_code, qty), keeping storage_location and value.
    """
    rn = (
        func.row_number()
        .over(
            partition_by=(WarehouseStock.plant, WarehouseStock.storage_location, WarehouseStock.material),
            order_by=WarehouseStock.stock_date.desc(),
        )
        .label("rn")
    )
    sub = select(WarehouseStock, rn).subquery()
    rows = db.execute(select(sub).where(sub.c.rn == 1)).all()
    cols = [c.name for c in WarehouseStock.__table__.columns]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame([dict(r._mapping) for r in rows])[cols]
    return df.rename(columns={
        "material": "material_code", "plant": "warehouse_code", "stock": "qty",
    })


def location_options_db(db: Session) -> list[str]:
    """Distinct site/warehouse values, queried directly (no full-table load).

    Reads the distinct plant/location values straight from the warehouse
    stock and inventory history — the global slicer bar is hit on every page
    navigation, so this avoids materializing those large tables into pandas
    just to read one column off each.
    """
    vals = set(db.execute(
        select(InventorySnapshot.location).distinct().where(InventorySnapshot.location.isnot(None))
    ).scalars().all())
    vals |= set(db.execute(
        select(WarehouseStock.plant).distinct().where(WarehouseStock.plant.isnot(None))
    ).scalars().all())
    return sorted(vals)


def supplier_options_db(db: Session) -> pd.DataFrame:
    """Distinct vendors (code + name) from the SOB master, for the supplier slicer."""
    rows = db.execute(
        select(SOBMaster.vendor_code, func.max(SOBMaster.vendor_name))
        .where(SOBMaster.vendor_code.isnot(None))
        .group_by(SOBMaster.vendor_code).order_by(SOBMaster.vendor_code)
    ).all()
    return pd.DataFrame(
        [{"supplier_code": vc, "name": nm or ""} for vc, nm in rows],
        columns=["supplier_code", "name"],
    )


def supplier_material_codes(db: Session, supplier) -> set | None:
    """Material codes sourced from a given vendor (via the SOB master), or None."""
    if not supplier:
        return None
    rows = db.execute(
        select(SOBMaster.material).where(SOBMaster.vendor_code == supplier)
    ).scalars().all()
    return {r for r in rows if r}


def location_options(*frames: pd.DataFrame) -> list[str]:
    """Union of distinct site/warehouse values across one or more frames.

    Prefers ``warehouse_code`` (WarehouseStock's site-level column) over the
    plain ``location`` column, since the latter is bin/shelf-level on that
    model but warehouse-level on InventorySnapshot — see filter_location().
    """
    vals: set[str] = set()
    for df in frames:
        if df.empty:
            continue
        col = "warehouse_code" if "warehouse_code" in df else "location" if "location" in df else None
        if col:
            vals |= set(df[col].dropna().unique().tolist())
    return sorted(vals)


def filter_options(materials: pd.DataFrame, commodity=None, buyer=None,
                    material=None, supplier=None, location=None,
                    suppliers: pd.DataFrame | None = None,
                    locations: list[str] | None = None) -> dict:
    """The slicer option lists + current selection, for the UI."""
    def opts(col, df=materials):
        return sorted(df[col].dropna().unique().tolist()) if (not df.empty and col in df) else []

    mat_opts = []
    if not materials.empty and "material_code" in materials:
        d = materials.sort_values("material_code")
        mat_opts = [
            {"code": r["material_code"], "label": f"{r['material_code']} — {r.get('description') or ''}".rstrip(" —")}
            for _, r in d.iterrows()
        ]
    sup_opts = []
    if suppliers is not None and not suppliers.empty:
        d = suppliers.sort_values("supplier_code")
        sup_opts = [
            {"code": r["supplier_code"], "label": f"{r['supplier_code']} — {r.get('name') or ''}".rstrip(" —")}
            for _, r in d.iterrows()
        ]

    return {
        "commodity": opts("commodity"), "buyer": opts("buyer"),
        "material": mat_opts, "supplier": sup_opts,
        "location": locations or [],
        "selected": {
            "commodity": commodity, "buyer": buyer, "material": material,
            "supplier": supplier, "location": location,
        },
    }


def filter_dates(df: pd.DataFrame, col: str, start=None, end=None) -> pd.DataFrame:
    """Restrict a frame to rows whose ``col`` falls within [start, end]."""
    if df.empty or col not in df or (not start and not end):
        return df
    s = pd.to_datetime(df[col], errors="coerce")
    mask = s.notna()
    if start:
        mask &= s >= pd.Timestamp(start)
    if end:
        mask &= s <= pd.Timestamp(end)
    return df[mask]
