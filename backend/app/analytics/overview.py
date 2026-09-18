"""Overall SCM dashboard.

A focused executive summary: today's inventory value and this month's incoming
receipts value, supplier and material counts, and buyer-wise breakdowns of
inventory value and incoming value.
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.common import (
    allowed_codes,
    apply_search,
    filter_options,
    load_df,
    location_options_db,
    materials_df,
    safe_round,
)
from app.models import InventorySnapshot, SOBMaster


def analyze(db: Session, *, as_of: date | None = None,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None,
            location: str | None = None, q: str | None = None) -> dict:
    materials = materials_df(db)
    opts = filter_options(materials, commodity, buyer, material, supplier, location,
                          suppliers=load_df(db, "suppliers"),
                          locations=location_options_db(db))

    # The material set the dashboard's inventory figures are scoped to.
    codes = allowed_codes(materials, commodity, buyer, material)
    fmats = apply_search(
        materials if codes is None else materials[materials["material_code"].isin(codes)],
        q, ["material_code", "description"],
    )
    allowed = set(fmats["material_code"]) if not fmats.empty else set()
    buyer_of = dict(zip(fmats.get("material_code", []), fmats.get("buyer", []))) if not fmats.empty else {}

    # --- Inventory value as on today: sum of value at the latest snapshot in
    # the daily stock table, scoped to the filtered materials / location. ---
    inv_total, inv_by_buyer = _inventory_today(db, allowed, buyer_of, location, has_filter=codes is not None or bool(q))

    # --- Incoming receipts value (this month) from goods movements: GR +
    # reversal of GR + return-to-vendor. Needs a movements transactions table,
    # which isn't loaded yet — 0 / empty until it is. ---
    incoming_total, incoming_by_buyer, incoming_pending = _incoming_receipts(db, allowed, buyer_of, as_of)

    # Buyer-wise trends for the ribbon charts (last 12 months).
    inventory_ribbon = _inventory_ribbon(db, allowed, buyer_of, location,
                                         has_filter=codes is not None or bool(q))

    suppliers_count = db.execute(
        select(func.count(func.distinct(SOBMaster.vendor_code)))
    ).scalar() or 0
    materials_count = int(len(fmats))

    return {
        "as_of": (as_of or date.today()).isoformat(),
        "filters": opts,
        "kpis": {
            "inventory_value": safe_round(inv_total),
            "incoming_receipts_value": safe_round(incoming_total),
            "suppliers": int(suppliers_count),
            "materials": materials_count,
        },
        "inventory_by_buyer": inv_by_buyer,
        "incoming_by_buyer": incoming_by_buyer,
        "inventory_ribbon": inventory_ribbon,
        "incoming_ribbon": {"months": [], "series": []},
        "incoming_pending": incoming_pending,
    }


def _to_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()


def _bucket(d: date, grain: str):
    """(sort_key, display_label) for a date at the requested granularity."""
    if grain == "weekly":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}", f"W{w:02d} {y}"
    if grain == "monthly":
        return d.strftime("%Y-%m"), d.strftime("%b %Y")
    if grain == "quarterly":
        qtr = (d.month - 1) // 3 + 1
        return f"{d.year}-Q{qtr}", f"Q{qtr} {d.year}"
    if grain == "yearly":
        return f"{d.year}", str(d.year)
    # daily (default)
    return d.isoformat(), d.strftime("%d %b %Y")


def inventory_timeseries(db: Session, *, grain: str = "monthly",
                         commodity: str | None = None, buyer: str | None = None,
                         material: str | None = None, supplier: str | None = None,
                         location: str | None = None, q: str | None = None) -> dict:
    """Inventory value over time at daily / weekly / monthly / quarterly / yearly
    granularity, scoped to the active slicers.

    Inventory is a stock, so each period is represented by its *last* daily
    snapshot (period-end inventory), not a sum across the period.
    """
    grain = grain if grain in {"daily", "weekly", "monthly", "quarterly", "yearly"} else "monthly"
    materials = materials_df(db)
    codes = allowed_codes(materials, commodity, buyer, material)
    fmats = apply_search(
        materials if codes is None else materials[materials["material_code"].isin(codes)],
        q, ["material_code", "description"],
    )
    has_filter = codes is not None or bool(q)
    allowed = set(fmats["material_code"]) if not fmats.empty else set()

    stmt = select(InventorySnapshot.snapshot_date, func.sum(InventorySnapshot.value))
    if location:
        stmt = stmt.where(InventorySnapshot.location == location)
    if has_filter:
        if not allowed:
            return {"grain": grain, "points": []}
        stmt = stmt.where(InventorySnapshot.material_code.in_(allowed))
    stmt = stmt.group_by(InventorySnapshot.snapshot_date).order_by(InventorySnapshot.snapshot_date)

    daily = [(_to_date(row[0]), float(row[1] or 0.0)) for row in db.execute(stmt).all()]
    if not daily:
        return {"grain": grain, "points": []}

    # Collapse to one value per period: the latest snapshot within it.
    buckets: dict[str, dict] = {}
    for d, val in daily:                       # daily list is already ascending
        key, label = _bucket(d, grain)
        buckets[key] = {"label": label, "date": d.isoformat(), "value": safe_round(val)}
    points = [buckets[k] for k in sorted(buckets)]
    return {"grain": grain, "points": points}


def _inventory_ribbon(db, allowed: set, buyer_of: dict, location, has_filter: bool, n: int = 12):
    """Buyer-wise inventory value at each month's last snapshot (last n months)."""
    md = db.execute(
        select(func.strftime("%Y-%m", InventorySnapshot.snapshot_date).label("m"),
               func.max(InventorySnapshot.snapshot_date))
        .group_by("m").order_by("m")
    ).all()
    md = md[-n:]
    months, per_month = [], []
    for m, dt in md:
        stmt = select(InventorySnapshot.material_code, func.sum(InventorySnapshot.value)).where(
            InventorySnapshot.snapshot_date == dt)
        if location:
            stmt = stmt.where(InventorySnapshot.location == location)
        stmt = stmt.group_by(InventorySnapshot.material_code)
        bb: dict[str, float] = {}
        for code, val in db.execute(stmt).all():
            if has_filter and code not in allowed:
                continue
            b = buyer_of.get(code) or "Unassigned"
            bb[b] = bb.get(b, 0.0) + float(val or 0.0)
        months.append(m)
        per_month.append(bb)
    buyers = sorted({b for bb in per_month for b in bb},
                    key=lambda b: -sum(bb.get(b, 0.0) for bb in per_month))
    series = [{"name": b, "values": [safe_round(bb.get(b, 0.0)) for bb in per_month]} for b in buyers]
    return {"months": months, "series": series}


