"""Sourcing analysis.

Supplier spend, on-time performance (from receipts vs PO expected dates),
price benchmarking per material, and single-source risk.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.analytics.common import load_df, safe_round
from sqlalchemy.orm import Session


def analyze(db: Session, *, as_of: date | None = None, top_n: int = 20,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None,
            location: str | None = None, q: str | None = None) -> dict:
    from app.analytics.common import allowed_codes, apply_search, filter_codes, filter_options, filter_supplier
    pos = load_df(db, "open_pos")
    receipts = load_df(db, "receipts")
    suppliers = load_df(db, "suppliers")
    materials = load_df(db, "materials")
    opts = filter_options(materials, commodity, buyer, material, supplier, location, suppliers=suppliers)

    codes = allowed_codes(materials, commodity, buyer, material)
    search_cols = ["material_code", "supplier_code"]
    pos = apply_search(filter_supplier(filter_codes(pos, codes), supplier), q, search_cols)
    receipts = apply_search(filter_supplier(filter_codes(receipts, codes), supplier), q, search_cols)
    # No location dimension on POs/receipts in this schema — Location is
    # accepted for consistency with the global filter bar but doesn't narrow
    # this page.

    if pos.empty and receipts.empty:
        return {**_empty(as_of), "filters": opts}

    supplier_names = {}
    if not suppliers.empty:
        supplier_names = suppliers.set_index("supplier_code")["name"].to_dict()

    spend = _supplier_spend(pos, receipts, supplier_names, top_n)
    otif = _on_time(pos, receipts)
    price_bench = _price_benchmark(pos, receipts, top_n)
    single_source = _single_source(pos, receipts, supplier_names)

    kpis = {
        "active_suppliers": int(len(spend)),
        "total_committed_value": safe_round(sum(s["open_value"] for s in spend)),
        "single_source_materials": len(single_source),
        "avg_on_time_pct": safe_round(
            np.mean([o["on_time_pct"] for o in otif]) if otif else 0
        ),
    }
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": False,
        "filters": opts,
        "kpis": kpis,
        "supplier_spend": spend,
        "on_time_performance": otif,
        "price_benchmark": price_bench,
        "single_source_risk": single_source,
    }


def _supplier_spend(pos, receipts, names, top_n) -> list[dict]:
    frames = []
    if not pos.empty and "supplier_code" in pos:
        p = pos.copy()
        p["order_qty"] = pd.to_numeric(p["order_qty"], errors="coerce").fillna(0)
        p["received_qty"] = pd.to_numeric(p["received_qty"], errors="coerce").fillna(0)
        p["open_qty"] = pd.to_numeric(p["open_qty"], errors="coerce").fillna(
            (p["order_qty"] - p["received_qty"]).clip(lower=0)
        )
        p["unit_price"] = pd.to_numeric(p["unit_price"], errors="coerce").fillna(0)
        p["open_value"] = p["open_qty"] * p["unit_price"]
        frames.append(p.groupby("supplier_code").agg(
            open_lines=("open_qty", "size"), open_value=("open_value", "sum")
        ))
    spend = frames[0] if frames else pd.DataFrame(columns=["open_lines", "open_value"])

    if not receipts.empty and "supplier_code" in receipts:
        r = receipts.copy()
        r["qty"] = pd.to_numeric(r["qty"], errors="coerce").fillna(0)
        r["unit_price"] = pd.to_numeric(r["unit_price"], errors="coerce").fillna(0)
        r["value"] = r["qty"] * r["unit_price"]
        received = r.groupby("supplier_code").agg(received_value=("value", "sum"))
        spend = spend.join(received, how="outer")

    spend = spend.fillna(0.0)
    if "received_value" not in spend:
        spend["received_value"] = 0.0
    spend = spend.sort_values("open_value", ascending=False).head(top_n)
    return [
        {
            "supplier_code": code,
            "supplier_name": names.get(code),
            "open_lines": int(r.get("open_lines", 0)),
            "open_value": safe_round(r.get("open_value", 0)),
            "received_value": safe_round(r.get("received_value", 0)),
        }
        for code, r in spend.iterrows()
    ]


def _on_time(pos, receipts) -> list[dict]:
    """On-time = receipt_date <= PO expected_date, matched on PO number."""
    if pos.empty or receipts.empty:
        return []
    if "expected_date" not in pos or "receipt_date" not in receipts:
        return []
    p = pos[["po_number", "supplier_code", "expected_date"]].dropna(subset=["po_number"]).copy()
    p["expected_date"] = pd.to_datetime(p["expected_date"], errors="coerce")
    r = receipts[["po_number", "receipt_date"]].dropna(subset=["po_number"]).copy()
    r["receipt_date"] = pd.to_datetime(r["receipt_date"], errors="coerce")
    merged = r.merge(p, on="po_number", how="inner").dropna(subset=["expected_date", "receipt_date"])
    if merged.empty:
        return []
    merged["on_time"] = merged["receipt_date"] <= merged["expected_date"]
    grp = merged.groupby("supplier_code").agg(
        deliveries=("on_time", "size"), on_time=("on_time", "sum")
    )
    grp["on_time_pct"] = 100 * grp["on_time"] / grp["deliveries"]
    grp = grp.sort_values("deliveries", ascending=False)
    return [
        {
            "supplier_code": code,
            "deliveries": int(r["deliveries"]),
            "on_time": int(r["on_time"]),
            "on_time_pct": safe_round(r["on_time_pct"]),
        }
        for code, r in grp.iterrows()
    ]


def _price_benchmark(pos, receipts, top_n) -> list[dict]:
    """Per material: min/max/avg price across suppliers, and potential saving."""
    frames = []
    for df, qty_col, price_col in [(pos, "open_qty", "unit_price"), (receipts, "qty", "unit_price")]:
        if df.empty or "supplier_code" not in df or price_col not in df:
            continue
        d = df[["material_code", "supplier_code", price_col]].copy()
        d[price_col] = pd.to_numeric(d[price_col], errors="coerce")
        d = d[d[price_col] > 0].rename(columns={price_col: "price"})
        frames.append(d)
    if not frames:
        return []
    allp = pd.concat(frames, ignore_index=True)
    grp = allp.groupby("material_code").agg(
        suppliers=("supplier_code", "nunique"),
        min_price=("price", "min"),
        max_price=("price", "max"),
        avg_price=("price", "mean"),
    )
    grp = grp[grp["suppliers"] > 1]
    grp["spread_pct"] = 100 * (grp["max_price"] - grp["min_price"]) / grp["min_price"]
    grp = grp.sort_values("spread_pct", ascending=False).head(top_n)
    return [
        {
            "material_code": code,
            "suppliers": int(r["suppliers"]),
            "min_price": safe_round(r["min_price"]),
            "max_price": safe_round(r["max_price"]),
            "avg_price": safe_round(r["avg_price"]),
            "spread_pct": safe_round(r["spread_pct"]),
        }
        for code, r in grp.iterrows()
    ]


def _single_source(pos, receipts, names) -> list[dict]:
    frames = []
    for df in (pos, receipts):
        if not df.empty and "supplier_code" in df and "material_code" in df:
            frames.append(df[["material_code", "supplier_code"]].dropna())
    if not frames:
        return []
    allm = pd.concat(frames, ignore_index=True).drop_duplicates()
    counts = allm.groupby("material_code")["supplier_code"].nunique()
    single = counts[counts == 1]
    out = []
    for code in single.index:
        sup = allm[allm["material_code"] == code]["supplier_code"].iloc[0]
        out.append({"material_code": code, "supplier_code": sup, "supplier_name": names.get(sup)})
    return out


def _empty(as_of: date | None) -> dict:
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": True,
        "message": "Load open POs and/or receipts (with suppliers) to run sourcing analysis.",
        "kpis": {
            "active_suppliers": 0,
            "total_committed_value": 0.0,
            "single_source_materials": 0,
            "avg_on_time_pct": 0.0,
        },
        "supplier_spend": [],
        "on_time_performance": [],
        "price_benchmark": [],
        "single_source_risk": [],
    }
