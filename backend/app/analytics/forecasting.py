"""Forecasting — rolling M1/M2/M3 forecast vs current supply position."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.analytics.common import (
    allowed_codes, apply_search, filter_codes, filter_options, load_df, safe_round,
    stock_by_material,
)
from sqlalchemy.orm import Session


def analyze(db: Session, *, as_of: date | None = None,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None,
            location: str | None = None, q: str | None = None, top_n: int = 30) -> dict:
    fc = load_df(db, "forecast")
    materials = load_df(db, "materials")
    stock = load_df(db, "stock")
    warehouse_stock = load_df(db, "warehouse_stock")
    pos = load_df(db, "open_pos")
    opts = filter_options(materials, commodity, buyer, material, supplier, location,
                          suppliers=load_df(db, "suppliers"))

    if fc.empty:
        return _empty(as_of, opts)

    fc = fc.copy()
    for c in ("m1_qty", "m2_qty", "m3_qty"):
        fc[c] = pd.to_numeric(fc[c], errors="coerce").fillna(0.0)
    fc["total_3m"] = fc["m1_qty"] + fc["m2_qty"] + fc["m3_qty"]

    codes = allowed_codes(materials, commodity, buyer, material)
    fc = filter_codes(fc, codes)

    if not materials.empty:
        fc = fc.merge(materials[["material_code", "description", "commodity", "buyer", "unit_cost"]],
                      on="material_code", how="left")
    for c in ("commodity", "buyer"):
        if c not in fc:
            fc[c] = "Unassigned"
        fc[c] = fc[c].fillna("Unassigned")
    fc["unit_cost"] = pd.to_numeric(fc.get("unit_cost"), errors="coerce").fillna(0.0)
    fc = apply_search(fc, q, ["material_code", "description"])

    fc["stock"] = fc["material_code"].map(stock_by_material(stock, warehouse_stock, location)).fillna(0.0)
    fc["incoming"] = fc["material_code"].map(_open_po(pos)).fillna(0.0)
    fc["available"] = fc["stock"] + fc["incoming"]
    fc["gap_3m"] = (fc["total_3m"] - fc["available"]).clip(lower=0)
    fc["forecast_value"] = fc["total_3m"] * fc["unit_cost"]
    fc["status"] = np.where(fc["gap_3m"] > 0, "short",
                    np.where(fc["available"] > fc["total_3m"] * 1.5, "excess", "ok"))

    kpis = {
        "materials": int(len(fc)),
        "m1_qty": safe_round(fc["m1_qty"].sum()),
        "m2_qty": safe_round(fc["m2_qty"].sum()),
        "m3_qty": safe_round(fc["m3_qty"].sum()),
        "forecast_value_3m": safe_round(fc["forecast_value"].sum()),
        "short_items": int((fc["status"] == "short").sum()),
    }
    monthly = [
        {"label": "M1", "value": kpis["m1_qty"]},
        {"label": "M2", "value": kpis["m2_qty"]},
        {"label": "M3", "value": kpis["m3_qty"]},
    ]
    by_commodity = (fc.groupby("commodity")["total_3m"].sum().sort_values(ascending=False)
                    .head(top_n).reset_index())
    rows = fc.sort_values("gap_3m", ascending=False).head(top_n)
    return {
        "as_of": (as_of or date.today()).isoformat(), "empty": False, "filters": opts,
        "kpis": kpis, "monthly": monthly,
        "by_commodity": [{"name": r["commodity"], "value": safe_round(r["total_3m"])} for _, r in by_commodity.iterrows()],
        "rows": [{
            "material_code": r["material_code"], "description": r.get("description"),
            "commodity": r["commodity"], "buyer": r["buyer"],
            "stock": safe_round(r["stock"]), "incoming": safe_round(r["incoming"]),
            "m1_qty": safe_round(r["m1_qty"]), "m2_qty": safe_round(r["m2_qty"]), "m3_qty": safe_round(r["m3_qty"]),
            "total_3m": safe_round(r["total_3m"]), "gap_3m": safe_round(r["gap_3m"]), "status": r["status"],
        } for _, r in rows.iterrows()],
    }


def _open_po(pos):
    if pos.empty:
        return {}
    pos = pos.copy()
    for c in ("order_qty", "received_qty", "open_qty"):
        pos[c] = pd.to_numeric(pos.get(c), errors="coerce")
    pos["open_qty"] = pos["open_qty"].fillna((pos["order_qty"].fillna(0) - pos["received_qty"].fillna(0)).clip(lower=0))
    return pos.groupby("material_code")["open_qty"].sum().to_dict()


def _empty(as_of, opts):
    return {"as_of": (as_of or date.today()).isoformat(), "empty": True,
            "message": "Load the Forecast (M1/M2/M3) dump to run forecasting.",
            "filters": opts,
            "kpis": {"materials": 0, "m1_qty": 0.0, "m2_qty": 0.0, "m3_qty": 0.0, "forecast_value_3m": 0.0, "short_items": 0},
            "monthly": [], "by_commodity": [], "rows": []}
