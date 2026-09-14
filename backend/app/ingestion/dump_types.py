"""Definitions of the daily "dumps" the business uploads.

Each dump type maps incoming columns (with flexible aliases) onto a target ORM
model. This drives both validation and the generic loader, so adding a new dump
type is just a matter of describing it here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import (
    BOMLine,
    Demand,
    Material,
    ProductionPlan,
    PurchaseOrder,
    Receipt,
    Stock,
    Supplier,
    WarehouseStock,
)


@dataclass(frozen=True)
class FieldSpec:
    name: str  # canonical column / model attribute
    aliases: tuple[str, ...] = ()  # accepted source header variants
    dtype: str = "str"  # str | float | int | date
    required: bool = False


@dataclass(frozen=True)
class DumpType:
    key: str
    label: str
    model: type
    fields: list[FieldSpec]
    description: str = ""

    def all_names(self) -> set[str]:
        return {f.name for f in self.fields}


DUMP_TYPES: dict[str, DumpType] = {
    "materials": DumpType(
        key="materials",
        label="Material Master",
        model=Material,
        description="Item master with planning parameters and unit cost.",
        fields=[
            FieldSpec("material_code", ("material", "item", "sku", "part_no", "material no"), required=True),
            FieldSpec("description", ("desc", "material description", "name")),
            FieldSpec("category", ("group", "material group", "family")),
            FieldSpec("uom", ("unit", "base uom", "unit of measure")),
            FieldSpec("unit_cost", ("cost", "std cost", "standard cost", "price"), dtype="float"),
            FieldSpec("currency", ("curr",)),
            FieldSpec("lead_time_days", ("lead time", "lt", "lead_time"), dtype="int"),
            FieldSpec("safety_stock", ("ss", "safety"), dtype="float"),
            FieldSpec("reorder_point", ("rop", "reorder"), dtype="float"),
            FieldSpec("min_order_qty", ("moq", "min order"), dtype="float"),
            FieldSpec("abc_class", ("abc", "class")),
        ],
    ),
    "suppliers": DumpType(
        key="suppliers",
        label="Supplier Master",
        model=Supplier,
        description="Vendor master with lead time and performance rating.",
        fields=[
            FieldSpec("supplier_code", ("supplier", "vendor", "vendor code", "supplier no"), required=True),
            FieldSpec("name", ("supplier name", "vendor name")),
            FieldSpec("country", ("nation",)),
            FieldSpec("lead_time_days", ("lead time", "lt"), dtype="int"),
            FieldSpec("rating", ("score", "performance"), dtype="float"),
        ],
    ),
    "stock": DumpType(
        key="stock",
        label="Stock Snapshot",
        model=Stock,
        description="Current on-hand stock per material.",
        fields=[
            FieldSpec("material_code", ("material", "item", "sku", "part_no"), required=True),
            FieldSpec("qty_on_hand", ("qty", "on hand", "stock", "quantity", "soh"), dtype="float", required=True),
            FieldSpec("qty_blocked", ("blocked", "blocked qty"), dtype="float"),
            FieldSpec("as_of_date", ("date", "snapshot date", "as of"), dtype="date"),
        ],
    ),
    "warehouse_stock": DumpType(
        key="warehouse_stock",
        label="Warehouse Stock",
        model=WarehouseStock,
        description="Stock by warehouse / storage location.",
        fields=[
            FieldSpec("warehouse_code", ("warehouse", "plant", "wh", "site"), required=True),
            FieldSpec("material_code", ("material", "item", "sku"), required=True),
            FieldSpec("location", ("bin", "storage location", "sloc")),
            FieldSpec("qty", ("quantity", "stock", "on hand"), dtype="float", required=True),
            FieldSpec("as_of_date", ("date", "snapshot date"), dtype="date"),
        ],
    ),
    "open_pos": DumpType(
        key="open_pos",
        label="Open Purchase Orders",
        model=PurchaseOrder,
        description="Open PO lines — the incoming materials pipeline.",
        fields=[
            FieldSpec("po_number", ("po", "po no", "order", "purchase order"), required=True),
            FieldSpec("po_line", ("line", "item", "po item")),
            FieldSpec("material_code", ("material", "sku", "part_no"), required=True),
            FieldSpec("supplier_code", ("supplier", "vendor")),
            FieldSpec("order_qty", ("qty", "quantity", "ordered", "po qty"), dtype="float"),
            FieldSpec("received_qty", ("received", "grn qty", "delivered"), dtype="float"),
            FieldSpec("open_qty", ("open", "balance", "outstanding", "remaining"), dtype="float"),
            FieldSpec("unit_price", ("price", "unit cost", "rate"), dtype="float"),
            FieldSpec("currency", ("curr",)),
            FieldSpec("order_date", ("po date", "created", "order dt"), dtype="date"),
            FieldSpec("expected_date", ("delivery date", "eta", "due date", "expected", "promised date"), dtype="date"),
        ],
    ),
    "receipts": DumpType(
        key="receipts",
        label="Goods Receipts (GRN)",
        model=Receipt,
        description="Received quantities against POs.",
        fields=[
            FieldSpec("receipt_id", ("grn", "grn no", "receipt", "document")),
            FieldSpec("po_number", ("po", "po no", "order")),
            FieldSpec("material_code", ("material", "sku"), required=True),
            FieldSpec("supplier_code", ("supplier", "vendor")),
            FieldSpec("qty", ("received", "quantity", "grn qty"), dtype="float", required=True),
            FieldSpec("unit_price", ("price", "rate"), dtype="float"),
            FieldSpec("receipt_date", ("date", "grn date", "posting date"), dtype="date"),
        ],
    ),
    "demand": DumpType(
        key="demand",
        label="Demand / Requirements",
        model=Demand,
        description="Forecast, sales-order, or production demand per period.",
        fields=[
            FieldSpec("material_code", ("material", "sku"), required=True),
            FieldSpec("period", ("date", "month", "week", "bucket"), dtype="date"),
            FieldSpec("qty", ("quantity", "demand", "requirement"), dtype="float", required=True),
            FieldSpec("demand_type", ("type", "source")),
        ],
    ),
    "bom": DumpType(
        key="bom",
        label="Bill of Materials",
        model=BOMLine,
        description="Component structure for finished goods.",
        fields=[
            FieldSpec("parent_material", ("parent", "fg", "finished good", "assembly"), required=True),
            FieldSpec("component_material", ("component", "child", "material"), required=True),
            FieldSpec("qty_per", ("qty", "quantity", "usage", "per"), dtype="float"),
            FieldSpec("scrap_pct", ("scrap", "scrap %", "waste"), dtype="float"),
        ],
    ),
    "production_plan": DumpType(
        key="production_plan",
        label="Production Plan (FG)",
        model=ProductionPlan,
        description="Planned finished-goods production per period.",
        fields=[
            FieldSpec("material_code", ("material", "fg", "product"), required=True),
            FieldSpec("period", ("date", "month", "week"), dtype="date"),
            FieldSpec("planned_qty", ("qty", "quantity", "plan", "planned"), dtype="float", required=True),
        ],
    ),
}


def get_dump_type(key: str) -> DumpType:
    if key not in DUMP_TYPES:
        raise KeyError(f"Unknown dump type '{key}'. Known: {sorted(DUMP_TYPES)}")
    return DUMP_TYPES[key]
