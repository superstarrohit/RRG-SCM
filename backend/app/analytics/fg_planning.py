"""Finished-Goods Planning.

Explodes the production plan through the BOM into component requirements, then
checks each component's availability (on-hand + incoming) to flag which planned
FG production is at risk and identify the constraining components.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from app.analytics.common import (
    allowed_codes, filter_options, latest_open_pos, load_df, safe_round, stock_by_material,
)
from sqlalchemy.orm import Session


def _explode(fg: str, qty: float, bom: dict, seen: set, acc: dict) -> None:
    if fg in seen:
        return
    seen = seen | {fg}
    for comp, qty_per in bom.get(fg, []):
        req = qty * qty_per
        if comp in bom:
            _explode(comp, req, bom, seen, acc)
        else:
            acc[comp] = acc.get(comp, 0.0) + req


def analyze(db: Session, *, as_of: date | None = None, top_n: int = 25,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None,
            location: str | None = None, q: str | None = None) -> dict:
    plan = load_df(db, "production_plan")
    bom = load_df(db, "bom")
    stock = load_df(db, "stock")
    warehouse_stock = load_df(db, "warehouse_stock")
    pos = latest_open_pos(db)
    materials = load_df(db, "materials")
    opts = filter_options(materials, commodity, buyer, material, supplier, location,
                          suppliers=load_df(db, "suppliers"))
    # Supplier doesn't apply to the production plan itself (no such dimension
    # on a finished-goods plan) — accepted for consistency with the bar.

    if plan.empty or bom.empty:
        return {**_empty(as_of), "filters": opts}

    bom["qty"] = pd.to_numeric(bom["qty"], errors="coerce").fillna(1.0)
    bom_map: dict[str, list] = {}
    for _, r in bom.iterrows():
        bom_map.setdefault(r["fg_material"], []).append((r["rm_material"], float(r["qty"])))

    plan["planned_qty"] = pd.to_numeric(plan["planned_qty"], errors="coerce").fillna(0)
    plan_by_fg = plan.groupby("material_code")["planned_qty"].sum()

    # BOM's own descriptions, used when the material master doesn't cover a
    # code (or hasn't been loaded at all).
    fg_desc = bom.dropna(subset=["description"]).drop_duplicates("fg_material").set_index("fg_material")["description"].to_dict() if "description" in bom else {}
    rm_desc = bom.dropna(subset=["rm_description"]).drop_duplicates("rm_material").set_index("rm_material")["rm_description"].to_dict() if "rm_description" in bom else {}

    fg_codes = allowed_codes(materials, commodity, buyer, material)
    if fg_codes is not None:
        plan_by_fg = plan_by_fg[plan_by_fg.index.isin(fg_codes)]
    if q:
        q_low = q.strip().lower()
        desc_map = materials.set_index("material_code")["description"].to_dict() if not materials.empty else {}
        plan_by_fg = plan_by_fg[[
            q_low in str(fg).lower() or q_low in str(desc_map.get(fg) or fg_desc.get(fg) or "").lower()
            for fg in plan_by_fg.index
        ]]

    # Component gross requirements across the (filtered) plan.
    gross: dict[str, float] = {}
    for fg, qty in plan_by_fg.items():
        _explode(fg, float(qty), bom_map, set(), gross)

    # Availability per component — a Location selection sources on-hand from
    # that warehouse instead of the company-wide total.
    on_hand = stock_by_material(stock, warehouse_stock, location)
    incoming = _incoming_map(pos)
    desc = {}
    if not materials.empty:
        desc = materials.set_index("material_code")["description"].to_dict()

    component_rows = []
    for comp, req in sorted(gross.items(), key=lambda kv: kv[1], reverse=True):
        avail = on_hand.get(comp, 0.0) + incoming.get(comp, 0.0)
        shortage = max(req - avail, 0.0)
        component_rows.append(
            {
                "component": comp,
                "description": desc.get(comp) or rm_desc.get(comp),
                "required": safe_round(req),
                "on_hand": safe_round(on_hand.get(comp, 0.0)),
                "incoming": safe_round(incoming.get(comp, 0.0)),
                "available": safe_round(avail),
                "shortage": safe_round(shortage),
                "status": "short" if shortage > 0 else "ok",
            }
        )

    short_components = {r["component"] for r in component_rows if r["status"] == "short"}

    # FG feasibility: which planned FGs rely on a short component.
    fg_rows = []
    for fg, qty in plan_by_fg.items():
        comps: dict[str, float] = {}
        _explode(fg, float(qty), bom_map, set(), comps)
        constraining = sorted(set(comps) & short_components)
        fg_rows.append(
            {
                "material_code": fg,
                "description": desc.get(fg) or fg_desc.get(fg),
                "planned_qty": safe_round(qty),
                "component_count": len(comps),
                "at_risk": bool(constraining),
                "constraining_components": constraining[:10],
            }
        )
    fg_rows.sort(key=lambda r: (not r["at_risk"], -r["planned_qty"]))

    kpis = {
        "fg_planned": int(len(plan_by_fg)),
        "fg_at_risk": sum(1 for r in fg_rows if r["at_risk"]),
        "components_required": len(component_rows),
        "components_short": len(short_components),
    }
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": False,
        "filters": opts,
        "kpis": kpis,
        "fg_feasibility": fg_rows[:top_n],
        "component_requirements": component_rows[:top_n],
    }


def _incoming_map(pos: pd.DataFrame) -> dict:
    if pos.empty:
        return {}
    pos = pos.copy()
    pos["order_qty"] = pd.to_numeric(pos["order_qty"], errors="coerce").fillna(0)
    pos["received_qty"] = pd.to_numeric(pos["received_qty"], errors="coerce").fillna(0)
    pos["open_qty"] = pd.to_numeric(pos["open_qty"], errors="coerce").fillna(
        (pos["order_qty"] - pos["received_qty"]).clip(lower=0)
    )
    return pos.groupby("material_code")["open_qty"].sum().to_dict()


def _empty(as_of: date | None) -> dict:
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": True,
        "message": "Load a production plan and BOM to run finished-goods planning.",
        "filters": {"commodity": [], "buyer": [], "material": [], "supplier": [], "location": [],
                   "selected": {"commodity": None, "buyer": None, "material": None, "supplier": None, "location": None}},
        "kpis": {"fg_planned": 0, "fg_at_risk": 0, "components_required": 0, "components_short": 0},
        "fg_feasibility": [],
        "component_requirements": [],
    }
