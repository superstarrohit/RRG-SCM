"""Map and coerce raw DataFrame columns onto a dump type's canonical schema."""
from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd

from app.ingestion.dump_types import DumpType, FieldSpec


def _normalise(name: str) -> str:
    """Lowercase, strip, collapse separators for fuzzy header matching."""
    s = str(name).strip().lower()
    s = re.sub(r"[\s\-./]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s.strip("_")


def build_column_map(
    df: pd.DataFrame, dump: DumpType, overrides: dict[str, str] | None = None
) -> dict[str, str]:
    """Return {source_column: canonical_field} for the given dump type.

    ``overrides`` lets the caller force a mapping ({canonical_field: source_column}).
    """
    overrides = overrides or {}
    norm_to_source = {_normalise(c): c for c in df.columns}
    mapping: dict[str, str] = {}

    for spec in dump.fields:
        # 1) explicit override wins
        if spec.name in overrides and overrides[spec.name] in df.columns:
            mapping[overrides[spec.name]] = spec.name
            continue
        # 2) exact / alias match on normalised names
        candidates = [spec.name, *spec.aliases]
        for cand in candidates:
            key = _normalise(cand)
            if key in norm_to_source:
                mapping[norm_to_source[key]] = spec.name
                break
    return mapping


def _coerce(series: pd.Series, dtype: str) -> pd.Series:
    if dtype == "float":
        return pd.to_numeric(series, errors="coerce")
    if dtype == "int":
        return pd.to_numeric(series, errors="coerce").astype("Int64")
    if dtype == "date":
        return pd.to_datetime(series, errors="coerce", dayfirst=False)
    return series.astype("string").str.strip()


def _to_python(value, dtype: str):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if pd.isna(value):
        return None
    if dtype == "float":
        return float(value)
    if dtype == "int":
        return int(value)
    if dtype == "date":
        if isinstance(value, (datetime, pd.Timestamp)):
            return value.date()
        if isinstance(value, date):
            return value
        return None
    return str(value)


def transform(
    df: pd.DataFrame, dump: DumpType, overrides: dict[str, str] | None = None
) -> tuple[list[dict], dict]:
    """Map, coerce and validate a raw DataFrame for a dump type.

    Returns (list of row dicts ready for the ORM, report metadata).
    """
    column_map = build_column_map(df, dump, overrides)
    mapped_fields = set(column_map.values())

    missing_required = [
        s.name for s in dump.fields if s.required and s.name not in mapped_fields
    ]
    report: dict = {
        "dump_type": dump.key,
        "source_columns": list(df.columns),
        "column_map": column_map,
        "mapped_fields": sorted(mapped_fields),
        "unmapped_source_columns": [c for c in df.columns if c not in column_map],
        "missing_required": missing_required,
        "rows_in": int(len(df)),
    }
    if missing_required:
        report["rows_out"] = 0
        return [], report

    # Build a clean frame with canonical column names + coerced dtypes.
    spec_by_name: dict[str, FieldSpec] = {s.name: s for s in dump.fields}
    clean = pd.DataFrame()
    for source_col, canonical in column_map.items():
        clean[canonical] = _coerce(df[source_col], spec_by_name[canonical].dtype)

    # Drop rows missing any required value.
    for name in [s.name for s in dump.fields if s.required]:
        clean = clean[clean[name].notna()]

    records: list[dict] = []
    for _, row in clean.iterrows():
        rec = {}
        for canonical in clean.columns:
            rec[canonical] = _to_python(row[canonical], spec_by_name[canonical].dtype)
        records.append(rec)

    report["rows_out"] = len(records)
    report["rows_dropped"] = report["rows_in"] - len(records)
    return records, report
