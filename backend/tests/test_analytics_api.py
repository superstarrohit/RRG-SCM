"""End-to-end API tests: ingest via upload, then run analytics."""
from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd


def _csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()


def _upload(client, dump_type: str, df: pd.DataFrame):
    return client.post(
        "/api/ingest/file",
        data={"dump_type": dump_type, "mode": "replace"},
        files={"file": (f"{dump_type}.csv", _csv_bytes(df), "text/csv")},
    )


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_dump_types_metadata(client):
    r = client.get("/api/meta/dump-types")
    assert r.status_code == 200
    keys = {d["key"] for d in r.json()}
    assert {"open_pos", "materials", "bom", "inventory_snapshots"} <= keys


def test_upload_and_incoming_analysis(client):
    today = date.today()

    materials = pd.DataFrame(
        {"Material": ["M1", "M2"], "Description": ["Part 1", "Part 2"],
         "Category": ["Raw", "Comp"], "Cost": [10.0, 5.0]}
    )
    assert _upload(client, "materials", materials).status_code == 200

    pos = pd.DataFrame(
        {
            "PO No": ["P1", "P2", "P3"],
            "Material": ["M1", "M2", "M1"],
            "Vendor": ["V1", "V2", "V1"],
            "Open Qty": [50, 200, 30],
            "Unit Price": [10.0, 5.0, 10.0],
            "ETA": [
                (today - timedelta(days=5)).isoformat(),  # overdue
                (today + timedelta(days=3)).isoformat(),   # this week
                (today + timedelta(days=40)).isoformat(),  # future
            ],
        }
    )
    assert _upload(client, "open_pos", pos).status_code == 200

    r = client.get("/api/analytics/incoming")
    assert r.status_code == 200
    data = r.json()
    assert data["empty"] is False
    k = data["kpis"]
    assert k["open_lines"] == 3
    # value = 50*10 + 200*5 + 30*10 = 500 + 1000 + 300 = 1800
    assert k["open_value"] == 1800.0
    assert k["overdue_lines"] == 1
    assert k["overdue_value"] == 500.0
    statuses = {s["status"] for s in data["status_breakdown"]}
    assert "overdue" in statuses and "due_this_week" in statuses


def test_incoming_empty_state(client):
    r = client.get("/api/analytics/incoming")
    assert r.status_code == 200
    assert r.json()["empty"] is True


def test_bad_dump_type_rejected(client):
    r = _upload(client, "not_a_type", pd.DataFrame({"a": [1]}))
    assert r.status_code == 400


def test_inventory_timeseries_drilldown(client):
    materials = pd.DataFrame(
        {"Material": ["M1", "M2"], "Description": ["Part 1", "Part 2"],
         "Buyer": ["Alice", "Bob"], "Commodity": ["Raw", "Comp"]}
    )
    assert _upload(client, "materials", materials).status_code == 200

    # Two months of snapshots; each period is represented by its last date.
    snaps = pd.DataFrame(
        {
            "Material": ["M1", "M2", "M1", "M2", "M1", "M2"],
            "Date": ["2025-01-15", "2025-01-15",
                     "2025-01-31", "2025-01-31",
                     "2025-02-28", "2025-02-28"],
            "On Hand": [10, 20, 12, 22, 15, 25],
            "Inventory Value": [100, 200, 120, 220, 150, 250],
        }
    )
    assert _upload(client, "inventory_snapshots", snaps).status_code == 200

    # Monthly: Jan uses the 31st (120+220=340), Feb uses the 28th (150+250=400).
    r = client.get("/api/analytics/inventory-timeseries", params={"grain": "monthly"})
    assert r.status_code == 200
    data = r.json()
    assert data["grain"] == "monthly"
    pts = {p["label"]: p["value"] for p in data["points"]}
    assert pts["Jan 2025"] == 340.0
    assert pts["Feb 2025"] == 400.0

    # Daily keeps every snapshot date.
    r = client.get("/api/analytics/inventory-timeseries", params={"grain": "daily"})
    assert len(r.json()["points"]) == 3

    # Buyer slicer scopes the series to that buyer's materials only (M1 → Alice).
    r = client.get("/api/analytics/inventory-timeseries",
                   params={"grain": "monthly", "buyer": "Alice"})
    pts = {p["label"]: p["value"] for p in r.json()["points"]}
    assert pts["Jan 2025"] == 120.0
    assert pts["Feb 2025"] == 150.0

    # Drilldown: start/end bound the window; points carry period bounds.
    r = client.get("/api/analytics/inventory-timeseries",
                   params={"grain": "monthly", "start": "2025-02-01", "end": "2025-02-28"})
    pts = r.json()["points"]
    assert [p["label"] for p in pts] == ["Feb 2025"]
    assert pts[0]["start"] == "2025-02-01" and pts[0]["end"] == "2025-02-28"


