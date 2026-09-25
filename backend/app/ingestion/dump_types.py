"""Definitions of the daily "dumps" the business uploads.

Each dump type maps incoming columns (with flexible aliases) onto a target ORM
model. This drives both validation and the generic loader, so adding a new dump
type is just a matter of describing it here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import (
    BOMLine,
    InventorySnapshot,
    LocationMaster,
    Material,
    Movement,
    MovementMaster,
    PurchaseOrder,
    SOBMaster,
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
        description="Item master: commodity, buyer, 12-month demand history, MAP, ABC/XYZ, lead times and stock levels.",
        fields=[
            FieldSpec("commodity", ("commodity group", "sourcing group")),
            FieldSpec("buyer", ("purchaser", "planner", "buyer name")),
            FieldSpec("rm_material_code", ("material_code", "material", "item", "sku", "part_no", "material no"), required=True),
            FieldSpec("rough", ("rough code", "rgh")),
            FieldSpec("material_description", ("description", "desc", "name")),
            *[FieldSpec(f"m{i}", (), dtype="float") for i in range(1, 13)],
            FieldSpec("average", ("avg",), dtype="float"),
            FieldSpec("map", ("moving average price", "unit_cost", "cost", "price"), dtype="float"),
            FieldSpec("abc", (), dtype="int"),
            FieldSpec("xyz", (), dtype="int"),
            FieldSpec("abcxyz", (), dtype="int"),
            FieldSpec("no_of_deliveries", ("deliveries",), dtype="int"),
            FieldSpec("leadtime", ("lead time",), dtype="int"),
            FieldSpec("transit_time", (), dtype="int"),
            FieldSpec("total_leadtime", ("total lead time",), dtype="int"),
            FieldSpec("max_leadtime", ("max lead time",), dtype="float"),
            FieldSpec("sku", (), dtype="int"),
            FieldSpec("supplier", ("vendor", "supplier name")),
            FieldSpec("last_month_opening", ("opening",), dtype="float"),
            FieldSpec("demand", (), dtype="float"),
            FieldSpec("demand_2", (), dtype="float"),
            FieldSpec("demand_3", (), dtype="float"),
            FieldSpec("demand_4", (), dtype="float"),
            FieldSpec("safety_stock", ("ss", "safety"), dtype="float"),
            FieldSpec("refill_level", ("refill", "refill level", "reorder level"), dtype="float"),
            FieldSpec("max_level", ("max", "max level", "maximum"), dtype="float"),
        ],
    ),
    "location_master": DumpType(
        key="location_master",
        label="Location Master",
        model=LocationMaster,
        description="Storage-location code to human-readable name.",
        fields=[
            FieldSpec("storage_location", ("location_code", "storage loc", "sloc"), required=True),
            FieldSpec("location", ("location name", "name", "description")),
        ],
    ),
    "movement_master": DumpType(
        key="movement_master",
        label="Movement Master",
        model=MovementMaster,
        description="Movement-type code to description (Mvt Master).",
        fields=[
            FieldSpec("mvt", ("movement type", "movement", "mvt type", "mvt_type"), required=True),
            FieldSpec("description", ("desc", "movement description", "name")),
        ],
    ),
    "sob_master": DumpType(
        key="sob_master",
        label="Source of Business",
        model=SOBMaster,
        description="Vendor sourcing share per material (source-of-business split).",
        fields=[
            FieldSpec("vendor_code", ("supplier_code", "vendor no"), required=True),
            FieldSpec("vendor", ("vendor short", "vendor abbr")),
            FieldSpec("vendor_name", ("supplier name", "name")),
            FieldSpec("share", ("split", "percent", "%", "sob"), dtype="float"),
            FieldSpec("material", ("material_code", "rm_material_code", "sku"), required=True),
            FieldSpec("mat", ("commodity", "category")),
            FieldSpec("description", ("material description", "desc")),
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
    "warehouse_stock": DumpType(
        key="warehouse_stock",
        label="Warehouse Stock",
        model=WarehouseStock,
        description="Daily on-hand stock per plant × storage location × material.",
        fields=[
            FieldSpec("stock_date", ("date", "snapshot", "as of"), dtype="date"),
            FieldSpec("plant", ("warehouse", "warehouse_code", "site", "wh"), required=True),
            FieldSpec("storage_location", ("sloc", "bin", "location_code", "location")),
            FieldSpec("material", ("material_code", "sku", "rm_material_code"), required=True),
            FieldSpec("stock", ("qty", "quantity", "on hand", "soh"), dtype="float"),
            FieldSpec("value", ("stock value", "amount", "inventory value"), dtype="float"),
        ],
    ),
    "movements": DumpType(
        key="movements",
        label="Material Movements",
        model=Movement,
        description="Goods-movement transactions — receipts, issues, transfers, returns and scrap — by material and date.",
        fields=[
            FieldSpec("movement_date", ("date", "posting date", "mvt date"), dtype="date", required=True),
            FieldSpec("material_code", ("rm_material_code", "material", "sku"), required=True),
            FieldSpec("description", ("material_description", "item description")),
            FieldSpec("mvt", ("movement_type", "mvt code", "mvt no"), required=True),
            FieldSpec("mvt_type", ("mvt_description", "movement description", "mvt desc")),
            FieldSpec("qty", ("quantity",), dtype="float"),
            FieldSpec("value", ("amount", "movement value"), dtype="float"),
            FieldSpec("from_location", ("from", "source location", "issuing plant")),
            FieldSpec("to_location", ("to", "destination location", "receiving plant")),
            FieldSpec("document_no", ("document", "doc no", "reference")),
        ],
    ),
}


def get_dump_type(key: str) -> DumpType:
    if key not in DUMP_TYPES:
        raise KeyError(f"Unknown dump type '{key}'. Known: {sorted(DUMP_TYPES)}")
    return DUMP_TYPES[key]
