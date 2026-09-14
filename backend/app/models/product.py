"""Product-structure models: BOM and finished-goods plan (used by costing & FG)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BOMLine(Base, TimestampMixin):
    """Bill-of-materials: which components make up a parent (finished good)."""

    __tablename__ = "bom_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_material: Mapped[str] = mapped_column(String(64), index=True)
    component_material: Mapped[str] = mapped_column(String(64), index=True)
    qty_per: Mapped[float] = mapped_column(Float, default=1.0)
    scrap_pct: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100


class ProductionPlan(Base, TimestampMixin):
    """Planned finished-goods production quantities per period."""

    __tablename__ = "production_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_code: Mapped[str] = mapped_column(String(64), index=True)
    period: Mapped[date | None] = mapped_column(Date, index=True)
    planned_qty: Mapped[float] = mapped_column(Float, default=0.0)
