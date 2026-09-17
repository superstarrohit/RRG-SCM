"""Transactional / snapshot models loaded from daily dumps.

These are the "dumps" the business uploads: stock snapshots, open purchase
orders, goods receipts, warehouse stock, and demand/requirements.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Stock(Base, TimestampMixin):
    """Current on-hand stock snapshot (company-wide, per material)."""

    __tablename__ = "stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_code: Mapped[str] = mapped_column(String(64), index=True)
    qty_on_hand: Mapped[float] = mapped_column(Float, default=0.0)
    qty_blocked: Mapped[float] = mapped_column(Float, default=0.0)
    as_of_date: Mapped[date | None] = mapped_column(Date, index=True)


class WarehouseStock(Base, TimestampMixin):
    """Stock broken down by warehouse / location."""

    __tablename__ = "warehouse_stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(64), index=True)
    material_code: Mapped[str] = mapped_column(String(64), index=True)
    location: Mapped[str | None] = mapped_column(String(64))
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    as_of_date: Mapped[date | None] = mapped_column(Date, index=True)


class PurchaseOrder(Base, TimestampMixin):
    """Daily snapshot of open purchase order lines (incoming materials pipeline).

    Uploaded as one row per PO line *per day* — open_qty depletes over the
    life of the line until it's fully received. Analytics that want "today's"
    open-PO state should go through ``analytics.common.latest_open_pos()``,
    which collapses this to one row per (po, item) at its latest snapshot
    and renames columns to the internal names those modules expect.
    """

    __tablename__ = "purchase_orders"
    __table_args__ = (
        # Speeds up latest_open_pos()'s ROW_NUMBER() OVER (PARTITION BY po, item …).
        Index("ix_purchase_orders_po_item_snapshot", "po", "item", "snapshot_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date | None] = mapped_column(Date, index=True)
    po: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str | None] = mapped_column(String(255))  # supplier name
    material: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str | None] = mapped_column(String(255))
    po_qty: Mapped[float] = mapped_column(Float, default=0.0)
    po_value: Mapped[float] = mapped_column(Float, default=0.0)
    delivery_date: Mapped[date | None] = mapped_column(Date, index=True)
    item: Mapped[str | None] = mapped_column(String(32))
    po_date: Mapped[date | None] = mapped_column(Date, index=True)
    open_qty: Mapped[float] = mapped_column(Float, default=0.0)
    net_price: Mapped[float] = mapped_column(Float, default=0.0)
    supplier_code: Mapped[str | None] = mapped_column(String(64), index=True)
    shipping: Mapped[str | None] = mapped_column(String(32))
    tax: Mapped[str | None] = mapped_column(String(32))
    created_by: Mapped[str | None] = mapped_column(String(120))


class Receipt(Base, TimestampMixin):
    """Goods receipts (GRN) against POs."""

    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[str | None] = mapped_column(String(64), index=True)
    po_number: Mapped[str | None] = mapped_column(String(64), index=True)
    material_code: Mapped[str] = mapped_column(String(64), index=True)
    supplier_code: Mapped[str | None] = mapped_column(String(64), index=True)
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    receipt_date: Mapped[date | None] = mapped_column(Date, index=True)


class InventorySnapshot(Base, TimestampMixin):
    """Historical stock snapshots for inventory trend analysis (qty + value)."""

    __tablename__ = "inventory_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_code: Mapped[str] = mapped_column(String(64), index=True)
    location: Mapped[str | None] = mapped_column(String(64), index=True)
    snapshot_date: Mapped[date | None] = mapped_column(Date, index=True)
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    value: Mapped[float] = mapped_column(Float, default=0.0)


class Movement(Base, TimestampMixin):
    """Material movements: receipts, issues, transfers, adjustments (GRN etc.)."""

    __tablename__ = "movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_code: Mapped[str] = mapped_column(String(64), index=True)
    mvt_type: Mapped[str | None] = mapped_column(String(64), index=True)  # e.g. GRN, Issue
    description: Mapped[str | None] = mapped_column(String(255))
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    movement_date: Mapped[date | None] = mapped_column(Date, index=True)


class Demand(Base, TimestampMixin):
    """Demand / requirements (forecast, sales orders, or production demand)."""

    __tablename__ = "demand"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_code: Mapped[str] = mapped_column(String(64), index=True)
    period: Mapped[date | None] = mapped_column(Date, index=True)
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    demand_type: Mapped[str | None] = mapped_column(String(32))  # forecast/so/prod


class Forecast(Base, TimestampMixin):
    """Rolling monthly forecast per material (M1 = next month, M2, M3)."""

    __tablename__ = "forecast"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_code: Mapped[str] = mapped_column(String(64), index=True)
    m1_qty: Mapped[float] = mapped_column(Float, default=0.0)
    m2_qty: Mapped[float] = mapped_column(Float, default=0.0)
    m3_qty: Mapped[float] = mapped_column(Float, default=0.0)
