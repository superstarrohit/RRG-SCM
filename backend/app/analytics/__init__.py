"""Analytics modules for the SCM platform."""
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

__all__ = [
    "incoming_materials",
    "material_planning",
    "sourcing",
    "costing",
    "fg_planning",
    "overview",
    "stock_monitoring",
    "inventory_monitoring",
    "vendor_receipts",
    "movements",
    "forecasting",
]
