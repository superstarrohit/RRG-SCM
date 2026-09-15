"""Tests for the Data Workspace API: browse, edit, delete, merge, join, export."""
from __future__ import annotations

import io

import pandas as pd


def _csv(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()


def _upload(client, dump, df, mode="replace", merge_keys=None):
    data = {"dump_type": dump, "mode": mode}
    if merge_keys:
        data["merge_keys"] = merge_keys
    return client.post("/api/ingest/file", data=data,
                       files={"file": (f"{dump}.csv", _csv(df), "text/csv")})


def _seed(client):
    _upload(client, "materials", pd.DataFrame(
        {"Material": ["M1", "M2"], "Description": ["A", "B"], "Cost": [10.0, 5.0]}))
    _upload(client, "stock", pd.DataFrame({"Material": ["M1", "M2"], "On Hand": [100, 50]}))


def test_datasets_list(client):
    _seed(client)
    r = client.get("/api/data/datasets")
    assert r.status_code == 200
    by_key = {d["key"]: d for d in r.json()}
    assert by_key["materials"]["rows"] == 2
    assert any(c["name"] == "material_code" for c in by_key["materials"]["columns"])


def test_rows_search_and_sort(client):
    _seed(client)
    r = client.get("/api/data/materials/rows", params={"q": "M1"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["rows"][0]["material_code"] == "M1"


def test_delete_rows_and_truncate(client):
    _seed(client)
    rows = client.get("/api/data/materials/rows").json()["rows"]
    rid = rows[0]["id"]
    d = client.post("/api/data/materials/delete-rows", json={"ids": [rid]})
    assert d.status_code == 200 and d.json()["deleted"] == 1
    t = client.delete("/api/data/materials")
    assert t.status_code == 200
    assert client.get("/api/data/materials/rows").json()["total"] == 0


def test_update_row(client):
    _seed(client)
    rid = client.get("/api/data/materials/rows").json()["rows"][0]["id"]
    u = client.post("/api/data/materials/update-row",
                    json={"row_id": rid, "values": {"description": "Renamed"}})
    assert u.status_code == 200
    rows = client.get("/api/data/materials/rows").json()["rows"]
    assert any(r["description"] == "Renamed" for r in rows)


def test_merge_upsert(client):
    _seed(client)
    r = _upload(client, "materials", pd.DataFrame(
        {"Material": ["M1", "M3"], "Description": ["A-upd", "C"], "Cost": [11.0, 3.0]}),
        mode="merge", merge_keys="material_code")
    assert r.status_code == 200
    body = r.json()
    assert body["inserted"] == 1 and body["updated"] == 1
    assert client.get("/api/data/materials/rows").json()["total"] == 3


def test_join(client):
    _seed(client)
    j = client.post("/api/data/join", json={
        "left": "stock", "right": "materials",
        "left_on": "material_code", "right_on": "material_code", "how": "inner"})
    assert j.status_code == 200
    body = j.json()
    assert body["total"] == 2
    names = {c["name"] for c in body["columns"]}
    assert "qty_on_hand" in names and "description" in names


def test_export_formats(client):
    _seed(client)
    for fmt, ctype in [("csv", "text/csv"), ("json", "application/json"),
                       ("xlsx", "application/vnd.openxmlformats")]:
        r = client.get("/api/data/materials/export", params={"format": fmt})
        assert r.status_code == 200
        assert ctype.split("/")[0] in r.headers["content-type"]


def test_profile(client):
    _seed(client)
    p = client.get("/api/data/materials/profile").json()
    assert p["rows"] == 2
    cost = next(c for c in p["columns"] if c["column"] == "unit_cost")
    assert cost["max"] == 10.0
