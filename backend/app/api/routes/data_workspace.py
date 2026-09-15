"""Data Workspace API: browse, edit, delete, merge, link (join), profile and
export the staged datasets — the interactive data-management back-end.
"""
from __future__ import annotations

import io
import json

import numpy as np
import pandas as pd
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analytics.common import _MODEL_BY_NAME, load_df
from app.database import get_db
from app.ingestion.dump_types import DUMP_TYPES

router = APIRouter(prefix="/data", tags=["data-workspace"])

_EDITABLE_SKIP = {"id", "created_at", "updated_at"}


def _model(dataset: str):
    if dataset not in _MODEL_BY_NAME:
        raise HTTPException(404, f"Unknown dataset '{dataset}'. Known: {sorted(_MODEL_BY_NAME)}")
    return _MODEL_BY_NAME[dataset]


def _columns(model) -> list[dict]:
    out = []
    for c in model.__table__.columns:
        out.append({
            "name": c.name,
            "type": str(c.type).split("(")[0].lower(),
            "editable": c.name not in _EDITABLE_SKIP,
        })
    return out


@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)) -> list[dict]:
    """All datasets (staged tables) with row counts and column metadata."""
    out = []
    for key, model in _MODEL_BY_NAME.items():
        count = db.execute(select(func.count()).select_from(model)).scalar() or 0
        dump = DUMP_TYPES.get(key)
        out.append({
            "key": key,
            "label": dump.label if dump else key,
            "description": dump.description if dump else "",
            "rows": int(count),
            "columns": _columns(model),
        })
    return out


