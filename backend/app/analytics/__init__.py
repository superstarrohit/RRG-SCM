"""Analytics modules for the SCM platform."""
from app.analytics import (
    costing,
    fg_planning,
    incoming_materials,
    inventory_monitoring,
    material_planning,
    overview,
    sourcing,
    stock_monitoring,
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
]
