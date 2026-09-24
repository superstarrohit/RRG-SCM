"""Material Planning — per-material stock-health & shortage report.

Compares each material's latest on-hand stock against its safety / refill /
max levels and this month's demand (M1), then rolls the remaining demand
months (M2-M4) forward against today's stock + open POs, requiring that
safety stock still be on hand at the end of every month.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
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

WORKING_DAYS_PER_MONTH = 20
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


def analyze(db: Session, *, as_of: date | None = None,
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

    inv = latest_inventory_stock(db)
    resolved_as_of = (as_of or date.today()).isoformat()
    if not inv.empty and "snapshot_date" in inv and inv["snapshot_date"].notna().any():
        resolved_as_of = str(pd.to_datetime(inv["snapshot_date"]).max().date())
    base["current_stock"] = base["material_code"].map(qty_by_material(inv)).fillna(0.0)

    wh = latest_warehouse_stock(db)
    if location and "warehouse_code" in wh:
        wh = wh[wh["warehouse_code"] == location]
    base["warehouse_stock"] = base["material_code"].map(qty_by_material(wh)).fillna(0.0)

    pos = filter_supplier(filter_codes(latest_open_pos(db), codes), supplier)
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

    # Roll M1..M4 forward: each month must still leave safety stock on hand
    # at its end, so a month's shortfall is assumed covered (procured up to
    # safety stock) before the next month starts — otherwise a single bad
    # month would cascade into every later one.
    balance = base["current_stock"] + base["open_po"]
    monthly = {}
    for label, col in MONTHS:
        demand = base[col]
        end_balance = balance - demand
        shortage = (base["safety_stock"] - end_balance).clip(lower=0)
        monthly[label] = (demand, shortage)
        balance = end_balance + shortage

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
            "reach_days": None if pd.isna(r["reach_days"]) else safe_round(r["reach_days"], 1),
            "status": r["status"],
            "open_po": safe_round(r["open_po"]),
        }
        for label, _ in MONTHS:
            demand, shortage = monthly[label]
            row[f"{label.lower()}_demand"] = safe_round(demand[idx])
            row[f"{label.lower()}_shortage"] = safe_round(shortage[idx])
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
