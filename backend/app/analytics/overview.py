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
from app.models import InventorySnapshot, Movement, SOBMaster


def _apply_supplier(db: Session, codes, supplier):
    """Intersect the current code set with the vendor's materials (SOB master)."""
    sup = supplier_material_codes(db, supplier)
    if sup is None:
        return codes
    return sup if codes is None else (codes & sup)


def analyze(db: Session, *, as_of: date | None = None,
            start: str | None = None, end: str | None = None,
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
    # the daily stock table, scoped to the filtered materials / location.
    # A "today" figure is a point-in-time snapshot, so the global date-range
    # filter narrows *which* date counts as "today": an explicit as_of wins,
    # else the range's end date, else the true latest snapshot. If the range
    # itself precedes any data (latest resolved date < start), there is
    # nothing to show for that window. ---
    cutoff = as_of.isoformat() if as_of else end
    inv_total, inv_by_buyer, inv_as_of = _inventory_today(
        db, allowed, buyer_of, location, has_filter=has_filter, cutoff=cutoff, start=start)

    # --- Incoming receipts value (this month) from goods movements: GR -
    # reversal of GR - return-to-vendor. ---
    supplier_of = _primary_supplier_of(db)
    incoming_total, incoming_by_buyer, incoming_by_supplier, incoming_pending = _incoming_receipts(
        db, allowed, buyer_of, supplier_of, has_filter, as_of)

    # Buyer-wise trends for the ribbon charts (last 12 months, bounded by the
    # date-range filter when one is active).
    inventory_ribbon = _inventory_ribbon(db, allowed, buyer_of, location,
                                         has_filter=has_filter, start=start, end=cutoff)

    suppliers_count = db.execute(
        select(func.count(func.distinct(SOBMaster.vendor_code)))
    ).scalar() or 0
    materials_count = int(len(fmats))

    resolved_as_of = _to_date(inv_as_of).isoformat() if inv_as_of is not None else (as_of or date.today()).isoformat()

    return {
        "as_of": resolved_as_of,
        "filters": opts,
        "kpis": {
            "inventory_value": safe_round(inv_total),
            "incoming_receipts_value": safe_round(incoming_total),
            "suppliers": int(suppliers_count),
            "materials": materials_count,
        },
        "inventory_by_buyer": inv_by_buyer,
        "incoming_by_buyer": incoming_by_buyer,
        "incoming_by_supplier": incoming_by_supplier,
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


def inventory_timeseries(db: Session, *, grain: str = "monthly", metric: str = "value",
                         start: str | None = None, end: str | None = None,
                         commodity: str | None = None, buyer: str | None = None,
                         material: str | None = None, supplier: str | None = None,
                         location: str | None = None, q: str | None = None) -> dict:
    """Inventory value (or quantity) over time at daily / weekly / monthly /
    quarterly / yearly granularity, scoped to the active slicers and an
    optional date window.

    Inventory is a stock, so each period is represented by its *last* daily
    snapshot (period-end inventory), not a sum across the period. `start`/`end`
    bound the window — used to drill a parent period into its child periods.
    """
    grain = grain if grain in {"daily", "weekly", "monthly", "quarterly", "yearly"} else "monthly"
    metric = metric if metric in {"value", "qty"} else "value"
    col = InventorySnapshot.value if metric == "value" else InventorySnapshot.qty
    materials = materials_df(db)
    codes = allowed_codes(materials, commodity, buyer, material)
    codes = _apply_supplier(db, codes, supplier)
    fmats = apply_search(
        materials if codes is None else materials[materials["material_code"].isin(codes)],
        q, ["material_code", "description"],
    )
    has_filter = codes is not None or bool(q)
    allowed = set(fmats["material_code"]) if not fmats.empty else set()

    stmt = select(InventorySnapshot.snapshot_date, func.sum(col))
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


def incoming_timeseries(db: Session, *, grain: str = "monthly", metric: str = "value",
                        start: str | None = None, end: str | None = None,
                        commodity: str | None = None, buyer: str | None = None,
                        material: str | None = None, supplier: str | None = None,
                        location: str | None = None, q: str | None = None) -> dict:
    """Incoming receipts value (or quantity) over time — the trend counterpart
    of ``inventory_timeseries``, drillable the same way (Year → Quarter →
    Month → Day). Each period is a *sum* of that period's net receipts (GR
    minus reversals-of-GR minus returns-to-vendor), unlike inventory's
    period-end snapshot, since receipts are a flow rather than a stock.

    Returns an empty, pending series until the movements dump is loaded —
    the Dashboard shows an "awaiting movements upload" empty state for it.
    """
    from app.analytics.common import _MODEL_BY_NAME
    grain = grain if grain in {"daily", "weekly", "monthly", "quarterly", "yearly"} else "monthly"
    metric = metric if metric in {"value", "qty"} else "value"
    col = Movement.value if metric == "value" else Movement.qty
    if "movements" not in _MODEL_BY_NAME:
        return {"grain": grain, "points": [], "pending": True}
    if db.execute(select(func.count()).select_from(Movement)).scalar() == 0:
        return {"grain": grain, "points": [], "pending": True}

    materials = materials_df(db)
    codes = allowed_codes(materials, commodity, buyer, material)
    codes = _apply_supplier(db, codes, supplier)
    fmats = apply_search(
        materials if codes is None else materials[materials["material_code"].isin(codes)],
        q, ["material_code", "description"],
    )
    has_filter = codes is not None or bool(q)
    allowed = set(fmats["material_code"]) if not fmats.empty else set()

    stmt = select(Movement.movement_date, Movement.mvt, Movement.material_code, col).where(
        Movement.mvt.in_([_GR, _GR_REVERSAL, _RETURN_VENDOR])
    )
    if start:
        stmt = stmt.where(Movement.movement_date >= start)
    if end:
        stmt = stmt.where(Movement.movement_date <= end)
    rows = db.execute(stmt).all()

    buckets: dict[str, dict] = {}
    for dt, mvt, code, val in rows:
        if has_filter and code not in allowed:
            continue
        d = _to_date(dt)
        key, label, ps, pe = _bucket(d, grain)
        b = buckets.setdefault(
            key, {"key": key, "label": label, "start": ps.isoformat(), "end": pe.isoformat(), "value": 0.0}
        )
        b["value"] += float(val or 0.0) if mvt == _GR else -float(val or 0.0)

    points = [{**buckets[k], "value": safe_round(buckets[k]["value"])} for k in sorted(buckets)]
    return {"grain": grain, "points": points, "pending": False}


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


def _inventory_ribbon(db, allowed: set, buyer_of: dict, location, has_filter: bool, n: int = 12,
                      start: str | None = None, end: str | None = None):
    """Buyer-wise inventory value at each month's last snapshot (last n months,
    or within [start, end] when the dashboard's date-range filter is active)."""
    stmt = select(func.strftime("%Y-%m", InventorySnapshot.snapshot_date).label("m"),
                  func.max(InventorySnapshot.snapshot_date))
    if start:
        stmt = stmt.where(InventorySnapshot.snapshot_date >= start)
    if end:
        stmt = stmt.where(InventorySnapshot.snapshot_date <= end)
    md = db.execute(stmt.group_by("m").order_by("m")).all()
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


def _inventory_today(db, allowed: set, buyer_of: dict, location, has_filter: bool,
                     cutoff: str | None = None, start: str | None = None):
    """Total + buyer-wise inventory value at the latest daily-stock date at or
    before `cutoff` (the dashboard's date-range end, or an explicit as_of) —
    the true latest when no cutoff is given. Returns (total, by_buyer, date);
    date is None (and total/by_buyer empty) when there's nothing at/before
    cutoff, or the resolved date falls before `start` (no data in the window).
    """
    stmt = select(func.max(InventorySnapshot.snapshot_date))
    if cutoff:
        stmt = stmt.where(InventorySnapshot.snapshot_date <= cutoff)
    latest = db.execute(stmt).scalar()
    if latest is None:
        return 0.0, [], None
    if start and _to_date(latest) < _to_date(start):
        return 0.0, [], None
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
    return total, donut, latest


# Goods-movement types that make up "incoming receipts" (from movement_master):
#   101 Goods Receipt - Purchase Order         (+)
#   102 Reversal of Goods Receipt              (−)
#   501 Return to Vendor / rejection to supplier (−)
_GR, _GR_REVERSAL, _RETURN_VENDOR = "101", "102", "501"


def _primary_supplier_of(db: Session) -> dict:
    """material_code -> its highest-share vendor's name (from the SOB master).

    SOB master is many-to-many (a material can be split across several
    vendors), so this picks each material's single largest-share source as
    its "primary supplier" — mirroring the 1:1 buyer_of dict built from the
    material master's own buyer column.
    """
    rows = db.execute(
        select(SOBMaster.material, SOBMaster.vendor_name, SOBMaster.vendor_code, SOBMaster.share)
        .where(SOBMaster.material.isnot(None))
    ).all()
    best: dict[str, tuple[float, str]] = {}
    for material, vendor_name, vendor_code, share in rows:
        name = vendor_name or vendor_code or "Unassigned"
        share = float(share or 0.0)
        if material not in best or share > best[material][0]:
            best[material] = (share, name)
    return {m: name for m, (_, name) in best.items()}


def _incoming_receipts(db, allowed: set, buyer_of: dict, supplier_of: dict, has_filter: bool, as_of):
    """Net incoming receipts value for the current month, by buyer and by
    (primary) supplier.

    GR minus reversals-of-GR minus returns-to-vendor. Sourced from the
    movements transactions table; returns (0, [], [], pending=True) until one
    is loaded.
    """
    from app.analytics.common import _MODEL_BY_NAME
    if "movements" not in _MODEL_BY_NAME:
        return 0.0, [], [], True
    if db.execute(select(func.count()).select_from(Movement)).scalar() == 0:
        return 0.0, [], [], True

    now = as_of or date.today()
    month_start = date(now.year, now.month, 1)
    month_end = _month_end(now.year, now.month)
    stmt = (
        select(Movement.material_code, Movement.mvt, func.sum(Movement.value))
        .where(
            Movement.movement_date >= month_start,
            Movement.movement_date <= month_end,
            Movement.mvt.in_([_GR, _GR_REVERSAL, _RETURN_VENDOR]),
        )
        .group_by(Movement.material_code, Movement.mvt)
    )
    by_buyer: dict[str, float] = {}
    by_supplier: dict[str, float] = {}
    total = 0.0
    for code, mvt, val in db.execute(stmt).all():
        if has_filter and code not in allowed:
            continue
        val = float(val or 0.0)
        contrib = val if mvt == _GR else -val
        total += contrib
        b = buyer_of.get(code) or "Unassigned"
        by_buyer[b] = by_buyer.get(b, 0.0) + contrib
        s = supplier_of.get(code) or "Unassigned"
        by_supplier[s] = by_supplier.get(s, 0.0) + contrib
    donut_buyer = [
        {"name": b, "value": safe_round(v)}
        for b, v in sorted(by_buyer.items(), key=lambda kv: kv[1], reverse=True)
    ]
    donut_supplier = _top_n_with_other(by_supplier, 12)
    return total, donut_buyer, donut_supplier, False


def _top_n_with_other(values: dict, n: int) -> list[dict]:
    """Sort a {name: value} map descending, keep the top n and fold the rest
    into a single "Other" bucket — the supplier list can run into the dozens,
    which makes a one-bar-per-entity chart unreadable past a handful."""
    ranked = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
    head, tail = ranked[:n], ranked[n:]
    out = [{"name": name, "value": safe_round(v)} for name, v in head]
    if tail:
        out.append({"name": "Other", "value": safe_round(sum(v for _, v in tail))})
    return out
