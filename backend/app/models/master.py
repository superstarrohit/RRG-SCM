"""Master-data models: materials, suppliers, and the location / movement /
source-of-business masters."""
from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Material(Base, TimestampMixin):
    """Item master — one row per material/SKU.

    Columns mirror the uploaded material_master exactly, including the
    12-month demand history (m1..m12), the moving-average price (``map``),
    the ABC/XYZ classification, and the lead-time breakdown. Analytics read
    friendlier internal names (material_code, description, unit_cost,
    lead_time_days, category, reorder_point, abc_class) via
    ``analytics.common.materials_df()``, which derives them from these.
    """

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity: Mapped[str | None] = mapped_column(String(128), index=True)
    buyer: Mapped[str | None] = mapped_column(String(128), index=True)
    rm_material_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rough: Mapped[str | None] = mapped_column(String(64))
    material_description: Mapped[str | None] = mapped_column(String(255))
    m1: Mapped[float] = mapped_column(Float, default=0.0)
    m2: Mapped[float] = mapped_column(Float, default=0.0)
    m3: Mapped[float] = mapped_column(Float, default=0.0)
    m4: Mapped[float] = mapped_column(Float, default=0.0)
    m5: Mapped[float] = mapped_column(Float, default=0.0)
    m6: Mapped[float] = mapped_column(Float, default=0.0)
    m7: Mapped[float] = mapped_column(Float, default=0.0)
    m8: Mapped[float] = mapped_column(Float, default=0.0)
    m9: Mapped[float] = mapped_column(Float, default=0.0)
    m10: Mapped[float] = mapped_column(Float, default=0.0)
    m11: Mapped[float] = mapped_column(Float, default=0.0)
    m12: Mapped[float] = mapped_column(Float, default=0.0)
    average: Mapped[float] = mapped_column(Float, default=0.0)
    map: Mapped[float] = mapped_column(Float, default=0.0)  # moving-average price
    abc: Mapped[int | None] = mapped_column(Integer)
    xyz: Mapped[int | None] = mapped_column(Integer)
    abcxyz: Mapped[int | None] = mapped_column(Integer)
    no_of_deliveries: Mapped[int | None] = mapped_column(Integer)
    leadtime: Mapped[int | None] = mapped_column(Integer)
    transit_time: Mapped[int | None] = mapped_column(Integer)
    total_leadtime: Mapped[int | None] = mapped_column(Integer)
    max_leadtime: Mapped[float | None] = mapped_column(Float)
    sku: Mapped[int | None] = mapped_column(Integer)
    supplier: Mapped[str | None] = mapped_column(String(255))
    last_month_opening: Mapped[float] = mapped_column(Float, default=0.0)
    demand: Mapped[float] = mapped_column(Float, default=0.0)
    demand_2: Mapped[float] = mapped_column(Float, default=0.0)
    demand_3: Mapped[float] = mapped_column(Float, default=0.0)
    demand_4: Mapped[float] = mapped_column(Float, default=0.0)
    safety_stock: Mapped[float] = mapped_column(Float, default=0.0)
    refill_level: Mapped[float] = mapped_column(Float, default=0.0)
    max_level: Mapped[float] = mapped_column(Float, default=0.0)


class LocationMaster(Base, TimestampMixin):
    """Storage-location master: code -> human-readable location name."""

    __tablename__ = "location_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    storage_location: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    location: Mapped[str | None] = mapped_column(String(255))


class MovementMaster(Base, TimestampMixin):
    """Movement-type master: SAP movement code -> description."""

    __tablename__ = "movement_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mvt: Mapped[str] = mapped_column(String(16), index=True)
    description: Mapped[str | None] = mapped_column(String(255))


class SOBMaster(Base, TimestampMixin):
    """Source-of-business master: each vendor's sourcing share per material."""

    __tablename__ = "sob_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_code: Mapped[str | None] = mapped_column(String(64), index=True)
    vendor: Mapped[str | None] = mapped_column(String(64))
    vendor_name: Mapped[str | None] = mapped_column(String(255))
    share: Mapped[float] = mapped_column(Float, default=0.0)  # percent of spend
    material: Mapped[str | None] = mapped_column(String(64), index=True)
    mat: Mapped[str | None] = mapped_column(String(128))  # commodity/category
    description: Mapped[str | None] = mapped_column(String(255))


class Supplier(Base, TimestampMixin):
    """Supplier / vendor master."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(64))
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float | None] = mapped_column(Float)  # 0-100 performance score
