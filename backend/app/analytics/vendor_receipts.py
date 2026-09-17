"""Vendor Receipts — inbound receipt (GRN) trends by supplier and commodity."""
from __future__ import annotations

from datetime import date

import pandas as pd

from app.analytics.common import (
    allowed_codes, apply_search, filter_codes, filter_dates, filter_options,
    filter_supplier, load_df, safe_round,
)
from sqlalchemy.orm import Session


def analyze(db: Session, *, as_of: date | None = None,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None,
            location: str | None = None, q: str | None = None,
            start: str | None = None, end: str | None = None, top_n: int = 12) -> dict:
    receipts = load_df(db, "receipts")
    materials = load_df(db, "materials")
    suppliers = load_df(db, "suppliers")
    opts = filter_options(materials, commodity, buyer, material, supplier, location, suppliers=suppliers)

    if receipts.empty:
        return _empty(as_of, opts)

    r = receipts.copy()
    r["qty"] = pd.to_numeric(r["qty"], errors="coerce").fillna(0.0)
    r["unit_price"] = pd.to_numeric(r["unit_price"], errors="coerce").fillna(0.0)
    r["receipt_date"] = pd.to_datetime(r["receipt_date"], errors="coerce")
    r["value"] = r["qty"] * r["unit_price"]

    codes = allowed_codes(materials, commodity, buyer, material)
    r = filter_codes(r, codes)
    r = filter_supplier(r, supplier)
    r = filter_dates(r, "receipt_date", start, end)
    r = apply_search(r, q, ["material_code", "po_number", "receipt_id", "supplier_code"])
    # Receipts aren't location-tagged in this schema — Location is accepted
    # for consistency with the global filter bar but doesn't narrow this page.
    if r.empty:
        return _empty(as_of, opts)
    if not materials.empty:
        m = materials[["material_code", "commodity", "buyer", "description"]]
        r = r.merge(m, on="material_code", how="left")
    if not suppliers.empty and "supplier_code" in r:
        r = r.merge(suppliers[["supplier_code", "name"]].rename(columns={"name": "supplier_name"}),
                    on="supplier_code", how="left")
    if "supplier_name" not in r:
        r["supplier_name"] = None

    dated = r[r["receipt_date"].notna()]
    trend = (dated.assign(month=dated["receipt_date"].dt.to_period("M").dt.to_timestamp())
             .groupby("month").agg(qty=("qty", "sum"), value=("value", "sum")).sort_index())
    timeline = [{"date": d.date().isoformat(), "label": d.strftime("%b %y"),
                 "qty": safe_round(row["qty"]), "value": safe_round(row["value"])}
                for d, row in trend.iterrows()]

    by_sup = (r.groupby("supplier_code").agg(
        supplier_name=("supplier_name", "first"), receipts=("qty", "size"),
        qty=("qty", "sum"), value=("value", "sum")).sort_values("value", ascending=False).head(top_n))
    by_commodity = _grp(r, "commodity", top_n)

    kpis = {
        "total_value": safe_round(r["value"].sum()),
        "total_qty": safe_round(r["qty"].sum()),
        "receipts": int(len(r)),
        "suppliers": int(r["supplier_code"].nunique()) if "supplier_code" in r else 0,
        "materials": int(r["material_code"].nunique()),
    }
    return {
        "as_of": (as_of or date.today()).isoformat(), "empty": False, "filters": opts,
        "kpis": kpis, "timeline": timeline, "by_commodity": by_commodity,
        "by_supplier": [{"supplier_code": c, "supplier_name": row["supplier_name"],
                         "receipts": int(row["receipts"]), "qty": safe_round(row["qty"]),
                         "value": safe_round(row["value"])} for c, row in by_sup.iterrows()],
    }


def _grp(df, key, top_n):
    if df.empty or key not in df:
        return []
    df = df.copy()
    df[key] = df[key].fillna("Unassigned")
    g = df.groupby(key).agg(qty=("qty", "sum"), value=("value", "sum")).sort_values("value", ascending=False).head(top_n)
    return [{"name": k, "qty": safe_round(r["qty"]), "value": safe_round(r["value"])} for k, r in g.iterrows()]


def _empty(as_of, opts):
    return {"as_of": (as_of or date.today()).isoformat(), "empty": True,
            "message": "Load the Goods Receipts (GRN) dump to see vendor receipt trends.",
            "filters": opts,
            "kpis": {"total_value": 0.0, "total_qty": 0.0, "receipts": 0, "suppliers": 0, "materials": 0},
            "timeline": [], "by_commodity": [], "by_supplier": []}
