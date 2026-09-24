"""Overall SCM dashboard.

A focused executive summary: today's inventory value and this month's incoming
receipts value, supplier and material counts, and buyer-wise breakdowns of
inventory value and incoming value.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.common import (
    allowed_codes,
    apply_search,
    filter_options,
    location_options_db,
    materials_df,
    safe_round,
    supplier_material_codes,
    supplier_options_db,
)
from app.models import InventorySnapshot, SOBMaster


def _apply_supplier(db: Session, codes, supplier):
    """Intersect the current code set with the vendor's materials (SOB master)."""
    sup = supplier_material_codes(db, supplier)
    if sup is None:
        return codes
    return sup if codes is None else (codes & sup)


def analyze(db: Session, *, as_of: date | None = None,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None,
            location: str | None = None, q: str | None = None) -> dict:
    materials = materials_df(db)
    opts = filter_options(materials, commodity, buyer, material, supplier, location,
                          suppliers=supplier_options_db(db),
                          locations=location_options_db(db))

    # The material set the dashboard's inventory figures are scoped to.
    codes = allowed_codes(materials, commodity, buyer, material)
    codes = _apply_supplier(db, codes, supplier)
    has_filter = codes is not None or bool(q)
    fmats = apply_search(
        materials if codes is None else materials[materials["material_code"].isin(codes)],
        q, ["material_code", "description"],
    )
    allowed = set(fmats["material_code"]) if not fmats.empty else set()
    buyer_of = dict(zip(fmats.get("material_code", []), fmats.get("buyer", []))) if not fmats.empty else {}

    # --- Inventory value as on today: sum of value at the latest snapshot in
    # the daily stock table, scoped to the filtered materials / location. ---
    inv_total, inv_by_buyer = _inventory_today(db, allowed, buyer_of, location, has_filter=has_filter)

    # --- Incoming receipts value (this month) from goods movements: GR +
    # reversal of GR + return-to-vendor. Needs a movements transactions table,
    # which isn't loaded yet — 0 / empty until it is. ---
    incoming_total, incoming_by_buyer, incoming_pending = _incoming_receipts(db, allowed, buyer_of, as_of)

    # Buyer-wise trends for the ribbon charts (last 12 months).
    inventory_ribbon = _inventory_ribbon(db, allowed, buyer_of, location,
                                         has_filter=has_filter)

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


def _month_end(y: int, m: int) -> date:
    return (date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1))


def _bucket(d: date, grain: str):
    """(sort_key, display_label, period_start, period_end) for a date."""
    if grain == "weekly":
        y, w, _ = d.isocalendar()
        monday = date.fromisocalendar(y, w, 1)
        return f"{y}-W{w:02d}", f"W{w:02d} {y}", monday, monday + timedelta(days=6)
    if grain == "monthly":
        return (d.strftime("%Y-%m"), d.strftime("%b %Y"),
                date(d.year, d.month, 1), _month_end(d.year, d.month))
    if grain == "quarterly":
        qtr = (d.month - 1) // 3 + 1
        sm = (qtr - 1) * 3 + 1
        return (f"{d.year}-Q{qtr}", f"Q{qtr} {d.year}",
                date(d.year, sm, 1), _month_end(d.year, sm + 2))
    if grain == "yearly":
        return f"{d.year}", str(d.year), date(d.year, 1, 1), date(d.year, 12, 31)
    # daily (default)
    return d.isoformat(), d.strftime("%d %b %Y"), d, d


def inventory_timeseries(db: Session, *, grain: str = "monthly",
                         start: str | None = None, end: str | None = None,
                         commodity: str | None = None, buyer: str | None = None,
                         material: str | None = None, supplier: str | None = None,
                         location: str | None = None, q: str | None = None) -> dict:
    """Inventory value over time at daily / weekly / monthly / quarterly / yearly
    granularity, scoped to the active slicers and an optional date window.

    Inventory is a stock, so each period is represented by its *last* daily
    snapshot (period-end inventory), not a sum across the period. `start`/`end`
    bound the window — used to drill a parent period into its child periods.
    """
    grain = grain if grain in {"daily", "weekly", "monthly", "quarterly", "yearly"} else "monthly"
    materials = materials_df(db)
    codes = allowed_codes(materials, commodity, buyer, material)
    codes = _apply_supplier(db, codes, supplier)
    fmats = apply_search(
        materials if codes is None else materials[materials["material_code"].isin(codes)],
        q, ["material_code", "description"],
    )
    has_filter = codes is not None or bool(q)
    allowed = set(fmats["material_code"]) if not fmats.empty else set()

    stmt = select(InventorySnapshot.snapshot_date, func.sum(InventorySnapshot.value))
    if location:
        stmt = stmt.where(InventorySnapshot.location == location)
    if start:
        stmt = stmt.where(InventorySnapshot.snapshot_date >= start)
    if end:
        stmt = stmt.where(InventorySnapshot.snapshot_date <= end)
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
        key, label, ps, pe = _bucket(d, grain)
        buckets[key] = {"key": key, "label": label, "date": d.isoformat(),
                        "start": ps.isoformat(), "end": pe.isoformat(),
                        "value": safe_round(val)}
    points = [buckets[k] for k in sorted(buckets)]
    return {"grain": grain, "points": points}


