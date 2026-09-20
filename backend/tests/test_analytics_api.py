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