def _inventory_today(db, allowed: set, buyer_of: dict, location, has_filter: bool):
    """Total + buyer-wise inventory value at the latest daily-stock date."""
    latest = db.execute(select(func.max(InventorySnapshot.snapshot_date))).scalar()
    if latest is None:
        return 0.0, []
    stmt = select(
        InventorySnapshot.material_code, func.sum(InventorySnapshot.value)
    ).where(InventorySnapshot.snapshot_date == latest)
    if location:
        stmt = stmt.where(InventorySnapshot.location == location)
    stmt = stmt.group_by(InventorySnapshot.material_code)
    rows = db.execute(stmt).all()

    by_buyer: dict[str, float] = {}
    total = 0.0
    for code, val in rows:
        if has_filter and code not in allowed:
            continue
        val = float(val or 0.0)
        total += val
        b = buyer_of.get(code) or "Unassigned"
        by_buyer[b] = by_buyer.get(b, 0.0) + val
    donut = [
        {"name": b, "value": safe_round(v)}
        for b, v in sorted(by_buyer.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return total, donut


# Goods-movement types that make up "incoming receipts" (from movement_master):
#   101 Goods Receipt - Purchase Order         (+)
#   102 Reversal of Goods Receipt              (−)
#   501 Return to Vendor / rejection to supplier (−)
_GR, _GR_REVERSAL, _RETURN_VENDOR = "101", "102", "501"


def _incoming_receipts(db, allowed: set, buyer_of: dict, as_of):
    """Net incoming receipts value for the current month, by buyer.

    GR minus reversals-of-GR minus returns-to-vendor. Sourced from a movements
    transactions table; returns (0, [], pending=True) until one is loaded.
    """
    from app.analytics.common import _MODEL_BY_NAME
    if "movements" not in _MODEL_BY_NAME:
        return 0.0, [], True
    mv = load_df(db, "movements")
    if mv.empty:
        return 0.0, [], True
    # Wired up once the movements schema is known (columns: date, mvt, value,
    # material). Placeholder net-zero handling kept intentionally simple here.
    return 0.0, [], False
