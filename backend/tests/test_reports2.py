"""Tests for Vendor Receipts, Movements, Forecasting and global slicers."""
from __future__ import annotations

import io

import pandas as pd


def _csv(df):
    b = io.StringIO(); df.to_csv(b, index=False); return b.getvalue().encode()


def _up(client, dump, df):
    return client.post("/api/ingest/file", data={"dump_type": dump, "mode": "replace"},
                       files={"file": (f"{dump}.csv", _csv(df), "text/csv")})


def _materials(client):
    _up(client, "materials", pd.DataFrame({
        "Material": ["M1", "M2"], "Commodity": ["Metals", "Electro"],
        "Buyer": ["A", "B"], "Cost": [10.0, 2.0]}))


def test_vendor_receipts(client):
    _materials(client)
    _up(client, "suppliers", pd.DataFrame({"Vendor": ["V1"], "Supplier Name": ["Acme"]}))
    _up(client, "receipts", pd.DataFrame({
        "Material": ["M1", "M2"], "Vendor": ["V1", "V1"], "Received": [100, 50],
        "Price": [10.0, 2.0], "Date": ["2026-08-10", "2026-09-05"]}))
    d = client.get("/api/analytics/vendor-receipts").json()
    assert d["kpis"]["total_value"] == 1100.0   # 100*10 + 50*2
    assert len(d["timeline"]) == 2


def test_movements(client):
    _materials(client)
    _up(client, "movements", pd.DataFrame({
        "Material": ["M1", "M1", "M2"], "Mvt": ["GRN", "Issue", "GRN"],
        "Qty": [100, -40, 20], "Value": [1000, -400, 40], "Date": ["2026-09-01", "2026-09-02", "2026-09-03"]}))
    d = client.get("/api/analytics/movements").json()
    assert d["kpis"]["inflow_qty"] == 120.0
    assert d["kpis"]["outflow_qty"] == 40.0
    assert d["kpis"]["net_qty"] == 80.0


def test_forecasting(client):
    _materials(client)
    _up(client, "forecast", pd.DataFrame({
        "Material": ["M1", "M2"], "M1": [100, 50], "M2": [110, 40], "M3": [90, 60]}))
    _up(client, "stock", pd.DataFrame({"Material": ["M1", "M2"], "On Hand": [0, 500]}))
    d = client.get("/api/analytics/forecasting").json()
    assert d["kpis"]["m1_qty"] == 150.0
    assert d["kpis"]["short_items"] >= 1   # M1 has no stock/incoming


def test_global_slicer_filters_incoming(client):
    _materials(client)
    _up(client, "open_pos", pd.DataFrame({
        "PO No": ["P1", "P2"], "Material": ["M1", "M2"], "Vendor": ["V1", "V1"],
        "Open Qty": [10, 20], "Unit Price": [10.0, 2.0]}))
    allc = client.get("/api/analytics/incoming").json()
    assert allc["kpis"]["open_lines"] == 2
    filt = client.get("/api/analytics/incoming", params={"commodity": "Metals"}).json()
    assert filt["kpis"]["open_lines"] == 1
    assert "Metals" in filt["filters"]["commodity"]


def test_slicers_meta(client):
    _materials(client)
    d = client.get("/api/meta/slicers").json()
    assert "Metals" in d["commodity"] and "A" in d["buyer"]