def test_supplier_slicer_and_filter(client):
    materials = pd.DataFrame(
        {"Material": ["M1", "M2"], "Description": ["Part 1", "Part 2"],
         "Buyer": ["Alice", "Bob"]}
    )
    assert _upload(client, "materials", materials).status_code == 200

    sob = pd.DataFrame(
        {"vendor_code": ["V1", "V2"], "vendor_name": ["Acme Ltd", "Globex"],
         "material": ["M1", "M2"], "share": [100, 100]}
    )
    assert _upload(client, "sob_master", sob).status_code == 200

    snaps = pd.DataFrame(
        {"Material": ["M1", "M2"], "Date": ["2025-01-31", "2025-01-31"],
         "Inventory Value": [500, 900]}
    )
    assert _upload(client, "inventory_snapshots", snaps).status_code == 200

    # The supplier slicer is now populated from the SOB master.
    opts = client.get("/api/meta/slicers").json()["supplier"]
    codes = {o["code"] for o in opts}
    assert {"V1", "V2"} <= codes

    # Filtering by a vendor scopes the dashboard to that vendor's materials.
    d = client.get("/api/analytics/overview", params={"supplier": "V1"}).json()
    assert d["kpis"]["materials"] == 1
    assert d["kpis"]["inventory_value"] == 500.0


def test_inventory_ribbon_drilldown(client):
    materials = pd.DataFrame(
        {"Material": ["M1", "M2"], "Description": ["Part 1", "Part 2"],
         "Buyer": ["Alice", "Bob"]}
    )
    assert _upload(client, "materials", materials).status_code == 200

    # Snapshots across two years, two quarters within 2025, to exercise
    # Year -> Quarter -> Month drilldown.
    snaps = pd.DataFrame(
        {
            "Material": ["M1", "M2", "M1", "M2", "M1", "M2"],
            "Date": ["2024-12-31", "2024-12-31",
                     "2025-03-31", "2025-03-31",
                     "2025-06-30", "2025-06-30"],
            "Inventory Value": [100, 200, 150, 250, 180, 300],
        }
    )
    assert _upload(client, "inventory_snapshots", snaps).status_code == 200

    # Top level: by year, buyer-wise series.
    r = client.get("/api/analytics/inventory-ribbon", params={"grain": "yearly"})
    assert r.status_code == 200
    data = r.json()
    assert data["grain"] == "yearly"
    labels = [p["label"] for p in data["points"]]
    assert labels == ["2024", "2025"]
    series = {s["name"]: s["values"] for s in data["series"]}
    assert series["Alice"] == [100.0, 180.0]   # M1 -> Alice, last snapshot per year
    assert series["Bob"] == [200.0, 300.0]     # M2 -> Bob

    # Drill into 2025: bounded quarterly view shows both quarters.
    y2025 = next(p for p in data["points"] if p["label"] == "2025")
    r = client.get("/api/analytics/inventory-ribbon",
                   params={"grain": "quarterly", "start": y2025["start"], "end": y2025["end"]})
    data = r.json()
    labels = [p["label"] for p in data["points"]]
    assert labels == ["Q1 2025", "Q2 2025"]
    series = {s["name"]: s["values"] for s in data["series"]}
    assert series["Alice"] == [150.0, 180.0]
    assert series["Bob"] == [250.0, 300.0]

    # Buyer slicer scopes the ribbon to a single series.
    r = client.get("/api/analytics/inventory-ribbon",
                   params={"grain": "yearly", "buyer": "Alice"})
    names = {s["name"] for s in r.json()["series"]}
    assert names == {"Alice"}


def test_overview_date_range_filter(client):
    materials = pd.DataFrame(
        {"Material": ["M1", "M2"], "Description": ["Part 1", "Part 2"],
         "Buyer": ["Alice", "Bob"]}
    )
    assert _upload(client, "materials", materials).status_code == 200

    snaps = pd.DataFrame(
        {
            "Material": ["M1", "M2", "M1", "M2"],
            "Date": ["2025-06-30", "2025-06-30", "2025-12-31", "2025-12-31"],
            "Inventory Value": [100, 200, 150, 250],
        }
    )
    assert _upload(client, "inventory_snapshots", snaps).status_code == 200

    # Unfiltered: "today" is the true latest snapshot (Dec).
    d = client.get("/api/analytics/overview").json()
    assert d["as_of"] == "2025-12-31"
    assert d["kpis"]["inventory_value"] == 400.0

    # A date-range filter's end date narrows "today" to the latest snapshot
    # at or before it, and the resolved date is reflected back in as_of.
    d = client.get("/api/analytics/overview", params={"end": "2025-09-30"}).json()
    assert d["as_of"] == "2025-06-30"
    assert d["kpis"]["inventory_value"] == 300.0

    # A window entirely before any data has nothing to show.
    d = client.get("/api/analytics/overview",
                   params={"start": "2024-01-01", "end": "2024-06-30"}).json()
    assert d["kpis"]["inventory_value"] == 0.0
    assert d["inventory_by_buyer"] == []


