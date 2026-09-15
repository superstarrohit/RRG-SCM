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
