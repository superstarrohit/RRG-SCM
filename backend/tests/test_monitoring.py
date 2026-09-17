"""Tests for Stock Monitoring and Inventory Monitoring analytics."""
from __future__ import annotations

import io

import pandas as pd


def _csv(df):
    buf = io.StringIO(); df.to_csv(buf, index=False); return buf.getvalue().encode()


def _up(client, dump, df):
    return client.post("/api/ingest/file", data={"dump_type": dump, "mode": "replace"},
                       files={"file": (f"{dump}.csv", _csv(df), "text/csv")})


def test_inventory_monitoring_trend(client):
    _up(client, "materials", pd.DataFrame({"Material": ["M1"], "Commodity": ["Metals"], "Buyer": ["A"]}))
    _up(client, "inventory_snapshots", pd.DataFrame({
        "Material": ["M1", "M1", "M1"],
        "Location": ["WH1", "WH1", "WH1"],
        "Date": ["2026-07-01", "2026-08-01", "2026-09-01"],
        "Qty": [100, 120, 150],
        "Value": [1000, 1200, 1500],
    }))
    r = client.get("/api/analytics/inventory-monitoring")
    assert r.status_code == 200
    d = r.json()
    assert len(d["timeline"]) == 3
    assert d["kpis"]["inventory_value"] == 1500.0
    assert d["kpis"]["mom_change_pct"] == 25.0   # 1200 -> 1500
    assert d["by_commodity"][0]["name"] == "Metals"


def test_monitoring_empty_states(client):
    assert client.get("/api/analytics/inventory-monitoring").json()["empty"] is True
    assert client.get("/api/analytics/stock-monitoring").json()["empty"] is True