def test_costing_description_search_filter(client):
    materials = pd.DataFrame(
        {"Material": ["FG1", "FG2"], "Description": ["Widget Assembly", "Gasket Assembly"],
         "Cost": [10.0, 5.0]}
    )
    assert _upload(client, "materials", materials).status_code == 200

    bom = pd.DataFrame(
        {"fg_material": ["FG1", "FG2"], "rm_material": ["RM1", "RM2"], "qty": [2, 3]}
    )
    assert _upload(client, "bom", bom).status_code == 200

    # Unfiltered: both finished goods show up.
    d = client.get("/api/analytics/costing").json()
    codes = {r["material_code"] for r in d["cost_rollup"]}
    assert codes == {"FG1", "FG2"}

    # The description search box narrows the roll-up (was previously a dead
    # parameter on this endpoint — accepted but never applied).
    d = client.get("/api/analytics/costing", params={"q": "gasket"}).json()
    codes = {r["material_code"] for r in d["cost_rollup"]}
    assert codes == {"FG2"}


def test_material_planning_report(client):
    materials = pd.DataFrame({
        "Material": ["M-SAFE", "M-STOCKOUT", "M-RISK", "M-ALARM", "M-EXCESS", "M-OPENPO"],
        "Description": ["Safe Item", "Stockout Item", "Risk Item", "Alarm Item", "Excess Item", "Open PO Item"],
        "Commodity": ["Raw", "Raw", "Comp", "Comp", "Raw", "Raw"],
        "Buyer": ["Alice", "Bob", "Alice", "Bob", "Alice", "Alice"],
        "Safety Stock": [50, 10, 10, 10, 10, 20],
        "Refill Level": [100, 20, 20, 20, 20, 0],
        "Max Level": [500, 100, 100, 100, 100, 0],
        "Demand": [200, 50, 10, 10, 10, 100],
        "Demand 2": [150, 0, 0, 0, 0, 0],
        "Demand 3": [100, 0, 0, 0, 0, 0],
        "Demand 4": [50, 0, 0, 0, 0, 0],
    })
    assert _upload(client, "materials", materials).status_code == 200

    snaps = pd.DataFrame({
        "Material": ["M-SAFE", "M-RISK", "M-ALARM", "M-EXCESS", "M-OPENPO"],
        "Date": ["2025-06-30"] * 5,
        "On Hand": [300, 5, 15, 600, 50],
        "Inventory Value": [3000, 50, 150, 6000, 500],
    })
    assert _upload(client, "inventory_snapshots", snaps).status_code == 200

    wh = pd.DataFrame({
        "Material": ["M-SAFE"],
        "Plant": ["P1"],
        "Storage Location": ["L1"],
        "Stock": [120],
        "Date": ["2025-06-30"],
    })
    assert _upload(client, "warehouse_stock", wh).status_code == 200

    pos = pd.DataFrame({
        "PO No": ["PO-1"], "Material": ["M-OPENPO"], "Vendor": ["V1"],
        "Open Qty": [30], "ETA": ["2025-07-15"],
    })
    assert _upload(client, "open_pos", pos).status_code == 200

    r = client.get("/api/analytics/planning")
    assert r.status_code == 200
    data = r.json()
    assert data["empty"] is False
    rows = {row["material_code"]: row for row in data["rows"]}

    # Status classification: Stockout (=0) > Risk (< safety) > Alarm (< refill)
    # > Excess (> max), else Safe.
    assert rows["M-STOCKOUT"]["status"] == "Stockout"
    assert rows["M-RISK"]["status"] == "Risk"
    assert rows["M-ALARM"]["status"] == "Alarm"
    assert rows["M-EXCESS"]["status"] == "Excess"
    assert rows["M-SAFE"]["status"] == "Safe"

    safe = rows["M-SAFE"]
    assert safe["current_stock"] == 300.0
    assert safe["warehouse_stock"] == 120.0  # sourced independently from the warehouse-stock dump
    assert safe["reach_days"] == 30.0  # 300 / (200 demand / 20 working days)
    # Rolling M1-M4 net requirement, each month required to still leave
    # safety stock on hand at its end.
    assert safe["m1_demand"] == 200.0 and safe["m1_shortage"] == 0.0
    assert safe["m2_demand"] == 150.0 and safe["m2_shortage"] == 100.0
    assert safe["m3_demand"] == 100.0 and safe["m3_shortage"] == 100.0
    assert safe["m4_demand"] == 50.0 and safe["m4_shortage"] == 50.0

    # Open POs offset the shortfall: without the 30 open, M1 shortage would
    # be 70 (safety 20 - (50 - 100)); with it, it's 40.
    openpo = rows["M-OPENPO"]
    assert openpo["open_po"] == 30.0
    assert openpo["m1_shortage"] == 40.0

    # Buyer slicer scopes the report like every other page.
    r = client.get("/api/analytics/planning", params={"buyer": "Alice"})
    codes = {row["material_code"] for row in r.json()["rows"]}
    assert codes == {"M-SAFE", "M-RISK", "M-EXCESS", "M-OPENPO"}


def test_incoming_timeseries_pending_until_movements_loaded(client):
    r = client.get("/api/analytics/incoming-timeseries")
    assert r.status_code == 200
    data = r.json()
    assert data["grain"] == "monthly"
    assert data["points"] == []
    assert data["pending"] is True
