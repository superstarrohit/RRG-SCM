"""Stock Monitoring — stock health & stockout-risk per material.

Compares current stock (sap_stock) against safety / refill / max levels plus
incoming open POs and demand, and classifies each material's risk:
stockout, critical, low, healthy or overstocked.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.analytics.common import latest_warehouse_stock, materials_df, latest_open_pos, load_df, safe_round, stock_by_material, today
from sqlalchemy.orm import Session

STATUS_ORDER = ["stockout", "critical", "low", "healthy", "overstock"]
STATUS_LABEL = {
    "stockout": "Stockout", "critical": "Critical (< safety)",
    "low": "Low (< refill)", "healthy": "Healthy", "overstock": "Overstock (> max)",
}


def analyze(
    db: Session, *, as_of: date | None = None,
    commodity: str | None = None, buyer: str | None = None,
    material: str | None = None, supplier: str | None = None,
    location: str | None = None, q: str | None = None, top_n: int = 25,
) -> dict:
    from app.analytics.common import apply_search, filter_supplier
    materials = materials_df(db)
    stock = load_df(db, "stock")
    warehouse_stock = latest_warehouse_stock(db)
    pos = latest_open_pos(db)
    demand = load_df(db, "demand")
    now = today(as_of)

    if materials.empty:
        return _empty(as_of)

    pos = filter_supplier(pos, supplier)

    base = materials[[
        "material_code", "description", "commodity", "buyer", "unit_cost",
        "safety_stock", "refill_level", "max_level",
    ]].copy()
    for c in ("unit_cost", "safety_stock", "refill_level", "max_level"):
        base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0.0)
    base["commodity"] = base["commodity"].fillna("Unassigned")
    base["buyer"] = base["buyer"].fillna("Unassigned")

    if commodity:
        base = base[base["commodity"] == commodity]
    if buyer:
        base = base[base["buyer"] == buyer]
    if material:
        base = base[base["material_code"] == material]
    base = apply_search(base, q, ["material_code", "description"])

    # A Location selection sources stock from that warehouse instead of the
    # company-wide total, so the slicer genuinely changes the figures.
    base["sap_stock"] = base["material_code"].map(stock_by_material(stock, warehouse_stock, location)).fillna(0.0)
    base["open_po"] = base["material_code"].map(_open_po(pos)).fillna(0.0)
    base["demand"] = base["material_code"].map(_sum(demand, "material_code", "qty")).fillna(0.0)
    base["projected"] = base["sap_stock"] + base["open_po"] - base["demand"]
    base["stock_value"] = base["sap_stock"] * base["unit_cost"]
    daily = base["demand"] / 90.0
    base["cover_days"] = np.where(daily > 0, base["sap_stock"] / daily, np.nan)

    def classify(r):
        if r["sap_stock"] <= 0:
            return "stockout"
        if r["sap_stock"] < r["safety_stock"]:
            return "critical"
        if r["refill_level"] and r["sap_stock"] < r["refill_level"]:
            return "low"
        if r["max_level"] and r["sap_stock"] > r["max_level"]:
            return "overstock"
        return "healthy"

    base["status"] = base.apply(classify, axis=1)
    # stockout risk also flags items whose projected balance goes negative.
    base["at_risk"] = (base["status"].isin(["stockout", "critical", "low"])) | (base["projected"] < 0)

    counts = base["status"].value_counts().to_dict()
    kpis = {
        "materials": int(len(base)),
        "stockout": int(counts.get("stockout", 0)),
        "critical": int(counts.get("critical", 0)),
        "low": int(counts.get("low", 0)),
        "overstock": int(counts.get("overstock", 0)),
        "at_risk": int(base["at_risk"].sum()),
        "stock_value": safe_round(base["stock_value"].sum()),
    }
    dist = [
        {"status": s, "label": STATUS_LABEL[s], "count": int(counts.get(s, 0))}
        for s in STATUS_ORDER if counts.get(s, 0)
    ]

    risk = base[base["at_risk"]].sort_values(["status", "stock_value"], ascending=[True, False])
    from app.analytics.common import filter_options, location_options
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": False,
        "filters": filter_options(materials, commodity, buyer, material, supplier, location,
                                  suppliers=load_df(db, "suppliers"),
                                  locations=location_options(warehouse_stock)),
        "kpis": kpis,
        "status_distribution": dist,
        "risk_items": _rows(risk.head(top_n)),
        "all_items": _rows(base.sort_values("stock_value", ascending=False).head(top_n)),
    }


def _open_po(pos: pd.DataFrame):
    if pos.empty:
        return {}
    pos = pos.copy()
    for c in ("order_qty", "received_qty", "open_qty"):
        pos[c] = pd.to_numeric(pos.get(c), errors="coerce")
    pos["open_qty"] = pos["open_qty"].fillna((pos["order_qty"].fillna(0) - pos["received_qty"].fillna(0)).clip(lower=0))
    return pos.groupby("material_code")["open_qty"].sum().to_dict()


def _sum(df, key, val):
    if df.empty or val not in df:
        return {}
    df = df.copy()
    df[val] = pd.to_numeric(df[val], errors="coerce").fillna(0)
    return df.groupby(key)[val].sum().to_dict()


def _rows(df: pd.DataFrame) -> list[dict]:
    out = []
    for _, r in df.iterrows():
        cov = r["cover_days"]
        out.append({
            "material_code": r["material_code"],
            "description": r.get("description"),
            "commodity": r.get("commodity"),
            "buyer": r.get("buyer"),
            "sap_stock": safe_round(r["sap_stock"]),
            "safety_stock": safe_round(r["safety_stock"]),
            "refill_level": safe_round(r["refill_level"]),
            "max_level": safe_round(r["max_level"]),
            "open_po": safe_round(r["open_po"]),
            "demand": safe_round(r["demand"]),
            "projected": safe_round(r["projected"]),
            "cover_days": None if pd.isna(cov) else safe_round(cov, 1),
            "stock_value": safe_round(r["stock_value"]),
            "status": r["status"],
        })
    return out


def _empty(as_of):
    return {
        "as_of": (as_of or date.today()).isoformat(), "empty": True,
        "message": "Load material master (with safety/refill/max levels) and stock to monitor stock health.",
        "filters": {"commodity": [], "buyer": [], "material": [], "supplier": [], "location": [],
                   "selected": {"commodity": None, "buyer": None, "material": None, "supplier": None, "location": None}},
        "kpis": {"materials": 0, "stockout": 0, "critical": 0, "low": 0, "overstock": 0, "at_risk": 0, "stock_value": 0.0},
        "status_distribution": [], "risk_items": [], "all_items": [],
    }
