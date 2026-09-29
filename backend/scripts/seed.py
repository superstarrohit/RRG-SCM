"""Generate a coherent sample SCM dataset and load it straight into the app
database, matching the *current* schema (see app/ingestion/dump_types.py).

Run from the backend directory:

    python -m scripts.seed

Dates are generated relative to today, so the incoming/overdue/trend analysis
stays meaningful whenever this is run (including the Docker image's
first-run seeding, on whatever day that happens to be).
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import insert

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, engine, init_db  # noqa: E402
from app.models import (  # noqa: E402
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

random.seed(42)
np.random.seed(42)

TODAY = date.today()
N_MATERIALS = 300

COMMODITIES = [
    "Bars", "Bearings", "Belts", "Brackets", "Consumables", "Couplings",
    "Engine Parts", "Fasteners", "Filters", "Flanges", "Gaskets", "Gears",
    "Hoses", "Instruments", "Joints", "Pump Parts", "Seals", "Sheets",
    "Tubing", "Valves",
]

BUYERS = [
    "Amit Sharma", "Arun Reddy", "Deepa Menon", "Kavya Iyer", "Priya Nair",
    "Rajesh Kumar", "Sneha Patel", "Vikram Singh",
]

PART_NAMES = {
    "Bars": ["Steel Bar", "Aluminium Bar", "Brass Rod"],
    "Bearings": ["Ball Bearing", "Roller Bearing", "Thrust Bearing"],
    "Belts": ["Drive Belt", "Timing Belt", "V-Belt"],
    "Brackets": ["Mounting Bracket", "Support Bracket", "L-Bracket"],
    "Consumables": ["Welding Rod", "Cutting Oil", "Abrasive Disc"],
    "Couplings": ["Flexible Coupling", "Rigid Coupling", "Jaw Coupling"],
    "Engine Parts": ["Piston Ring Set", "Cylinder Liner", "Crankshaft"],
    "Fasteners": ["Hex Bolt", "Lock Nut", "Washer Set"],
    "Filters": ["Oil Filter", "Air Filter", "Fuel Filter"],
    "Flanges": ["Weld Flange", "Slip-On Flange", "Blind Flange"],
    "Gaskets": ["Head Gasket", "Flange Gasket", "O-Ring Set"],
    "Gears": ["Spur Gear", "Bevel Gear", "Worm Gear"],
    "Hoses": ["Hydraulic Hose", "Coolant Hose", "Air Hose"],
    "Instruments": ["Pressure Gauge", "Temperature Sensor", "Flow Meter"],
    "Joints": ["Universal Joint", "Ball Joint", "Expansion Joint"],
    "Pump Parts": ["Pump Impeller", "Pump Casing", "Pump Shaft"],
    "Seals": ["Oil Seal", "Mechanical Seal", "Lip Seal"],
    "Sheets": ["Steel Sheet", "Aluminium Sheet", "Rubber Sheet"],
    "Tubing": ["Copper Tubing", "PVC Tubing", "Steel Tubing"],
    "Valves": ["Ball Valve", "Gate Valve", "Check Valve"],
}

VENDOR_PREFIXES = [
    "Indo", "Malabar", "Zenith", "Orion", "Everest", "Bharat", "Deccan",
    "Konkan", "Vindhya", "Nilgiri", "Coromandel", "Ganga", "Himal",
    "Sahyadri", "Narmada", "Godavari", "Krishna", "Cauvery", "Satpura",
    "Aravalli",
]
VENDOR_TYPES = [
    "Precision Forgings Co", "Metal Traders LLP", "Fasteners Industries",
    "Engineering Works", "Industrial Supplies", "Auto Components Ltd",
    "Alloys Pvt Ltd", "Tooling Co", "Bearings Pvt Ltd", "Hydraulics Pvt Ltd",
]

MOVEMENT_TYPES = [
    ("101", "Goods Receipt from PO"),
    ("261", "Issue to Production"),
    ("301", "Plant to Plant Transfer"),
    ("311", "Storage Location Transfer"),
    ("501", "Return to Vendor"),
    ("551", "Scrap"),
    ("601", "Delivery to Customer"),
    ("641", "Stock Transport Order"),
    ("701", "Physical Inventory Gain"),
    ("702", "Physical Inventory Loss"),
]
# Receipts and production issues dominate real movement traffic; returns,
# scrap and inventory adjustments are comparatively rare. Keeping "Goods
# Receipt" reliably ahead of "Return to Vendor" matters because the
# dashboard's "Incoming Receipts (this month)" KPI nets GR minus returns.
MOVEMENT_WEIGHTS = [30, 30, 8, 8, 3, 5, 10, 3, 2, 1]

LOCATIONS = [
    ("1000", "Main Raw Material Store"),
    ("1001", "WIP Store"),
    ("1002", "Finished Goods Store"),
    ("1003", "Quality Hold Area"),
    ("2000", "Plant B Store"),
    ("2001", "Overflow Warehouse"),
    ("2002", "Returns Store"),
    ("2003", "Scrap Yard"),
]
PLANT = "PL01"


def vendor_pool(n: int) -> list[tuple[str, str]]:
    """n distinct (vendor_code, vendor_name) pairs."""
    names = set()
    out = []
    while len(out) < n:
        name = f"{random.choice(VENDOR_PREFIXES)} {random.choice(VENDOR_TYPES)}"
        if name in names:
            continue
        names.add(name)
        out.append((f"V{1000 + len(out)}", name))
    return out


def build_materials() -> pd.DataFrame:
    rows = []
    for i in range(N_MATERIALS):
        commodity = COMMODITIES[i % len(COMMODITIES)]
        part = random.choice(PART_NAMES[commodity])
        abbr = "".join(w[0] for w in part.split())[:3].upper()
        code = f"RM-{1001 + i}"
        avg_monthly = round(random.uniform(200, 4000), 1)
        demand_hist = [round(avg_monthly * random.uniform(0.7, 1.3), 1) for _ in range(12)]
        unit_cost = round(random.uniform(0.5, 60.0), 2)
        lead_time = random.choice([7, 10, 14, 21, 28, 35, 45])
        safety_stock = round(avg_monthly * random.uniform(0.15, 0.4), 1)
        refill = round(safety_stock * random.uniform(1.6, 2.2), 1)
        maxl = round(refill * random.uniform(1.8, 2.6), 1)
        rows.append({
            "commodity": commodity,
            "buyer": random.choice(BUYERS),
            "rm_material_code": code,
            "rough": code.replace("RM", "RG"),
            "material_description": f"RRG_{part} {abbr}-{random.randint(10,99)}",
            **{f"m{j+1}": demand_hist[j] for j in range(12)},
            "average": round(sum(demand_hist) / 12, 1),
            "map": unit_cost,
            "abc": random.choices([1, 2, 3], weights=[0.2, 0.3, 0.5])[0],
            "xyz": random.choices([1, 2, 3], weights=[0.4, 0.35, 0.25])[0],
            "abcxyz": 1,
            "no_of_deliveries": random.randint(4, 60),
            "leadtime": lead_time,
            "transit_time": random.randint(1, 7),
            "total_leadtime": lead_time + random.randint(1, 7),
            "max_leadtime": lead_time * 1.3,
            "sku": i + 1,
            "supplier": "",  # actual sourcing lives in sob_master
            "last_month_opening": round(avg_monthly * random.uniform(0.8, 1.5), 1),
            "demand": demand_hist[-1],
            "demand_2": demand_hist[-2],
            "demand_3": demand_hist[-3],
            "demand_4": demand_hist[-4],
            "safety_stock": safety_stock,
            "refill_level": refill,
            "max_level": maxl,
        })
    return pd.DataFrame(rows)


def build_location_master() -> pd.DataFrame:
    return pd.DataFrame(
        [{"storage_location": c, "location": n} for c, n in LOCATIONS]
    )


def build_movement_master() -> pd.DataFrame:
    return pd.DataFrame(
        [{"mvt": c, "description": n} for c, n in MOVEMENT_TYPES]
    )


def build_sob_master(materials: pd.DataFrame, vendors: list[tuple[str, str]]) -> pd.DataFrame:
    rows = []
    for _, m in materials.iterrows():
        n_vendors = random.choice([1, 1, 2, 2, 3])
        shares = np.random.dirichlet(np.ones(n_vendors)) * 100
        picked = random.sample(vendors, n_vendors)
        for (vcode, vname), share in zip(picked, shares):
            rows.append({
                "vendor_code": vcode,
                "vendor": vname.split()[0],
                "vendor_name": vname,
                "share": round(float(share), 1),
                "material": m["rm_material_code"],
                "mat": m["commodity"],
                "description": m["material_description"],
            })
    return pd.DataFrame(rows)


def build_bom(materials: pd.DataFrame) -> pd.DataFrame:
    fg_products = [f"FG-{2001 + i}" for i in range(20)]
    fg_names = [f"{n} Assembly" for n in [
        "Engine", "Gearbox", "Chassis", "Suspension", "Braking System",
        "Steering Unit", "Cooling Module", "Fuel System", "Exhaust Unit",
        "Drive Axle", "Hydraulic Pack", "Electrical Harness", "Cabin Frame",
        "Transmission", "Differential", "Radiator Pack", "Clutch Assembly",
        "Turbo Unit", "Pump Station", "Control Panel",
    ]]
    rows = []
    codes = materials["rm_material_code"].tolist()
    descs = dict(zip(materials["rm_material_code"], materials["material_description"]))
    for fg, name in zip(fg_products, fg_names):
        comps = random.sample(codes, random.randint(4, 8))
        for rm in comps:
            rows.append({
                "product": name,
                "fg_material": fg,
                "description": name,
                "rm_material": rm,
                "rm_description": descs[rm],
                "qty": round(random.uniform(1, 10), 1),
            })
    return pd.DataFrame(rows)


def build_open_pos(materials: pd.DataFrame, vendors: list[tuple[str, str]]) -> pd.DataFrame:
    rows = []
    codes = materials["rm_material_code"].tolist()
    descs = dict(zip(materials["rm_material_code"], materials["material_description"]))
    for i in range(700):
        material = random.choice(codes)
        vcode, vname = random.choice(vendors)
        po_qty = round(random.uniform(50, 2000), 0)
        received_frac = random.choice([0, 0, 0.2, 0.5, 0.7])
        open_qty = round(po_qty * (1 - received_frac), 0)
        po_date = TODAY - timedelta(days=random.randint(1, 45))
        lead = random.choice([7, 10, 14, 21, 28, 35])
        delivery_date = po_date + timedelta(days=lead)
        rows.append({
            "snapshot_date": TODAY,
            "po": f"45{100000 + i}",
            "name": vname,
            "material": material,
            "description": descs[material],
            "po_qty": po_qty,
            "po_value": round(po_qty * random.uniform(0.5, 60.0), 2),
            "delivery_date": delivery_date,
            "item": "10",
            "po_date": po_date,
            "open_qty": open_qty,
            "net_price": round(random.uniform(0.5, 60.0), 2),
            "supplier_code": vcode,
            "shipping": random.choice(["Road", "Rail", "Air", "Sea"]),
            "tax": "GST18",
            "created_by": random.choice(BUYERS),
        })
    return pd.DataFrame(rows)


def build_inventory_snapshots(materials: pd.DataFrame) -> pd.DataFrame:
    rows = []
    codes = materials["rm_material_code"].tolist()
    costs = dict(zip(materials["rm_material_code"], materials["map"]))
    base_qty = {c: random.uniform(2000, 40000) for c in codes}

    # Weekly history for the full ~2-year range, then daily for the last 60 days.
    weekly_dates = [TODAY - timedelta(days=d) for d in range(0, 730, 7)]
    daily_dates = [TODAY - timedelta(days=d) for d in range(0, 60)]
    all_dates = sorted(set(weekly_dates) | set(daily_dates))

    for d in all_dates:
        for c in codes:
            drift = 1 + 0.15 * np.sin((TODAY - d).days / 45.0 + hash(c) % 10)
            noise = random.uniform(0.9, 1.1)
            qty = max(0.0, base_qty[c] * drift * noise)
            rows.append({
                "material_code": c,
                "location": "Main Warehouse",
                "snapshot_date": d,
                "qty": round(qty, 1),
                "value": round(qty * costs[c], 2),
            })
    return pd.DataFrame(rows)


def build_warehouse_stock(materials: pd.DataFrame) -> pd.DataFrame:
    rows = []
    codes = materials["rm_material_code"].tolist()
    costs = dict(zip(materials["rm_material_code"], materials["map"]))
    for d_off in range(0, 30):
        d = TODAY - timedelta(days=d_off)
        for loc, _ in LOCATIONS[:4]:
            for c in codes:
                qty = max(0.0, random.uniform(0, 8000))
                rows.append({
                    "stock_date": d,
                    "plant": PLANT,
                    "storage_location": loc,
                    "material": c,
                    "stock": round(qty, 1),
                    "value": round(qty * costs[c], 2),
                })
    return pd.DataFrame(rows)


def build_movements(materials: pd.DataFrame) -> pd.DataFrame:
    rows = []
    codes = materials["rm_material_code"].tolist()
    descs = dict(zip(materials["rm_material_code"], materials["material_description"]))
    costs = dict(zip(materials["rm_material_code"], materials["map"]))
    for d_off in range(0, 180):
        d = TODAY - timedelta(days=d_off)
        for _ in range(random.randint(10, 25)):
            c = random.choice(codes)
            mvt, mvt_type = random.choices(MOVEMENT_TYPES, weights=MOVEMENT_WEIGHTS)[0]
            qty = round(random.uniform(10, 500), 1)
            rows.append({
                "movement_date": d,
                "material_code": c,
                "description": descs[c],
                "mvt": mvt,
                "mvt_type": mvt_type,
                "qty": qty,
                "value": round(qty * costs[c], 2),
                "from_location": random.choice(LOCATIONS)[0],
                "to_location": random.choice(LOCATIONS)[0],
                "document_no": f"DOC{d_off:04d}{random.randint(1000,9999)}",
            })
    return pd.DataFrame(rows)


def bulk_load(model, df: pd.DataFrame) -> None:
    if df.empty:
        return
    records = df.replace({np.nan: None}).to_dict(orient="records")
    with engine.begin() as conn:
        conn.execute(insert(model.__table__), records)
    print(f"  loaded {model.__tablename__:<20} -> {len(records)} rows")


def main() -> None:
    init_db()

    print("Generating sample data...")
    materials = build_materials()
    vendors = vendor_pool(30)

    print("Loading into the app database...")
    session = SessionLocal()
    try:
        for model in (
            Material, LocationMaster, MovementMaster, SOBMaster,
            BOMLine, PurchaseOrder, InventorySnapshot, WarehouseStock, Movement,
        ):
            session.execute(model.__table__.delete())
        session.commit()
    finally:
        session.close()

    bulk_load(Material, materials)
    bulk_load(LocationMaster, build_location_master())
    bulk_load(MovementMaster, build_movement_master())
    bulk_load(SOBMaster, build_sob_master(materials, vendors))
    bulk_load(BOMLine, build_bom(materials))
    bulk_load(PurchaseOrder, build_open_pos(materials, vendors))
    bulk_load(InventorySnapshot, build_inventory_snapshots(materials))
    bulk_load(WarehouseStock, build_warehouse_stock(materials))
    bulk_load(Movement, build_movements(materials))

    print("Done.")


if __name__ == "__main__":
    main()