def inventory_ribbon(db: Session, *, grain: str = "yearly",
                     start: str | None = None, end: str | None = None,
                     commodity: str | None = None, buyer: str | None = None,
                     material: str | None = None, supplier: str | None = None,
                     location: str | None = None, q: str | None = None,
                     top_n: int = 8) -> dict:
    """Buyer-wise inventory value over time, drillable Year → Quarter → Month
    (the ribbon-chart counterpart of ``inventory_timeseries``).

    Each period is represented by its last daily-stock snapshot (period-end
    inventory). `start`/`end` bound the window — used to drill a parent period
    (e.g. a year) into its child periods (its quarters).
    """
    grain = grain if grain in {"yearly", "quarterly", "monthly"} else "yearly"
    materials = materials_df(db)
    codes = allowed_codes(materials, commodity, buyer, material)
    codes = _apply_supplier(db, codes, supplier)
    fmats = apply_search(
        materials if codes is None else materials[materials["material_code"].isin(codes)],
        q, ["material_code", "description"],
    )
    has_filter = codes is not None or bool(q)
    allowed = set(fmats["material_code"]) if not fmats.empty else set()
    buyer_of = dict(zip(fmats.get("material_code", []), fmats.get("buyer", []))) if not fmats.empty else {}

    stmt = select(InventorySnapshot.snapshot_date).distinct()
    if start:
        stmt = stmt.where(InventorySnapshot.snapshot_date >= start)
    if end:
        stmt = stmt.where(InventorySnapshot.snapshot_date <= end)
    dates = sorted(_to_date(r[0]) for r in db.execute(stmt).all())
    if not dates:
        return {"grain": grain, "points": [], "series": []}

    # One representative (last) snapshot date per period.
    reps: dict[str, dict] = {}
    for d in dates:                             # ascending, so the last one wins
        key, label, ps, pe = _bucket(d, grain)
        reps[key] = {"key": key, "label": label, "start": ps.isoformat(), "end": pe.isoformat(), "date": d}
    periods = [reps[k] for k in sorted(reps)]

    per_period_by_buyer = []
    for p in periods:
        stmt = select(InventorySnapshot.material_code, func.sum(InventorySnapshot.value)).where(
            InventorySnapshot.snapshot_date == p["date"])
        if location:
            stmt = stmt.where(InventorySnapshot.location == location)
        stmt = stmt.group_by(InventorySnapshot.material_code)
        bb: dict[str, float] = {}
        for code, val in db.execute(stmt).all():
            if has_filter and code not in allowed:
                continue
            b = buyer_of.get(code) or "Unassigned"
            bb[b] = bb.get(b, 0.0) + float(val or 0.0)
        per_period_by_buyer.append(bb)

    buyers = sorted({b for bb in per_period_by_buyer for b in bb},
                    key=lambda b: -sum(bb.get(b, 0.0) for bb in per_period_by_buyer))[:top_n]
    series = [{"name": b, "values": [safe_round(bb.get(b, 0.0)) for bb in per_period_by_buyer]} for b in buyers]
    points = [{"key": p["key"], "label": p["label"], "start": p["start"], "end": p["end"]} for p in periods]
    return {"grain": grain, "points": points, "series": series}


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
    from app.analytics.common import _MODEL_BY_NAME, load_df
    if "movements" not in _MODEL_BY_NAME:
        return 0.0, [], True
    mv = load_df(db, "movements")
    if mv.empty:
        return 0.0, [], True
    # Wired up once the movements schema is known (columns: date, mvt, value,
    # material). Placeholder net-zero handling kept intentionally simple here.
    return 0.0, [], False
