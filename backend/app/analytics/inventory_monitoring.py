"""Inventory Monitoring — stock value & quantity trends over time.

Uses the Inventory History dump (time-series snapshots), enriched with material
master (commodity / buyer), to show how inventory moves period-over-period and
where it concentrates (by commodity, location, buyer).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from app.analytics.common import load_df, safe_round
from sqlalchemy.orm import Session


def analyze(
    db: Session, *, as_of: date | None = None,
    commodity: str | None = None, buyer: str | None = None, top_n: int = 12,
) -> dict:
    snaps = load_df(db, "inventory_snapshots")
    materials = load_df(db, "materials")

    if snaps.empty:
        return _empty(as_of)

    snaps = snaps.copy()
    snaps["qty"] = pd.to_numeric(snaps["qty"], errors="coerce").fillna(0.0)
    snaps["value"] = pd.to_numeric(snaps["value"], errors="coerce").fillna(0.0)
    snaps["snapshot_date"] = pd.to_datetime(snaps["snapshot_date"], errors="coerce")
    snaps = snaps[snaps["snapshot_date"].notna()]

    if not materials.empty:
        m = materials[["material_code", "commodity", "buyer", "description"]].copy()
        m["commodity"] = m["commodity"].fillna("Unassigned")
        m["buyer"] = m["buyer"].fillna("Unassigned")
        snaps = snaps.merge(m, on="material_code", how="left")
    for c in ("commodity", "buyer"):
        if c not in snaps:
            snaps[c] = "Unassigned"
        snaps[c] = snaps[c].fillna("Unassigned")

    filters = {
        "commodity": sorted(snaps["commodity"].dropna().unique().tolist()),
        "buyer": sorted(snaps["buyer"].dropna().unique().tolist()),
        "selected": {"commodity": commodity, "buyer": buyer},
    }
    if commodity:
        snaps = snaps[snaps["commodity"] == commodity]
    if buyer:
        snaps = snaps[snaps["buyer"] == buyer]

    # Trend: total value & qty per snapshot date.
    trend = snaps.groupby("snapshot_date").agg(value=("value", "sum"), qty=("qty", "sum")).sort_index()
    timeline = [
        {"date": d.date().isoformat(), "label": d.strftime("%b %y"),
         "value": safe_round(r["value"]), "qty": safe_round(r["qty"])}
        for d, r in trend.iterrows()
    ]

    # Latest snapshot = current position.
    latest_date = snaps["snapshot_date"].max()
    latest = snaps[snaps["snapshot_date"] == latest_date]
    prev_dates = [d for d in trend.index if d < latest_date]
    prev_value = float(trend.loc[prev_dates[-1], "value"]) if prev_dates else 0.0
    cur_value = float(latest["value"].sum())
    mom = safe_round(100 * (cur_value - prev_value) / prev_value) if prev_value else 0.0

    by_commodity = _group(latest, "commodity", top_n)
    by_location = _group(latest, "location", top_n) if "location" in latest else []
    by_buyer = _group(latest, "buyer", top_n)

    kpis = {
        "inventory_value": safe_round(cur_value),
        "inventory_qty": safe_round(latest["qty"].sum()),
        "materials": int(latest["material_code"].nunique()),
        "locations": int(latest["location"].nunique()) if "location" in latest else 0,
        "commodities": int(latest["commodity"].nunique()),
        "mom_change_pct": mom,
        "as_of_snapshot": latest_date.date().isoformat() if pd.notna(latest_date) else None,
    }
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": False,
        "filters": filters,
        "kpis": kpis,
        "timeline": timeline,
        "by_commodity": by_commodity,
        "by_location": by_location,
        "by_buyer": by_buyer,
    }


def _group(df: pd.DataFrame, key: str, top_n: int) -> list[dict]:
    if df.empty or key not in df:
        return []
    g = df.groupby(key).agg(value=("value", "sum"), qty=("qty", "sum")).sort_values("value", ascending=False).head(top_n)
    return [{"name": k or "Unassigned", "value": safe_round(r["value"]), "qty": safe_round(r["qty"])} for k, r in g.iterrows()]


def _empty(as_of):
    return {
        "as_of": (as_of or date.today()).isoformat(), "empty": True,
        "message": "Load the Inventory History dump (dated stock snapshots) to see inventory trends.",
        "filters": {"commodity": [], "buyer": [], "selected": {"commodity": None, "buyer": None}},
        "kpis": {"inventory_value": 0.0, "inventory_qty": 0.0, "materials": 0, "locations": 0, "commodities": 0, "mom_change_pct": 0.0, "as_of_snapshot": None},
        "timeline": [], "by_commodity": [], "by_location": [], "by_buyer": [],
    }
