"""Costing analysis.

Rolls BOM component costs up to finished-good level (single & multi-level),
and reports material cost distribution.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from app.analytics.common import materials_df, allowed_codes, apply_search, filter_options, load_df, safe_round
from sqlalchemy.orm import Session


def _roll_up(parent: str, bom: dict, cost: dict, seen: set) -> float:
    """Recursively compute the rolled-up material cost of a parent material."""
    if parent in seen:  # guard against cyclic BOMs
        return 0.0
    seen = seen | {parent}
    total = 0.0
    for comp, qty in bom.get(parent, []):
        if comp in bom:  # sub-assembly -> recurse
            total += qty * _roll_up(comp, bom, cost, seen)
        else:  # raw / purchased component
            total += qty * cost.get(comp, 0.0)
    return total


def analyze(db: Session, *, as_of: date | None = None, top_n: int = 25,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None,
            location: str | None = None, q: str | None = None) -> dict:
    materials = materials_df(db)
    bom = load_df(db, "bom")
    opts = filter_options(materials, commodity, buyer, material, supplier, location,
                          suppliers=load_df(db, "suppliers"))
    # Supplier/Location don't apply to BOM cost roll-up (no such dimension on
    # a bill of materials) — accepted for consistency with the global bar.

    if bom.empty:
        return {**_empty(as_of), "filters": opts}

    parent_codes = allowed_codes(materials, commodity, buyer, material)

    cost = {}
    desc = {}
    if not materials.empty:
        materials["unit_cost"] = pd.to_numeric(materials["unit_cost"], errors="coerce").fillna(0)
        cost = materials.set_index("material_code")["unit_cost"].to_dict()
        desc = materials.set_index("material_code")["description"].to_dict()

    # The BOM carries its own FG description, so costing still shows readable
    # names even when the material master hasn't been loaded (or doesn't cover
    # this FG) — material master takes precedence when both are present.
    bom_desc = bom.dropna(subset=["description"]).drop_duplicates("fg_material").set_index("fg_material")["description"].to_dict() if "description" in bom else {}

    bom["qty"] = pd.to_numeric(bom["qty"], errors="coerce").fillna(1.0)
    bom_map: dict[str, list] = {}
    for _, r in bom.iterrows():
        bom_map.setdefault(r["fg_material"], []).append((r["rm_material"], float(r["qty"])))

    parents = [p for p in bom_map if parent_codes is None or p in parent_codes]
    if q:
        ql = q.lower()
        parents = [
            p for p in parents
            if ql in p.lower() or ql in str(desc.get(p) or bom_desc.get(p) or "").lower()
        ]

    rows = []
    for parent in parents:
        rolled = _roll_up(parent, bom_map, cost, set())
        std = cost.get(parent, 0.0)
        rows.append(
            {
                "material_code": parent,
                "description": desc.get(parent) or bom_desc.get(parent),
                "components": len(bom_map[parent]),
                "rolled_up_cost": safe_round(rolled),
                "standard_cost": safe_round(std),
                "variance": safe_round(std - rolled),
                "variance_pct": safe_round(100 * (std - rolled) / rolled) if rolled else None,
            }
        )
    if q:
        q_low = q.strip().lower()
        rows = [r for r in rows if q_low in str(r["material_code"]).lower()
                or q_low in str(r.get("description") or "").lower()]

    rows.sort(key=lambda r: r["rolled_up_cost"], reverse=True)

    kpis = {
        "finished_goods_costed": len(rows),
        "avg_rolled_up_cost": safe_round(
            sum(r["rolled_up_cost"] for r in rows) / len(rows) if rows else 0
        ),
        "items_with_variance": sum(1 for r in rows if abs(r["variance"]) > 0.01),
    }
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": False,
        "filters": opts,
        "kpis": kpis,
        "cost_rollup": rows[:top_n],
    }


def _empty(as_of: date | None) -> dict:
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "empty": True,
        "message": "Load a Bill of Materials (and material master for costs) to run costing.",
        "filters": {"commodity": [], "buyer": [], "material": [], "supplier": [], "location": [],
                   "selected": {"commodity": None, "buyer": None, "material": None, "supplier": None, "location": None}},
        "kpis": {"finished_goods_costed": 0, "avg_rolled_up_cost": 0.0, "items_with_variance": 0},
        "cost_rollup": [],
    }
