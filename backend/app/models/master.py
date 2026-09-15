"""Master-data models: materials and suppliers."""
from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Material(Base, TimestampMixin):
    """Item master. One row per material/SKU."""

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(128), index=True)
    commodity: Mapped[str | None] = mapped_column(String(128), index=True)  # sourcing group
    buyer: Mapped[str | None] = mapped_column(String(128), index=True)      # responsible buyer
    uom: Mapped[str | None] = mapped_column(String(32))  # unit of measure

    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str | None] = mapped_column(String(8), default="USD")

    # Planning parameters
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0)
    safety_stock: Mapped[float] = mapped_column(Float, default=0.0)
    reorder_point: Mapped[float] = mapped_column(Float, default=0.0)
    refill_level: Mapped[float] = mapped_column(Float, default=0.0)  # trigger re-order
    max_level: Mapped[float] = mapped_column(Float, default=0.0)     # overstock ceiling
    min_order_qty: Mapped[float] = mapped_column(Float, default=0.0)

    abc_class: Mapped[str | None] = mapped_column(String(1))  # A / B / C


class Supplier(Base, TimestampMixin):
    """Supplier / vendor master."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(64))
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float | None] = mapped_column(Float)  # 0-100 performance score
