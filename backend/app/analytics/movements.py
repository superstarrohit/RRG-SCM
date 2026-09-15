"""Movements — goods-movement trends by movement type over time."""
from __future__ import annotations

from datetime import date

import pandas as pd

from app.analytics.common import (
    allowed_codes, filter_codes, filter_options, load_df, safe_round,
)
from sqlalchemy.orm import Session


def analyze(db: Session, *, as_of: date | None = None,
            commodity: str | None = None, buyer: str | None = None, top_n: int = 20) -> dict:
    mv = load_df(db, "movements")
    materials = load_df(db, "materials")
    opts = filter_options(materials, commodity, buyer)

    if mv.empty:
        return _empty(as_of, opts)

    mv = mv.copy()
    mv["qty"] = pd.to_numeric(mv["qty"], errors="coerce").fillna(0.0)
    mv["value"] = pd.to_numeric(mv["value"], errors="coerce").fillna(0.0)
    mv["movement_date"] = pd.to_datetime(mv["movement_date"], errors="coerce")
    mv["mvt_type"] = mv["mvt_type"].fillna("Other")

    codes = allowed_codes(materials, commodity, buyer)
    mv = filter_codes(mv, codes)
    if not materials.empty:
        mv = mv.merge(materials[["material_code", "description", "commodity", "buyer"]],
                      on="material_code", how="left", suffixes=("", "_m"))

    by_type = mv.groupby("mvt_type").agg(
        count=("qty", "size"), qty=("qty", "sum"), value=("value", "sum")).sort_values("value", ascending=False)

    dated = mv[mv["movement_date"].notna()]
    trend = (dated.assign(month=dated["movement_date"].dt.to_period("M").dt.to_timestamp())
             .groupby(["month", "mvt_type"])["value"].sum().reset_index())
    months = sorted(trend["month"].unique())
    types = list(by_type.index)
    series = {t: [] for t in types}
    labels = []
    for mth in months:
        labels.append(pd.Timestamp(mth).strftime("%b %y"))
        sub = trend[trend["month"] == mth].set_index("mvt_type")["value"].to_dict()
        for t in types:
            series[t].append(safe_round(sub.get(t, 0.0)))

    inflow = mv[mv["qty"] > 0]["qty"].sum()
    outflow = -mv[mv["qty"] < 0]["qty"].sum()
    kpis = {
        "movements": int(len(mv)),
        "inflow_qty": safe_round(inflow),
        "outflow_qty": safe_round(outflow),
        "net_qty": safe_round(inflow - outflow),
        "movement_types": int(mv["mvt_type"].nunique()),
    }
    return {
        "as_of": (as_of or date.today()).isoformat(), "empty": False, "filters": opts,
        "kpis": kpis,
        "by_type": [{"mvt_type": t, "count": int(r["count"]), "qty": safe_round(r["qty"]),
                     "value": safe_round(r["value"])} for t, r in by_type.iterrows()],
        "trend": {"labels": labels, "series": [{"name": t, "values": series[t]} for t in types]},
        "recent": _recent(mv, top_n),
    }


def _recent(mv, top_n):
    d = mv.sort_values("movement_date", ascending=False).head(top_n)
    out = []
    for _, r in d.iterrows():
        out.append({
            "material_code": r["material_code"], "description": r.get("description"),
            "mvt_type": r["mvt_type"], "movement_desc": r.get("description_m") or r.get("description"),
            "qty": safe_round(r["qty"]), "value": safe_round(r["value"]),
            "movement_date": r["movement_date"].date().isoformat() if pd.notna(r["movement_date"]) else None,
        })
    return out


def _empty(as_of, opts):
    return {"as_of": (as_of or date.today()).isoformat(), "empty": True,
            "message": "Load the Material Movements dump to see movement trends.",
            "filters": opts,
            "kpis": {"movements": 0, "inflow_qty": 0.0, "outflow_qty": 0.0, "net_qty": 0.0, "movement_types": 0},
            "by_type": [], "trend": {"labels": [], "series": []}, "recent": []}