@router.get("/{dataset}/rows")
def get_rows(
    dataset: str,
    limit: int = 50,
    offset: int = 0,
    sort: str | None = None,
    direction: str = "asc",
    q: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Paginated, sortable, searchable rows of a dataset."""
    model = _model(dataset)
    df = load_df(db, dataset)
    total_all = len(df)

    if q and not df.empty:
        mask = df.apply(lambda r: r.astype(str).str.contains(q, case=False, na=False).any(), axis=1)
        df = df[mask]
    total = len(df)

    if sort and sort in df.columns:
        df = df.sort_values(sort, ascending=(direction != "desc"), na_position="last")

    page = df.iloc[offset: offset + limit]
    records = json.loads(page.to_json(orient="records", date_format="iso"))
    return {
        "dataset": dataset,
        "columns": _columns(model),
        "rows": records,
        "total": total,
        "total_unfiltered": total_all,
        "offset": offset,
        "limit": limit,
    }


@router.delete("/{dataset}")
def truncate_dataset(dataset: str, db: Session = Depends(get_db)) -> dict:
    """Delete ALL rows of a dataset."""
    model = _model(dataset)
    n = db.execute(select(func.count()).select_from(model)).scalar() or 0
    db.execute(delete(model))
    db.commit()
    return {"dataset": dataset, "deleted": int(n)}


@router.post("/{dataset}/delete-rows")
def delete_rows(dataset: str, ids: list[int] = Body(..., embed=True), db: Session = Depends(get_db)) -> dict:
    """Delete selected rows by id."""
    model = _model(dataset)
    if not ids:
        return {"dataset": dataset, "deleted": 0}
    res = db.execute(delete(model).where(model.id.in_(ids)))
    db.commit()
    return {"dataset": dataset, "deleted": int(res.rowcount or 0)}


@router.post("/{dataset}/update-row")
def update_row(
    dataset: str,
    row_id: int = Body(..., embed=True),
    values: dict = Body(..., embed=True),
    db: Session = Depends(get_db),
) -> dict:
    """Update editable fields of a single row (inline cell editing)."""
    model = _model(dataset)
    obj = db.get(model, row_id)
    if not obj:
        raise HTTPException(404, f"Row {row_id} not found in '{dataset}'.")
    valid = {c.name for c in model.__table__.columns} - _EDITABLE_SKIP
    changed = {}
    for k, v in values.items():
        if k in valid:
            setattr(obj, k, v)
            changed[k] = v
    db.commit()
    return {"dataset": dataset, "id": row_id, "updated": changed}


@router.get("/{dataset}/profile")
def profile_dataset(dataset: str, db: Session = Depends(get_db)) -> dict:
    """Data-quality / modeling report: per-column nulls, distinct, ranges."""
    _model(dataset)
    df = load_df(db, dataset)
    cols = []
    for c in df.columns:
        if c in _EDITABLE_SKIP - {"id"}:
            continue
        s = df[c]
        info = {
            "column": c,
            "non_null": int(s.notna().sum()),
            "nulls": int(s.isna().sum()),
            "null_pct": round(100 * s.isna().mean(), 1) if len(s) else 0.0,
            "distinct": int(s.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(s) and s.notna().any():
            info["min"] = _num(s.min())
            info["max"] = _num(s.max())
            info["mean"] = _num(s.mean())
            info["sum"] = _num(s.sum())
        cols.append(info)
    return {"dataset": dataset, "rows": int(len(df)), "columns": cols}


@router.post("/join")
def join_datasets(
    left: str = Body(...),
    right: str = Body(...),
    left_on: str = Body(...),
    right_on: str = Body(...),
    how: str = Body("inner"),
    limit: int = Body(100),
    db: Session = Depends(get_db),
) -> dict:
    """Column-to-column link: join two datasets and preview the result."""
    _model(left)
    _model(right)
    if how not in {"inner", "left", "right", "outer"}:
        raise HTTPException(400, "how must be inner | left | right | outer")
    ldf, rdf = load_df(db, left), load_df(db, right)
    if left_on not in ldf.columns:
        raise HTTPException(400, f"'{left_on}' not in {left}.")
    if right_on not in rdf.columns:
        raise HTTPException(400, f"'{right_on}' not in {right}.")
    ldf = ldf.drop(columns=[c for c in ("id", "created_at", "updated_at") if c in ldf])
    rdf = rdf.drop(columns=[c for c in ("id", "created_at", "updated_at") if c in rdf])
    merged = ldf.merge(rdf, left_on=left_on, right_on=right_on, how=how,
                       suffixes=(f"_{left}", f"_{right}"))
    matched = int((merged[left_on].notna()).sum()) if left_on in merged else len(merged)
    page = merged.head(limit)
    records = json.loads(page.to_json(orient="records", date_format="iso"))
    return {
        "columns": [{"name": c} for c in merged.columns],
        "rows": records,
        "total": int(len(merged)),
        "matched": matched,
        "left_rows": int(len(ldf)),
        "right_rows": int(len(rdf)),
    }


@router.get("/{dataset}/export")
def export_dataset(dataset: str, format: str = "csv", db: Session = Depends(get_db)):
    """Export a dataset as CSV, JSON or Excel (file download)."""
    _model(dataset)
    df = load_df(db, dataset)
    df = df.drop(columns=[c for c in ("created_at", "updated_at") if c in df])
    return _stream(df, dataset, format)


def _stream(df: pd.DataFrame, name: str, fmt: str) -> StreamingResponse:
    fmt = fmt.lower()
    if fmt == "csv":
        buf = io.BytesIO(df.to_csv(index=False).encode("utf-8"))
        media, ext = "text/csv", "csv"
    elif fmt == "json":
        buf = io.BytesIO(df.to_json(orient="records", date_format="iso", indent=2).encode("utf-8"))
        media, ext = "application/json", "json"
    elif fmt in ("xlsx", "excel"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xl:
            df.to_excel(xl, index=False, sheet_name=name[:31] or "data")
        buf.seek(0)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        raise HTTPException(400, "format must be csv | json | xlsx")
    headers = {"Content-Disposition": f'attachment; filename="{name}.{ext}"'}
    return StreamingResponse(buf, media_type=media, headers=headers)


def _num(v):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), 3)
