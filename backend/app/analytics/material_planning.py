"""Material Planning (MRP-style net requirements).

Nets demand against on-hand stock plus scheduled receipts (open POs) and each
material's safety stock, flagging shortages, excess and coverage.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.analytics.common import materials_df, latest_open_pos, load_df, safe_round, stock_by_material, today
from sqlalchemy.orm import Session


def analyze(db: Session, *, as_of: date | None = None, top_n: int = 20,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None,
            location: str | None = None, q: str | None = None) -> dict:
    from app.analytics.common import allowed_codes, apply_search, filter_codes, filter_options, filter_supplier, location_options
    materials = materials_df(db)
    stock = load_df(db, "stock")
    warehouse_stock = load_df(db, "warehouse_stock")
    pos = latest_open_pos(db)
    demand = load_df(db, "demand")
    now = today(as_of)
    opts = filter_options(materials, commodity, buyer, material, supplier, location,
                          suppliers=load_df(db, "suppliers"),
                          locations=location_options(warehouse_stock))

    if materials.empty and stock.empty and demand.empty:
        return {**_empty(as_of), "filters": opts}

    materials_loaded = not materials.empty  # before filtering, to distinguish "no master" from "filtered to zero"
    codes = allowed_codes(materials, commodity, buyer, material)
    materials = apply_search(filter_codes(materials, codes), q, ["material_code", "description"])
    stock = filter_codes(stock, codes)
    pos = filter_supplier(filter_codes(pos, codes), supplier)
    demand = filter_codes(demand, codes)

    base = _material_base(materials, stock, warehouse_stock, location, materials_loaded)

    # Scheduled receipts (incoming open qty).
    if not pos.empty:
        pos["order_qty"] = pd.to_numeric(pos["order_qty"], errors="coerce").fillna(0)
        pos["received_qty"] = pd.to_numeric(pos["received_qty"], errors="coerce").fillna(0)
        pos["open_qty"] = pd.to_numeric(pos["open_qty"], errors="coerce").fillna(
            (pos["order_qty"] - pos["received_qty"]).clip(lower=0)
        )
        incoming = pos.groupby("material_code")["open_qty"].sum()
    else:
        incoming = pd.Series(dtype=float)
    base["incoming"] = base["material_code"].map(incoming).fillna(0.0)

    # Total demand + daily rate for coverage.
    horizon_days = 90
    if not demand.empty:
        demand["qty"] = pd.to_numeric(demand["qty"], errors="coerce").fillna(0)
        total_demand = demand.groupby("material_code")["qty"].sum()
    else:
        total_demand = pd.Series(dtype=float)
    base["demand"] = base["material_code"].map(total_demand).fillna(0.0)
    base["daily_demand"] = base["demand"] / horizon_days

    # Net requirement = demand + safety - (on_hand + incoming)
    base["available"] = base["on_hand"] + base["incoming"]
    base["net_requirement"] = (
        base["demand"] + base["safety_stock"] - base["available"]
    ).clip(lower=0)
    base["projected_balance"] = base["available"] - base["demand"]
    base["coverage_days"] = np.where(
        base["daily_demand"] > 0, base["on_hand"] / base["daily_demand"], np.nan
    )

    # Suggested order respecting MOQ.
    base["suggested_order"] = np.where(
        base["net_requirement"] > 0,
        np.maximum(base["net_requirement"], base["min_order_qty"]),
        0.0,
    )
    base["order_value"] = base["suggested_order"] * base["unit_cost"]

    def flag(row):
        if row["net_requirement"] > 0:
            return "shortage"
        if row["demand"] > 0 and row["projected_balance"] > 2 * max(row["safety_stock"], row["demand"]):
            return "excess"
        return "ok"

    base["status"] = base.apply(flag, axis=1)

    shortages = base[base["status"] == "shortage"].sort_values("order_value", ascending=False)
    excess = base[base["status"] == "excess"].sort_values("projected_balance", ascending=False)

    kpis = {
        "materials_planned": int(len(base)),
        "shortage_items": int((base["status"] == "shortage").sum()),
        "excess_items": int((base["status"] == "excess").sum()),
        "total_shortage_qty": safe_round(base["net_requirement"].sum()),
        "suggested_order_value": safe_round(base["order_value"].sum()),
        "at_or_below_rop": int((base["available"] <= base["reorder_point"]).sum()),
    }
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": False,
        "filters": opts,
        "kpis": kpis,
        "shortages": _rows(shortages.head(top_n)),
        "excess": _rows(excess.head(top_n)),
        "reorder_alerts": _rows(
            base[base["available"] <= base["reorder_point"]].sort_values("available").head(top_n)
        ),
    }


def _material_base(materials: pd.DataFrame, stock: pd.DataFrame,
                    warehouse_stock: pd.DataFrame | None = None,
                    location: str | None = None, materials_loaded: bool = True) -> pd.DataFrame:
    if materials_loaded:
        base = materials[
            ["material_code", "description", "category", "unit_cost",
             "safety_stock", "reorder_point", "min_order_qty"]
        ].copy()
    else:
        codes = stock["material_code"].unique() if not stock.empty else []
        base = pd.DataFrame({"material_code": codes})
        for c in ["description", "category"]:
            base[c] = None
        for c in ["unit_cost", "safety_stock", "reorder_point", "min_order_qty"]:
            base[c] = 0.0
    for c in ["unit_cost", "safety_stock", "reorder_point", "min_order_qty"]:
        base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0.0)

    on_hand = stock_by_material(stock, warehouse_stock if warehouse_stock is not None else pd.DataFrame(), location)
    base["on_hand"] = base["material_code"].map(on_hand).fillna(0.0)
    return base


def _rows(df: pd.DataFrame) -> list[dict]:
    out = []
    for _, r in df.iterrows():
        cov = r.get("coverage_days")
        out.append(
            {
                "material_code": r["material_code"],
                "description": r.get("description"),
                "category": r.get("category"),
                "on_hand": safe_round(r["on_hand"]),
                "incoming": safe_round(r["incoming"]),
                "demand": safe_round(r["demand"]),
                "safety_stock": safe_round(r["safety_stock"]),
                "net_requirement": safe_round(r["net_requirement"]),
                "projected_balance": safe_round(r["projected_balance"]),
                "coverage_days": None if cov is None or pd.isna(cov) else safe_round(cov, 1),
                "suggested_order": safe_round(r["suggested_order"]),
                "order_value": safe_round(r["order_value"]),
                "status": r["status"],
            }
        )
    return out


def _empty(as_of: date | None) -> dict:
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": True,
        "message": "Load material master, stock and demand dumps to run planning.",
        "kpis": {
            "materials_planned": 0,
            "shortage_items": 0,
            "excess_items": 0,
            "total_shortage_qty": 0.0,
            "suggested_order_value": 0.0,
            "at_or_below_rop": 0,
        },
        "shortages": [],
        "excess": [],
        "reorder_alerts": [],
    }
