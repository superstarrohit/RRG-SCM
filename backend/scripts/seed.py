"""Generate coherent sample SCM data, write it to sample_data/, and load it.

Run from the backend directory:

    python -m scripts.seed            # generate CSVs + load into the app DB
    python -m scripts.seed --files    # only write the sample CSV files
    python -m scripts.seed --load     # only load existing sample CSVs into DB

Dates are generated relative to today so the incoming/overdue analysis is
meaningful in the demo.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# Make "app" importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db  # noqa: E402
from app.ingestion import load_dataframe  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
TODAY = date.today()


def d(offset_days: int) -> str:
    return (TODAY + timedelta(days=offset_days)).isoformat()


def build_frames() -> dict[str, pd.DataFrame]:
    materials = pd.DataFrame(
        [
            # code, desc, category, uom, cost, lt, ss, rop, moq, abc
            ("RM-1001", "Steel Sheet 2mm", "Raw Material", "KG", 3.20, 21, 500, 800, 1000, "A"),
            ("RM-1002", "Aluminium Bar", "Raw Material", "KG", 5.10, 28, 300, 500, 500, "A"),
            ("RM-1003", "Copper Wire", "Raw Material", "M", 1.75, 14, 1000, 1500, 2000, "B"),
            ("RM-1004", "Plastic Granule", "Raw Material", "KG", 0.95, 10, 800, 1200, 1000, "C"),
            ("CP-2001", "Bearing 6203", "Component", "EA", 2.40, 30, 200, 400, 500, "B"),
            ("CP-2002", "Fastener M6", "Component", "EA", 0.05, 7, 5000, 8000, 10000, "C"),
            ("CP-2003", "Control Board", "Component", "EA", 18.50, 45, 50, 120, 100, "A"),
            ("CP-2004", "Gasket Set", "Component", "EA", 1.20, 21, 300, 500, 500, "C"),
            ("SA-3001", "Motor Assembly", "Sub-Assembly", "EA", 42.00, 14, 20, 40, 25, "A"),
            ("FG-5001", "Pump Unit A", "Finished Good", "EA", 0.0, 0, 10, 20, 10, "A"),
            ("FG-5002", "Pump Unit B", "Finished Good", "EA", 0.0, 0, 5, 15, 10, "A"),
            ("PK-4001", "Carton Box", "Packaging", "EA", 0.30, 7, 2000, 3000, 5000, "C"),
        ],
        columns=["material_code", "description", "category", "uom", "unit_cost",
                 "lead_time_days", "safety_stock", "reorder_point", "min_order_qty", "abc_class"],
    )

    suppliers = pd.DataFrame(
        [
            ("SUP-001", "Apex Metals Ltd", "USA", 21, 88),
            ("SUP-002", "Global Components Co", "Germany", 30, 76),
            ("SUP-003", "Eastern Polymers", "India", 14, 92),
            ("SUP-004", "Precision Parts Inc", "Japan", 45, 81),
        ],
        columns=["supplier_code", "name", "country", "lead_time_days", "rating"],
    )

    stock = pd.DataFrame(
        [
            ("RM-1001", 620, 0), ("RM-1002", 210, 20), ("RM-1003", 1450, 0),
            ("RM-1004", 300, 0), ("CP-2001", 180, 10), ("CP-2002", 12000, 0),
            ("CP-2003", 35, 0), ("CP-2004", 260, 0), ("SA-3001", 8, 0),
            ("FG-5001", 14, 0), ("FG-5002", 6, 0), ("PK-4001", 4200, 0),
        ],
        columns=["material_code", "qty_on_hand", "qty_blocked"],
    )
    stock["as_of_date"] = d(0)

    warehouse_stock = pd.DataFrame(
        [
            ("WH-NORTH", "RM-1001", "A-01", 400), ("WH-SOUTH", "RM-1001", "B-12", 220),
            ("WH-NORTH", "CP-2003", "C-04", 35), ("WH-NORTH", "FG-5001", "D-01", 14),
            ("WH-SOUTH", "FG-5002", "D-08", 6), ("WH-NORTH", "CP-2001", "C-11", 120),
            ("WH-SOUTH", "CP-2001", "B-03", 60),
        ],
        columns=["warehouse_code", "material_code", "location", "qty"],
    )
    warehouse_stock["as_of_date"] = d(0)

    # Open POs — mix of overdue, this-week, this-month, future. Uses friendly
    # headers to exercise the column-alias mapping.
    open_pos = pd.DataFrame(
        [
            ("PO-9001", "10", "RM-1001", "SUP-001", 2000, 0, 2000, 3.10, d(-12)),
            ("PO-9002", "10", "RM-1002", "SUP-001", 800, 300, 500, 5.00, d(-5)),
            ("PO-9003", "10", "CP-2003", "SUP-002", 150, 0, 150, 18.20, d(-2)),
            ("PO-9004", "10", "CP-2001", "SUP-004", 500, 0, 500, 2.35, d(3)),
            ("PO-9005", "20", "RM-1003", "SUP-003", 2500, 500, 2000, 1.70, d(6)),
            ("PO-9006", "10", "CP-2002", "SUP-002", 10000, 0, 10000, 0.048, d(9)),
            ("PO-9007", "10", "RM-1004", "SUP-003", 1500, 0, 1500, 0.92, d(15)),
            ("PO-9008", "10", "SA-3001", "SUP-004", 30, 0, 30, 41.00, d(20)),
            ("PO-9009", "10", "CP-2003", "SUP-002", 120, 0, 120, 18.60, d(28)),
            ("PO-9010", "10", "RM-1001", "SUP-001", 3000, 0, 3000, 3.05, d(40)),
            ("PO-9011", "10", "CP-2004", "SUP-004", 500, 0, 500, 1.15, d(45)),
            ("PO-9012", "10", "PK-4001", "SUP-003", 5000, 0, 5000, 0.29, d(2)),
            ("PO-9013", "20", "RM-1002", "SUP-004", 600, 0, 600, 5.25, d(-8)),
            ("PO-9014", "10", "CP-2001", "SUP-002", 400, 0, 400, 2.50, d(35)),
        ],
        columns=["PO No", "Line", "Material", "Vendor", "Order Qty", "Received",
                 "Open Qty", "Unit Price", "ETA"],
    )

    receipts = pd.DataFrame(
        [
            ("GRN-5001", "PO-9002", "RM-1002", "SUP-001", 300, 5.00, d(-10)),
            ("GRN-5002", "PO-9005", "RM-1003", "SUP-003", 500, 1.70, d(-7)),
            ("GRN-4990", "PO-8990", "CP-2001", "SUP-004", 500, 2.30, d(-40)),
            ("GRN-4991", "PO-8991", "CP-2001", "SUP-002", 400, 2.55, d(-38)),
            ("GRN-4992", "PO-8992", "RM-1001", "SUP-001", 2000, 3.15, d(-25)),
            ("GRN-4993", "PO-8993", "CP-2003", "SUP-002", 100, 18.40, d(-20)),
        ],
        columns=["GRN No", "PO", "Material", "Vendor", "Received", "Price", "Date"],
    )

    demand = pd.DataFrame(
        [
            ("RM-1001", d(30), 2500, "forecast"), ("RM-1002", d(30), 900, "forecast"),
            ("RM-1003", d(30), 1800, "forecast"), ("CP-2003", d(30), 200, "forecast"),
            ("CP-2001", d(30), 700, "forecast"), ("FG-5001", d(30), 40, "so"),
            ("FG-5002", d(30), 25, "so"), ("SA-3001", d(30), 35, "prod"),
        ],
        columns=["material_code", "period", "qty", "demand_type"],
    )

    bom = pd.DataFrame(
        [
            # FG-5001 = Pump Unit A
            ("FG-5001", "SA-3001", 1, 0),
            ("FG-5001", "CP-2004", 2, 5),
            ("FG-5001", "PK-4001", 1, 0),
            ("FG-5001", "CP-2002", 12, 2),
            # FG-5002 = Pump Unit B
            ("FG-5002", "SA-3001", 1, 0),
            ("FG-5002", "CP-2003", 1, 0),
            ("FG-5002", "CP-2004", 3, 5),
            ("FG-5002", "PK-4001", 1, 0),
            # SA-3001 = Motor Assembly (sub-assembly -> raw)
            ("SA-3001", "RM-1002", 0.8, 3),
            ("SA-3001", "CP-2001", 2, 1),
            ("SA-3001", "RM-1003", 5, 2),
        ],
        columns=["parent_material", "component_material", "qty_per", "scrap_pct"],
    )

    production_plan = pd.DataFrame(
        [
            ("FG-5001", d(30), 50),
            ("FG-5002", d(30), 30),
            ("FG-5001", d(60), 40),
        ],
        columns=["material_code", "period", "planned_qty"],
    )

    return {
        "materials": materials,
        "suppliers": suppliers,
        "stock": stock,
        "warehouse_stock": warehouse_stock,
        "open_pos": open_pos,
        "receipts": receipts,
        "demand": demand,
        "bom": bom,
        "production_plan": production_plan,
    }


def write_files(frames: dict[str, pd.DataFrame]) -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in frames.items():
        path = SAMPLE_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"  wrote {path.relative_to(SAMPLE_DIR.parent)}  ({len(df)} rows)")


def load(frames: dict[str, pd.DataFrame]) -> None:
    init_db()
    db = SessionLocal()
    try:
        for name, df in frames.items():
            report = load_dataframe(
                db, df, name, source_type="file",
                source_name=f"sample_data/{name}.csv", mode="replace",
            )
            print(f"  loaded {name:16s} -> {report['rows_ingested']} rows "
                  f"[{report['status']}]")
    finally:
        db.close()


def load_from_files() -> None:
    frames = {p.stem: pd.read_csv(p) for p in sorted(SAMPLE_DIR.glob("*.csv"))}
    load(frames)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed RRG-SCM sample data.")
    parser.add_argument("--files", action="store_true", help="only write CSV files")
    parser.add_argument("--load", action="store_true", help="only load existing CSVs")
    args = parser.parse_args()

    if args.load:
        print("Loading sample CSVs into the app database...")
        load_from_files()
        return

    frames = build_frames()
    print("Writing sample CSV files...")
    write_files(frames)
    if not args.files:
        print("Loading sample data into the app database...")
        load(frames)
    print("Done.")


if __name__ == "__main__":
    main()
