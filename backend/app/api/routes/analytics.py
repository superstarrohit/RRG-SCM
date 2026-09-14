"""Analytics endpoints — one per module plus the overall dashboard."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics import (
    costing,
    fg_planning,
    incoming_materials,
    material_planning,
    overview,
    sourcing,
)
from app.database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _as_of(as_of: str | None) -> date | None:
    return date.fromisoformat(as_of) if as_of else None


@router.get("/overview")
def get_overview(as_of: str | None = Query(None), db: Session = Depends(get_db)) -> dict:
    return overview.analyze(db, as_of=_as_of(as_of))


@router.get("/incoming")
def get_incoming(
    as_of: str | None = Query(None),
    horizon_weeks: int = Query(8, ge=1, le=52),
    top_n: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return incoming_materials.analyze(
        db, as_of=_as_of(as_of), horizon_weeks=horizon_weeks, top_n=top_n
    )


@router.get("/planning")
def get_planning(
    as_of: str | None = Query(None),
    top_n: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return material_planning.analyze(db, as_of=_as_of(as_of), top_n=top_n)


@router.get("/sourcing")
def get_sourcing(
    as_of: str | None = Query(None),
    top_n: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return sourcing.analyze(db, as_of=_as_of(as_of), top_n=top_n)


@router.get("/costing")
def get_costing(
    as_of: str | None = Query(None),
    top_n: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return costing.analyze(db, as_of=_as_of(as_of), top_n=top_n)


@router.get("/fg-planning")
def get_fg_planning(
    as_of: str | None = Query(None),
    top_n: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return fg_planning.analyze(db, as_of=_as_of(as_of), top_n=top_n)
