"""Finished-Goods Planning.

Explodes the production plan through the BOM into component requirements, then
checks each component's availability (on-hand + incoming) to flag which planned
FG production is at risk and identify the constraining components.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from app.analytics.common import load_df, safe_round
from sqlalchemy.orm import Session


def _explode(fg: str, qty: float, bom: dict, seen: set, acc: dict) -> None:
    if fg in seen:
        return
    seen = seen | {fg}
    for comp, qty_per, scrap in bom.get(fg, []):
        req = qty * qty_per * (1 + scrap / 100.0)
        if comp in bom:
            _explode(comp, req, bom, seen, acc)
        else:
            acc[comp] = acc.get(comp, 0.0) + req


def analyze(db: Session, *, as_of: date | None = None, top_n: int = 25) -> dict:
    plan = load_df(db, "production_plan")
    bom = load_df(db, "bom")
    stock = load_df(db, "stock")
    pos = load_df(db, "open_pos")
    materials = load_df(db, "materials")

    if plan.empty or bom.empty:
        return _empty(as_of)

    bom["qty_per"] = pd.to_numeric(bom["qty_per"], errors="coerce").fillna(1.0)
    bom["scrap_pct"] = pd.to_numeric(bom["scrap_pct"], errors="coerce").fillna(0.0)
    bom_map: dict[str, list] = {}
    for _, r in bom.iterrows():
        bom_map.setdefault(r["parent_material"], []).append(
            (r["component_material"], float(r["qty_per"]), float(r["scrap_pct"]))
        )

    plan["planned_qty"] = pd.to_numeric(plan["planned_qty"], errors="coerce").fillna(0)
    plan_by_fg = plan.groupby("material_code")["planned_qty"].sum()

    # Component gross requirements across the whole plan.
    gross: dict[str, float] = {}
    for fg, qty in plan_by_fg.items():
        _explode(fg, float(qty), bom_map, set(), gross)

    # Availability per component.
    on_hand = _sum_map(stock, "material_code", "qty_on_hand")
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
                "description": desc.get(comp),
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
                "description": desc.get(fg),
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
        "kpis": kpis,
        "fg_feasibility": fg_rows[:top_n],
        "component_requirements": component_rows[:top_n],
    }


def _sum_map(df: pd.DataFrame, key: str, val: str) -> dict:
    if df.empty or val not in df:
        return {}
    df = df.copy()
    df[val] = pd.to_numeric(df[val], errors="coerce").fillna(0)
    return df.groupby(key)[val].sum().to_dict()


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
        "kpis": {"fg_planned": 0, "fg_at_risk": 0, "components_required": 0, "components_short": 0},
        "fg_feasibility": [],
        "component_requirements": [],
    }
