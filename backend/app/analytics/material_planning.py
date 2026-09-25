"""Material Planning — per-material stock-health & net-requirement report.

Compares each material's latest on-hand stock against its safety / refill /
max levels and this month's demand (M1), then rolls a standard MRP
net-requirement / balance calculation forward through M2-M4: each month's
Forecast (what to procure to still hold safety stock) and Bal (the
resulting projected closing stock, carried into the next month).
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.common import (
    allowed_codes,
    apply_search,
    filter_codes,
    filter_supplier,
    latest_inventory_stock,
    latest_open_pos,
    latest_warehouse_stock,
    materials_df,
    qty_by_material,
    safe_round,
    supplier_material_codes,
)
from app.models import Movement

WORKING_DAYS_PER_MONTH = 20
# Goods-movement types that make up "incoming receipts" (mirrors overview.py):
#   101 Goods Receipt - Purchase Order          (+)
#   102 Reversal of Goods Receipt               (−)
#   501 Return to Vendor / rejection to supplier (−)
_GR, _GR_REVERSAL, _RETURN_VENDOR = "101", "102", "501"
# Worst-first, matching the severity a planner should look at first.
STATUS_ORDER = ["Stockout", "Risk", "Alarm", "Safe", "Excess"]
# (label, demand column) for M1..M4 — the material master carries these as
# raw monthly-demand columns (demand = M1, demand_2..4 = M2..M4).
MONTHS = [("M1", "demand"), ("M2", "demand_2"), ("M3", "demand_3"), ("M4", "demand_4")]


def _status(current_stock: float, safety_stock: float, refill_level: float, max_level: float) -> str:
    if current_stock <= 0:
        return "Stockout"
    if current_stock < safety_stock:
        return "Risk"
    if refill_level and current_stock < refill_level:
        return "Alarm"
    if max_level and current_stock > max_level:
        return "Excess"
    return "Safe"


def _receipts_qty_by_material(db: Session, stock_date: str | None) -> dict:
    """Net incoming receipts qty per material for the month containing
    ``stock_date`` (or today, if not given), up through that exact date —
    GR minus reversals-of-GR minus returns-to-vendor, same definition the
    Dashboard's incoming-receipts KPI uses. Empty until a movements dump is
    loaded.
    """
    from app.analytics.common import _MODEL_BY_NAME
    if "movements" not in _MODEL_BY_NAME:
        return {}
    if db.execute(select(func.count()).select_from(Movement)).scalar() == 0:
        return {}

    end = pd.Timestamp(stock_date) if stock_date else pd.Timestamp(date.today())
    start = end.replace(day=1)
    stmt = (
        select(Movement.material_code, Movement.mvt, func.sum(Movement.qty))
        .where(
            Movement.movement_date >= start.date(),
            Movement.movement_date <= end.date(),
            Movement.mvt.in_([_GR, _GR_REVERSAL, _RETURN_VENDOR]),
        )
        .group_by(Movement.material_code, Movement.mvt)
    )
    receipts: dict[str, float] = {}
    for code, mvt, qty in db.execute(stmt).all():
        qty = float(qty or 0.0)
        contrib = qty if mvt == _GR else -qty
        receipts[code] = receipts.get(code, 0.0) + contrib
    return receipts


def analyze(db: Session, *, as_of: date | None = None, stock_date: str | None = None,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None,
            location: str | None = None, q: str | None = None) -> dict:
    materials = materials_df(db)
    if materials.empty:
        return _empty(as_of)

    codes = allowed_codes(materials, commodity, buyer, material)
    sup_codes = supplier_material_codes(db, supplier)
    if sup_codes is not None:
        codes = sup_codes if codes is None else (codes & sup_codes)
    base = apply_search(filter_codes(materials, codes), q, ["material_code", "description"])
    if base.empty:
        return {
            "as_of": (as_of or date.today()).isoformat(),
            "empty": False,
            "kpis": {"materials": 0, **{s.lower(): 0 for s in STATUS_ORDER}},
            "rows": [],
        }

    cols = ["material_code", "description", "safety_stock", "refill_level", "max_level"] + [c for _, c in MONTHS]
    base = base[cols].copy()
    for c in cols[2:]:
        base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0.0)

    inv = latest_inventory_stock(db, as_of=stock_date)
    resolved_as_of = (as_of or date.today()).isoformat()
    if not inv.empty and "snapshot_date" in inv and inv["snapshot_date"].notna().any():
        resolved_as_of = str(pd.to_datetime(inv["snapshot_date"]).max().date())
    base["current_stock"] = base["material_code"].map(qty_by_material(inv)).fillna(0.0)

    wh = latest_warehouse_stock(db, as_of=stock_date)
    if location and "warehouse_code" in wh:
        wh = wh[wh["warehouse_code"] == location]
    base["warehouse_stock"] = base["material_code"].map(qty_by_material(wh)).fillna(0.0)

    base["receipts"] = base["material_code"].map(_receipts_qty_by_material(db, stock_date)).fillna(0.0)

    pos = filter_supplier(filter_codes(latest_open_pos(db, as_of=stock_date), codes), supplier)
    if not pos.empty:
        pos = pos.copy()
        pos["order_qty"] = pd.to_numeric(pos.get("order_qty"), errors="coerce").fillna(0.0)
        pos["received_qty"] = pd.to_numeric(pos.get("received_qty"), errors="coerce").fillna(0.0)
        pos["open_qty"] = pd.to_numeric(pos.get("open_qty"), errors="coerce").fillna(
            (pos["order_qty"] - pos["received_qty"]).clip(lower=0)
        )
        open_po = pos.groupby("material_code")["open_qty"].sum()
    else:
        open_po = pd.Series(dtype=float)
    base["open_po"] = base["material_code"].map(open_po).fillna(0.0)

    base["status"] = [
        _status(cs, ss, rl, ml)
        for cs, ss, rl, ml in zip(base["current_stock"], base["safety_stock"], base["refill_level"], base["max_level"])
    ]

    daily_demand = base["demand"] / WORKING_DAYS_PER_MONTH
    base["reach_days"] = np.where(daily_demand > 0, base["current_stock"] / daily_demand, np.nan)

    # Roll M1..M4 forward as a net-requirement / balance rollup:
    #   Forecast[n] = max(0, Demand[n] + Safety - Bal[n-1])       (Bal[0] = current stock)
    #   Bal[n]      = (Forecast[n] + Bal[n-1]) - (Demand[n] + Safety)
    # Forecast is what to procure that month to still hold safety stock by
    # its end (floored at 0 — you can't procure a negative amount); Bal
    # feeds the next month in place of "current stock".
    balance = base["current_stock"]
    monthly = {}
    for label, col in MONTHS:
        demand = base[col]
        forecast = (demand + base["safety_stock"] - balance).clip(lower=0)
        bal = (forecast + balance) - (demand + base["safety_stock"])
        monthly[label] = (demand, forecast, bal)
        balance = bal

    status_rank = {s: i for i, s in enumerate(STATUS_ORDER)}
    base["_rank"] = base["status"].map(status_rank)
    base = base.sort_values(["_rank", "material_code"])

    rows = []
    for idx, r in base.iterrows():
        row = {
            "material_code": r["material_code"],
            "description": r.get("description"),
            "safety_stock": safe_round(r["safety_stock"]),
            "current_stock": safe_round(r["current_stock"]),
            "warehouse_stock": safe_round(r["warehouse_stock"]),
            "receipts": safe_round(r["receipts"]),
            "reach_days": None if pd.isna(r["reach_days"]) else safe_round(r["reach_days"], 1),
            "status": r["status"],
            "open_po": safe_round(r["open_po"]),
        }
        for label, _ in MONTHS:
            demand, forecast, bal = monthly[label]
            row[f"{label.lower()}_demand"] = safe_round(demand[idx])
            row[f"{label.lower()}_forecast"] = safe_round(forecast[idx])
            row[f"{label.lower()}_bal"] = safe_round(bal[idx])
        rows.append(row)

    counts = base["status"].value_counts().to_dict()
    return {
        "as_of": resolved_as_of,
        "empty": False,
        "kpis": {
            "materials": int(len(base)),
            **{s.lower(): int(counts.get(s, 0)) for s in STATUS_ORDER},
        },
        "rows": rows,
    }


def _empty(as_of: date | None) -> dict:
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": True,
        "message": "Load the material master (with safety/refill/max levels and demand) to run planning.",
        "kpis": {"materials": 0, **{s.lower(): 0 for s in STATUS_ORDER}},
        "rows": [],
    }
