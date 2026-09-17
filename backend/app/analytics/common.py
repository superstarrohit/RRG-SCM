"""Shared helpers for analytics modules."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BOMLine,
    Demand,
    Forecast,
    InventorySnapshot,
    Material,
    Movement,
    ProductionPlan,
    PurchaseOrder,
    Receipt,
    Stock,
    Supplier,
    WarehouseStock,
)

_MODEL_BY_NAME = {
    "materials": Material,
    "suppliers": Supplier,
    "stock": Stock,
    "warehouse_stock": WarehouseStock,
    "open_pos": PurchaseOrder,
    "receipts": Receipt,
    "demand": Demand,
    "forecast": Forecast,
    "inventory_snapshots": InventorySnapshot,
    "movements": Movement,
    "bom": BOMLine,
    "production_plan": ProductionPlan,
}


def load_df(db: Session, name: str) -> pd.DataFrame:
    """Load a model table into a DataFrame (empty frame if no rows)."""
    model = _MODEL_BY_NAME[name]
    rows = db.execute(select(model)).scalars().all()
    if not rows:
        cols = [c.name for c in model.__table__.columns]
        return pd.DataFrame(columns=cols)
    records = [
        {c.name: getattr(r, c.name) for c in model.__table__.columns} for r in rows
    ]
    return pd.DataFrame.from_records(records)


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


def filter_options(materials: pd.DataFrame, commodity=None, buyer=None,
                    material=None, supplier=None, suppliers: pd.DataFrame | None = None) -> dict:
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
        "selected": {"commodity": commodity, "buyer": buyer, "material": material, "supplier": supplier},
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
