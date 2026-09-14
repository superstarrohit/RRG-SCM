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
    assert {"open_pos", "stock", "materials", "bom"} <= keys


def test_upload_and_incoming_analysis(client):
    today = date.today()

    materials = pd.DataFrame(
        {"Material": ["M1", "M2"], "Description": ["Part 1", "Part 2"],
         "Category": ["Raw", "Comp"], "Cost": [10.0, 5.0]}
    )
    assert _upload(client, "materials", materials).status_code == 200

    stock = pd.DataFrame({"Material": ["M1", "M2"], "On Hand": [100, 0]})
    assert _upload(client, "stock", stock).status_code == 200

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


def test_planning_shortage(client):
    materials = pd.DataFrame(
        {"Material": ["M1"], "Cost": [10.0], "SS": [20], "ROP": [50], "MOQ": [100]}
    )
    _upload(client, "materials", materials)
    _upload(client, "stock", pd.DataFrame({"Material": ["M1"], "On Hand": [10]}))
    _upload(client, "demand", pd.DataFrame({"Material": ["M1"], "Qty": [200]}))

    r = client.get("/api/analytics/planning")
    assert r.status_code == 200
    data = r.json()
    assert data["kpis"]["shortage_items"] == 1
    assert data["shortages"][0]["material_code"] == "M1"
    # net = demand(200) + ss(20) - onhand(10) = 210 -> order max(210, moq 100)=210
    assert data["shortages"][0]["suggested_order"] == 210.0


def test_bad_dump_type_rejected(client):
    r = _upload(client, "not_a_type", pd.DataFrame({"a": [1]}))
    assert r.status_code == 400
