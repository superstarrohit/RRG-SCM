"""Incoming Materials Analysis.

Turns the Open Purchase Orders dump (enriched with material, supplier and stock
master data) into a picture of the incoming pipeline: what is arriving, when,
from whom, how much it is worth, what is late, and how it compares to demand and
current stock.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.analytics.common import (
    abc_classify, allowed_codes, filter_codes, filter_supplier, load_df, safe_round, today,
)
from sqlalchemy.orm import Session


def _prepare(db, as_of, commodity=None, buyer=None, material=None, supplier=None):
    pos = load_df(db, "open_pos")
    now = today(as_of)
    if pos.empty:
        return pos, now

    materials = load_df(db, "materials")
    suppliers = load_df(db, "suppliers")
    pos = filter_codes(pos, allowed_codes(materials, commodity, buyer, material))
    pos = filter_supplier(pos, supplier)
    if pos.empty:
        return pos, now

    pos["order_qty"] = pd.to_numeric(pos["order_qty"], errors="coerce").fillna(0.0)
    pos["received_qty"] = pd.to_numeric(pos["received_qty"], errors="coerce").fillna(0.0)
    pos["open_qty"] = pd.to_numeric(pos["open_qty"], errors="coerce")
    # Derive open qty when not supplied.
    derived = (pos["order_qty"] - pos["received_qty"]).clip(lower=0)
    pos["open_qty"] = pos["open_qty"].fillna(derived)
    pos.loc[pos["open_qty"] < 0, "open_qty"] = 0.0

    pos["unit_price"] = pd.to_numeric(pos["unit_price"], errors="coerce").fillna(0.0)
    pos["expected_date"] = pd.to_datetime(pos["expected_date"], errors="coerce")

    # Enrich with material master (category, fallback cost, abc).
    if not materials.empty:
        mcols = materials[["material_code", "category", "unit_cost", "abc_class", "description"]]
        pos = pos.merge(mcols, on="material_code", how="left", suffixes=("", "_mat"))
    for col in ("category", "abc_class", "description"):
        if col not in pos:
            pos[col] = None
    if "unit_cost" not in pos:
        pos["unit_cost"] = 0.0
    pos["unit_cost"] = pd.to_numeric(pos["unit_cost"], errors="coerce").fillna(0.0)

    # Effective price for valuation: PO price, else material standard cost.
    pos["eff_price"] = np.where(pos["unit_price"] > 0, pos["unit_price"], pos["unit_cost"])
    pos["open_value"] = pos["open_qty"] * pos["eff_price"]

    # Supplier name.
    if not suppliers.empty and "supplier_code" in pos:
        scols = suppliers[["supplier_code", "name"]].rename(columns={"name": "supplier_name"})
        pos = pos.merge(scols, on="supplier_code", how="left")
    if "supplier_name" not in pos:
        pos["supplier_name"] = None

    # Timing.
    pos["days_to_arrival"] = (pos["expected_date"] - now).dt.days
    pos["status"] = _status(pos["days_to_arrival"], pos["expected_date"])
    pos["days_overdue"] = np.where(pos["days_to_arrival"] < 0, -pos["days_to_arrival"], 0)

    # Keep only lines that still have something open.
    pos = pos[pos["open_qty"] > 0].copy()
    return pos, now


def _status(days: pd.Series, expected: pd.Series) -> pd.Series:
    status = pd.Series("future", index=days.index, dtype="object")
    status[expected.isna()] = "no_date"
    status[(days.notna()) & (days < 0)] = "overdue"
    status[(days >= 0) & (days <= 7)] = "due_this_week"
    status[(days > 7) & (days <= 30)] = "due_this_month"
    return status


_STATUS_ORDER = ["overdue", "due_this_week", "due_this_month", "future", "no_date"]
_STATUS_LABEL = {
    "overdue": "Overdue",
    "due_this_week": "Due this week",
    "due_this_month": "Due this month",
    "future": "Future (>30d)",
    "no_date": "No ETA",
}


def analyze(
    db: Session,
    *,
    as_of: date | None = None,
    horizon_weeks: int = 8,
    top_n: int = 15,
    commodity: str | None = None,
    buyer: str | None = None,
    material: str | None = None,
    supplier: str | None = None,
) -> dict:
    from app.analytics.common import filter_options
    opts = filter_options(load_df(db, "materials"), commodity, buyer, material, supplier,
                          suppliers=load_df(db, "suppliers"))
    pos, now = _prepare(db, as_of, commodity, buyer, material, supplier)

    if pos.empty:
        return {
            "as_of": (as_of or date.today()).isoformat(),
            "empty": True,
            "message": "No open purchase orders loaded (or none match the filters). Upload the 'Open Purchase Orders' dump.",
            "filters": opts,
            "kpis": _empty_kpis(),
            "status_breakdown": [],
            "arrival_timeline": [],
            "overdue_lines": [],
            "by_supplier": [],
            "by_category": [],
            "abc_incoming": [],
            "coverage": [],
        }

    kpis = _kpis(pos, now)
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": False,
        "filters": opts,
        "kpis": kpis,
        "status_breakdown": _status_breakdown(pos),
        "arrival_timeline": _arrival_timeline(pos, now, horizon_weeks),
        "overdue_lines": _overdue_lines(pos, top_n),
        "by_supplier": _by_supplier(pos, top_n),
        "by_category": _by_category(pos),
        "abc_incoming": _abc_incoming(pos),
        "coverage": _coverage(db, pos, top_n),
    }


def _empty_kpis() -> dict:
    return {
        "open_lines": 0,
        "open_qty": 0.0,
        "open_value": 0.0,
        "overdue_lines": 0,
        "overdue_value": 0.0,
        "overdue_pct_value": 0.0,
        "arriving_7d_value": 0.0,
        "arriving_30d_value": 0.0,
        "suppliers": 0,
        "materials": 0,
        "avg_days_to_arrival": 0.0,
    }


def _kpis(pos: pd.DataFrame, now: pd.Timestamp) -> dict:
    total_value = pos["open_value"].sum()
    overdue = pos[pos["status"] == "overdue"]
    d7 = pos[(pos["days_to_arrival"] >= 0) & (pos["days_to_arrival"] <= 7)]
    d30 = pos[(pos["days_to_arrival"] >= 0) & (pos["days_to_arrival"] <= 30)]
    fut = pos[pos["days_to_arrival"] >= 0]["days_to_arrival"]
    return {
        "open_lines": int(len(pos)),
        "open_qty": safe_round(pos["open_qty"].sum()),
        "open_value": safe_round(total_value),
        "overdue_lines": int(len(overdue)),
        "overdue_value": safe_round(overdue["open_value"].sum()),
        "overdue_pct_value": safe_round(
            100 * overdue["open_value"].sum() / total_value if total_value else 0
        ),
        "arriving_7d_value": safe_round(d7["open_value"].sum()),
        "arriving_30d_value": safe_round(d30["open_value"].sum()),
        "suppliers": int(pos["supplier_code"].nunique()) if "supplier_code" in pos else 0,
        "materials": int(pos["material_code"].nunique()),
        "avg_days_to_arrival": safe_round(fut.mean() if not fut.empty else 0),
    }


def _status_breakdown(pos: pd.DataFrame) -> list[dict]:
    grp = pos.groupby("status").agg(
        lines=("open_qty", "size"),
        qty=("open_qty", "sum"),
        value=("open_value", "sum"),
    )
    out = []
    for st in _STATUS_ORDER:
        if st in grp.index:
            row = grp.loc[st]
            out.append(
                {
                    "status": st,
                    "label": _STATUS_LABEL[st],
                    "lines": int(row["lines"]),
                    "qty": safe_round(row["qty"]),
                    "value": safe_round(row["value"]),
                }
            )
    return out


def _arrival_timeline(pos: pd.DataFrame, now: pd.Timestamp, horizon_weeks: int) -> list[dict]:
    dated = pos[pos["expected_date"].notna()].copy()
    if dated.empty:
        return []
    week_start = now - pd.Timedelta(days=now.dayofweek)
    buckets = []
    for w in range(horizon_weeks):
        start = week_start + pd.Timedelta(weeks=w)
        end = start + pd.Timedelta(weeks=1)
        if w == 0:  # first bucket also sweeps up anything overdue
            sel = dated[dated["expected_date"] < end]
            label = "This week + overdue"
        elif w == horizon_weeks - 1:  # last bucket sweeps up everything beyond
            sel = dated[dated["expected_date"] >= start]
            label = f"{start.date().isoformat()}+"
        else:
            sel = dated[(dated["expected_date"] >= start) & (dated["expected_date"] < end)]
            label = start.date().isoformat()
        buckets.append(
            {
                "week_start": start.date().isoformat(),
                "label": label,
                "lines": int(len(sel)),
                "qty": safe_round(sel["open_qty"].sum()),
                "value": safe_round(sel["open_value"].sum()),
            }
        )
    return buckets


def _overdue_lines(pos: pd.DataFrame, top_n: int) -> list[dict]:
    overdue = pos[pos["status"] == "overdue"].sort_values(
        ["days_overdue", "open_value"], ascending=False
    ).head(top_n)
    out = []
    for _, r in overdue.iterrows():
        out.append(
            {
                "po_number": r.get("po_number"),
                "po_line": r.get("po_line"),
                "material_code": r["material_code"],
                "description": r.get("description"),
                "supplier_code": r.get("supplier_code"),
                "supplier_name": r.get("supplier_name"),
                "open_qty": safe_round(r["open_qty"]),
                "open_value": safe_round(r["open_value"]),
                "expected_date": r["expected_date"].date().isoformat()
                if pd.notna(r["expected_date"])
                else None,
                "days_overdue": int(r["days_overdue"]),
            }
        )
    return out


def _by_supplier(pos: pd.DataFrame, top_n: int) -> list[dict]:
    if "supplier_code" not in pos:
        return []
    grp = pos.groupby(["supplier_code"]).agg(
        supplier_name=("supplier_name", "first"),
        lines=("open_qty", "size"),
        open_qty=("open_qty", "sum"),
        open_value=("open_value", "sum"),
        overdue_value=("open_value", lambda s: s[pos.loc[s.index, "status"] == "overdue"].sum()),
    ).sort_values("open_value", ascending=False).head(top_n)
    out = []
    for code, r in grp.iterrows():
        out.append(
            {
                "supplier_code": code,
                "supplier_name": r["supplier_name"],
                "lines": int(r["lines"]),
                "open_qty": safe_round(r["open_qty"]),
                "open_value": safe_round(r["open_value"]),
                "overdue_value": safe_round(r["overdue_value"]),
            }
        )
    return out


def _by_category(pos: pd.DataFrame) -> list[dict]:
    pos = pos.copy()
    pos["category"] = pos["category"].fillna("Uncategorised")
    grp = pos.groupby("category").agg(
        lines=("open_qty", "size"),
        open_qty=("open_qty", "sum"),
        open_value=("open_value", "sum"),
    ).sort_values("open_value", ascending=False)
    return [
        {
            "category": cat,
            "lines": int(r["lines"]),
            "open_qty": safe_round(r["open_qty"]),
            "open_value": safe_round(r["open_value"]),
        }
        for cat, r in grp.iterrows()
    ]


def _abc_incoming(pos: pd.DataFrame) -> list[dict]:
    by_mat = pos.groupby("material_code").agg(
        description=("description", "first"),
        open_qty=("open_qty", "sum"),
        open_value=("open_value", "sum"),
    )
    by_mat["abc"] = abc_classify(by_mat["open_value"])
    summary = by_mat.groupby("abc").agg(
        materials=("open_value", "size"),
        open_value=("open_value", "sum"),
    )
    total = by_mat["open_value"].sum()
    out = []
    for cls in ["A", "B", "C"]:
        if cls in summary.index:
            r = summary.loc[cls]
            out.append(
                {
                    "abc": cls,
                    "materials": int(r["materials"]),
                    "open_value": safe_round(r["open_value"]),
                    "value_pct": safe_round(100 * r["open_value"] / total if total else 0),
                }
            )
    return out


def _coverage(db: Session, pos: pd.DataFrame, top_n: int) -> list[dict]:
    """Compare incoming qty against current stock for the biggest incoming items."""
    stock = load_df(db, "stock")
    stock_by_mat = {}
    if not stock.empty:
        stock["qty_on_hand"] = pd.to_numeric(stock["qty_on_hand"], errors="coerce").fillna(0)
        stock_by_mat = stock.groupby("material_code")["qty_on_hand"].sum().to_dict()

    by_mat = pos.groupby("material_code").agg(
        description=("description", "first"),
        incoming_qty=("open_qty", "sum"),
        incoming_value=("open_value", "sum"),
    ).sort_values("incoming_value", ascending=False).head(top_n)

    out = []
    for code, r in by_mat.iterrows():
        on_hand = float(stock_by_mat.get(code, 0.0))
        incoming = float(r["incoming_qty"])
        total_avail = on_hand + incoming
        # None means there is no stock on hand (coverage ratio is undefined).
        vs_stock = safe_round(100 * incoming / on_hand) if on_hand > 0 else None
        out.append(
            {
                "material_code": code,
                "description": r["description"],
                "on_hand": safe_round(on_hand),
                "incoming_qty": safe_round(incoming),
                "total_available": safe_round(total_avail),
                "incoming_value": safe_round(r["incoming_value"]),
                "incoming_vs_stock_pct": vs_stock,
            }
        )
    return out
