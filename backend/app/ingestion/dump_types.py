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
    Forecast,
    InventorySnapshot,
    Material,
    Movement,
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
            FieldSpec("material_code", ("material", "item", "sku", "part_no", "material no", "rm_material_code"), required=True),
            FieldSpec("description", ("desc", "material description", "name")),
            FieldSpec("category", ("group", "material group", "family")),
            FieldSpec("commodity", ("commodity group", "sourcing group")),
            FieldSpec("buyer", ("purchaser", "planner", "buyer name")),
            FieldSpec("uom", ("unit", "base uom", "unit of measure")),
            FieldSpec("unit_cost", ("cost", "std cost", "standard cost", "price"), dtype="float"),
            FieldSpec("currency", ("curr",)),
            FieldSpec("lead_time_days", ("lead time", "lt", "lead_time"), dtype="int"),
            FieldSpec("safety_stock", ("ss", "safety"), dtype="float"),
            FieldSpec("reorder_point", ("rop", "reorder"), dtype="float"),
            FieldSpec("refill_level", ("refill", "refill level", "reorder level"), dtype="float"),
            FieldSpec("max_level", ("max", "max level", "maximum"), dtype="float"),
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
        description="Daily snapshot of open PO lines — the incoming materials pipeline.",
        fields=[
            FieldSpec("snapshot_date", ("date", "as of", "snapshot"), dtype="date"),
            FieldSpec("po", ("po_number", "po no", "order", "purchase order"), required=True),
            FieldSpec("name", ("supplier name", "vendor name")),
            FieldSpec("material", ("material_code", "sku", "part_no"), required=True),
            FieldSpec("description", ("item description", "material description")),
            FieldSpec("po_qty", ("order_qty", "qty", "quantity", "ordered", "po qty"), dtype="float"),
            FieldSpec("po_value", ("order value", "amount", "line value"), dtype="float"),
            FieldSpec("delivery_date", ("expected_date", "delivery date", "eta", "due date", "expected", "promised date"), dtype="date"),
            FieldSpec("item", ("po_line", "line", "po item")),
            FieldSpec("po_date", ("order_date", "po date", "created", "order dt"), dtype="date"),
            FieldSpec("open_qty", ("open", "balance", "outstanding", "remaining"), dtype="float"),
            FieldSpec("net_price", ("unit_price", "price", "unit cost", "rate"), dtype="float"),
            FieldSpec("supplier_code", ("supplier", "vendor", "vendor code")),
            FieldSpec("shipping", ("shipping mode", "mode of transport", "incoterm")),
            FieldSpec("tax", ("tax code", "gst")),
            FieldSpec("created_by", ("buyer", "requested by", "raised by")),
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
    "forecast": DumpType(
        key="forecast",
        label="Forecast (M1/M2/M3)",
        model=Forecast,
        description="Rolling monthly forecast per material (next three months).",
        fields=[
            FieldSpec("material_code", ("material", "sku", "rm_material_code"), required=True),
            FieldSpec("m1_qty", ("m1", "m1_forecast", "month 1", "m1 f"), dtype="float"),
            FieldSpec("m2_qty", ("m2", "m2_forecast", "month 2", "m2 f"), dtype="float"),
            FieldSpec("m3_qty", ("m3", "m3_forecast", "month 3"), dtype="float"),
        ],
    ),
    "bom": DumpType(
        key="bom",
        label="Bill of Materials",
        model=BOMLine,
        description="Which raw materials (and how much of each) go into each finished-good product.",
        fields=[
            FieldSpec("product", ("product family", "product group", "product name")),
            FieldSpec("fg_material", ("fg_material_code", "fg", "finished good", "parent", "parent_material", "assembly"), required=True),
            FieldSpec("description", ("fg description", "fg_description", "product description")),
            FieldSpec("rm_material", ("rm_material_code", "rm", "component", "component_material", "child"), required=True),
            FieldSpec("rm_description", ("component description", "rm description", "material description")),
            FieldSpec("qty", ("qty_per", "quantity", "usage", "per"), dtype="float"),
        ],
    ),
    "inventory_snapshots": DumpType(
        key="inventory_snapshots",
        label="Inventory History",
        model=InventorySnapshot,
        description="Historical stock snapshots (qty + value) for trend analysis.",
        fields=[
            FieldSpec("material_code", ("material", "sku", "rm_material_code"), required=True),
            FieldSpec("location", ("plant", "warehouse", "site")),
            FieldSpec("snapshot_date", ("date", "month", "period", "snapshot", "stock_date"), dtype="date", required=True),
            FieldSpec("qty", ("stock", "quantity", "on hand", "soh"), dtype="float"),
            FieldSpec("value", ("stock value", "amount", "inventory value"), dtype="float"),
        ],
    ),
    "movements": DumpType(
        key="movements",
        label="Material Movements",
        model=Movement,
        description="Goods movements: receipts, issues, transfers and adjustments.",
        fields=[
            FieldSpec("material_code", ("material", "sku", "rm_material_code"), required=True),
            FieldSpec("mvt_type", ("mvt", "movement", "movement type", "type")),
            FieldSpec("description", ("desc", "text")),
            FieldSpec("qty", ("quantity", "movement qty"), dtype="float", required=True),
            FieldSpec("value", ("amount", "movement value"), dtype="float"),
            FieldSpec("movement_date", ("date", "posting date"), dtype="date"),
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
