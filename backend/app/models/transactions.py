"""Transactional / snapshot models loaded from daily dumps.

Currently the open-PO daily snapshot and the inventory history — the two
transactional dumps backed by real uploaded files.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


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


class InventorySnapshot(Base, TimestampMixin):
    """Historical stock snapshots for inventory trend analysis (qty + value)."""

    __tablename__ = "inventory_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_code: Mapped[str] = mapped_column(String(64), index=True)
    location: Mapped[str | None] = mapped_column(String(64), index=True)
    snapshot_date: Mapped[date | None] = mapped_column(Date, index=True)
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    value: Mapped[float] = mapped_column(Float, default=0.0)


class WarehouseStock(Base, TimestampMixin):
    """Daily warehouse-stock snapshot, per plant × storage location × material.

    Uploaded as one row per (plant, storage_location, material) per day.
    ``analytics.common.latest_warehouse_stock()`` collapses it to the most
    recent snapshot and renames columns to the internal names
    (material_code, warehouse_code, qty) the on-hand calculations expect.
    """

    __tablename__ = "warehouse_stock"
    __table_args__ = (
        Index("ix_warehouse_stock_key_date", "plant", "storage_location", "material", "stock_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_date: Mapped[date | None] = mapped_column(Date, index=True)
    plant: Mapped[str | None] = mapped_column(String(64), index=True)
    storage_location: Mapped[str | None] = mapped_column(String(64), index=True)
    material: Mapped[str] = mapped_column(String(64), index=True)
    stock: Mapped[float] = mapped_column(Float, default=0.0)
    value: Mapped[float] = mapped_column(Float, default=0.0)
