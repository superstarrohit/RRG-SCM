"""Analytics endpoints — one per module plus the overall dashboard."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics import (
    costing,
    fg_planning,
    forecasting,
    incoming_materials,
    inventory_monitoring,
    material_planning,
    movements,
    overview,
    sourcing,
    stock_monitoring,
    vendor_receipts,
)
from app.database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _as_of(as_of: str | None) -> date | None:
    return date.fromisoformat(as_of) if as_of else None


# Shared global slicers (mirrors the reference report's filter panel:
# commodity, buyer, material, supplier, location and a free-text search box
# — date range is passed separately as start/end since only the time-series
# endpoints use it).
def _slicers(
    commodity: str | None = Query(None),
    buyer: str | None = Query(None),
    material: str | None = Query(None),
    supplier: str | None = Query(None),
    location: str | None = Query(None),
    q: str | None = Query(None, description="Free-text search (material, description, PO, supplier)"),
) -> dict:
    return {
        "commodity": commodity, "buyer": buyer, "material": material,
        "supplier": supplier, "location": location, "q": q,
    }


@router.get("/overview")
def get_overview(as_of: str | None = Query(None), f: dict = Depends(_slicers),
                 db: Session = Depends(get_db)) -> dict:
    return overview.analyze(db, as_of=_as_of(as_of), **f)


@router.get("/incoming")
def get_incoming(
    as_of: str | None = Query(None),
    horizon_weeks: int = Query(8, ge=1, le=52),
    top_n: int = Query(15, ge=1, le=100),
    f: dict = Depends(_slicers),
    db: Session = Depends(get_db),
) -> dict:
    return incoming_materials.analyze(
        db, as_of=_as_of(as_of), horizon_weeks=horizon_weeks, top_n=top_n, **f
    )


@router.get("/planning")
def get_planning(
    as_of: str | None = Query(None),
    top_n: int = Query(20, ge=1, le=200),
    f: dict = Depends(_slicers),
    db: Session = Depends(get_db),
) -> dict:
    return material_planning.analyze(db, as_of=_as_of(as_of), top_n=top_n, **f)


@router.get("/sourcing")
def get_sourcing(
    as_of: str | None = Query(None),
    top_n: int = Query(20, ge=1, le=200),
    f: dict = Depends(_slicers),
    db: Session = Depends(get_db),
) -> dict:
    return sourcing.analyze(db, as_of=_as_of(as_of), top_n=top_n, **f)


@router.get("/costing")
def get_costing(
    as_of: str | None = Query(None),
    top_n: int = Query(25, ge=1, le=200),
    f: dict = Depends(_slicers),
    db: Session = Depends(get_db),
) -> dict:
    return costing.analyze(db, as_of=_as_of(as_of), top_n=top_n, **f)


@router.get("/fg-planning")
def get_fg_planning(
    as_of: str | None = Query(None),
    top_n: int = Query(25, ge=1, le=200),
    f: dict = Depends(_slicers),
    db: Session = Depends(get_db),
) -> dict:
    return fg_planning.analyze(db, as_of=_as_of(as_of), top_n=top_n, **f)


@router.get("/stock-monitoring")
def get_stock_monitoring(
    as_of: str | None = Query(None),
    top_n: int = Query(25, ge=1, le=500),
    f: dict = Depends(_slicers),
    db: Session = Depends(get_db),
) -> dict:
    return stock_monitoring.analyze(db, as_of=_as_of(as_of), top_n=top_n, **f)


@router.get("/inventory-monitoring")
def get_inventory_monitoring(
    as_of: str | None = Query(None),
    top_n: int = Query(12, ge=1, le=100),
    start: str | None = Query(None),
    end: str | None = Query(None),
    f: dict = Depends(_slicers),
    db: Session = Depends(get_db),
) -> dict:
    return inventory_monitoring.analyze(db, as_of=_as_of(as_of), top_n=top_n, start=start, end=end, **f)


@router.get("/vendor-receipts")
def get_vendor_receipts(
    as_of: str | None = Query(None),
    top_n: int = Query(12, ge=1, le=100),
    start: str | None = Query(None),
    end: str | None = Query(None),
    f: dict = Depends(_slicers),
    db: Session = Depends(get_db),
) -> dict:
    return vendor_receipts.analyze(db, as_of=_as_of(as_of), top_n=top_n, start=start, end=end, **f)


@router.get("/movements")
def get_movements(
    as_of: str | None = Query(None),
    top_n: int = Query(20, ge=1, le=200),
    start: str | None = Query(None),
    end: str | None = Query(None),
    mvt_type: str | None = Query(None, description="Movement type — page-specific slicer"),
    f: dict = Depends(_slicers),
    db: Session = Depends(get_db),
) -> dict:
    return movements.analyze(db, as_of=_as_of(as_of), top_n=top_n, start=start, end=end, mvt_type=mvt_type, **f)


@router.get("/forecasting")
def get_forecasting(
    as_of: str | None = Query(None),
    top_n: int = Query(30, ge=1, le=500),
    f: dict = Depends(_slicers),
    db: Session = Depends(get_db),
) -> dict:
    return forecasting.analyze(db, as_of=_as_of(as_of), top_n=top_n, **f)
