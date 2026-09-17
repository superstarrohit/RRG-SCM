"""Tests for the mapping/ingestion layer."""
from __future__ import annotations

import pandas as pd

from app.ingestion import build_column_map, get_dump_type, transform


def test_alias_mapping_open_pos():
    dump = get_dump_type("open_pos")
    df = pd.DataFrame(
        {
            "PO No": ["P1"],
            "Material": ["M1"],
            "Vendor": ["V1"],
            "Order Qty": [10],
            "Open Qty": [10],
            "ETA": ["2026-01-01"],
        }
    )
    col_map = build_column_map(df, dump)
    assert col_map["PO No"] == "po"
    assert col_map["Material"] == "material"
    assert col_map["Vendor"] == "supplier_code"
    assert col_map["ETA"] == "delivery_date"


def test_transform_coerces_and_validates():
    dump = get_dump_type("stock")
    df = pd.DataFrame(
        {"Material": ["M1", "M2", None], "On Hand": ["10", "20", "5"]}
    )
    records, report = transform(df, dump)
    # The row with a null required material_code is dropped.
    assert report["rows_in"] == 3
    assert report["rows_out"] == 2
    assert records[0]["qty_on_hand"] == 10.0
    assert report["missing_required"] == []


def test_missing_required_reported():
    dump = get_dump_type("stock")
    df = pd.DataFrame({"foo": [1], "bar": [2]})
    records, report = transform(df, dump)
    assert records == []
    assert "material_code" in report["missing_required"]
