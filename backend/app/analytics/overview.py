"""Overall SCM dashboard — a cross-module executive summary."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import (
    incoming_materials,
    material_planning,
    sourcing,
)
from app.analytics.common import load_df, safe_round
from app.models import IngestionLog


def analyze(db: Session, *, as_of: date | None = None,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None) -> dict:
    from app.analytics.common import allowed_codes, filter_codes, filter_options
    kw = {"commodity": commodity, "buyer": buyer, "material": material, "supplier": supplier}
    incoming = incoming_materials.analyze(db, as_of=as_of, **kw)
    planning = material_planning.analyze(db, as_of=as_of, **kw)
    srcing = sourcing.analyze(db, as_of=as_of, **kw)

    materials = load_df(db, "materials")
    opts = filter_options(materials, commodity, buyer, material, supplier,
                          suppliers=load_df(db, "suppliers"))
    codes = allowed_codes(materials, commodity, buyer, material)
    stock = filter_codes(load_df(db, "stock"), codes)
    stock_value = 0.0
    if not stock.empty and not materials.empty:
        merged = stock.merge(
            materials[["material_code", "unit_cost"]], on="material_code", how="left"
        )
        merged["qty_on_hand"] = merged["qty_on_hand"].fillna(0)
        merged["unit_cost"] = merged["unit_cost"].fillna(0)
        stock_value = (merged["qty_on_hand"] * merged["unit_cost"]).sum()

    data_status = _data_status(db)

    return {
        "as_of": (as_of or date.today()).isoformat(),
        "filters": opts,
        "kpis": {
            "inventory_value": safe_round(stock_value),
            "incoming_value": incoming["kpis"]["open_value"],
            "overdue_value": incoming["kpis"]["overdue_value"],
            "shortage_items": planning["kpis"]["shortage_items"],
            "reorder_alerts": planning["kpis"]["at_or_below_rop"],
            "active_suppliers": srcing["kpis"]["active_suppliers"],
            "single_source_materials": srcing["kpis"]["single_source_materials"],
            "avg_on_time_pct": srcing["kpis"]["avg_on_time_pct"],
        },
        "incoming_status": incoming["status_breakdown"],
        "top_shortages": planning["shortages"][:5],
        "top_suppliers": srcing["supplier_spend"][:5],
        "arrival_timeline": incoming["arrival_timeline"],
        "data_status": data_status,
    }


def _data_status(db: Session) -> list[dict]:
    """Row counts + last-ingested per dump type, for a data-freshness panel."""
    from app.ingestion.dump_types import DUMP_TYPES

    out = []
    for key, dump in DUMP_TYPES.items():
        model = dump.model
        count = db.execute(select(func.count()).select_from(model)).scalar() or 0
        last = db.execute(
            select(func.max(IngestionLog.ingested_at)).where(IngestionLog.dump_type == key)
        ).scalar()
        out.append(
            {
                "dump_type": key,
                "label": dump.label,
                "rows": int(count),
                "last_ingested": last.isoformat() if last else None,
                "loaded": count > 0,
            }
        )
    return out
