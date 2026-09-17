"""Overall SCM dashboard — a cross-module executive summary."""
from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import (
    incoming_materials,
    material_planning,
    sourcing,
)
from app.analytics.common import materials_df, load_df, safe_round, stock_by_material
from app.models import IngestionLog


def analyze(db: Session, *, as_of: date | None = None,
            commodity: str | None = None, buyer: str | None = None,
            material: str | None = None, supplier: str | None = None,
            location: str | None = None, q: str | None = None) -> dict:
    from app.analytics.common import allowed_codes, apply_search, filter_codes, filter_options, location_options
    kw = {"commodity": commodity, "buyer": buyer, "material": material,
          "supplier": supplier, "location": location, "q": q}
    incoming = incoming_materials.analyze(db, as_of=as_of, **kw)
    planning = material_planning.analyze(db, as_of=as_of, **kw)
    srcing = sourcing.analyze(db, as_of=as_of, **kw)

    materials = materials_df(db)
    warehouse_stock = load_df(db, "warehouse_stock")
    opts = filter_options(materials, commodity, buyer, material, supplier, location,
                          suppliers=load_df(db, "suppliers"),
                          locations=location_options(warehouse_stock))
    codes = allowed_codes(materials, commodity, buyer, material)
    filtered_materials = apply_search(filter_codes(materials, codes), q, ["material_code", "description"])
    stock_map = stock_by_material(load_df(db, "stock"), warehouse_stock, location)
    stock_value = 0.0
    if not filtered_materials.empty:
        m = filtered_materials.copy()
        m["qty_on_hand"] = m["material_code"].map(stock_map).fillna(0.0)
        m["unit_cost"] = pd.to_numeric(m["unit_cost"], errors="coerce").fillna(0.0)
        stock_value = (m["qty_on_hand"] * m["unit_cost"]).sum()

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
