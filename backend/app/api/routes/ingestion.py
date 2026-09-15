"""Ingestion endpoints: upload files or pull from databases, preview, load."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors import (
    ConnectorError,
    DBConnectionConfig,
    FileConnector,
    SQLConnector,
)
from app.database import get_db
from app.ingestion import build_column_map, get_dump_type, load_dataframe
from app.ingestion.dump_types import DUMP_TYPES
from app.models import IngestionLog
from app.schemas import DBConnectionRequest, DBIngestRequest, DBPreviewRequest

router = APIRouter(prefix="/ingest", tags=["ingestion"])


def _cfg(req: DBConnectionRequest) -> DBConnectionConfig:
    return DBConnectionConfig(
        source_type=req.source_type,
        host=req.host,
        port=req.port,
        database=req.database,
        username=req.username,
        password=req.password,
        odbc_driver=req.odbc_driver,
        dsn=req.dsn,
        file_path=req.file_path,
    )


@router.post("/file/preview")
async def preview_file(
    dump_type: str = Form(...),
    sheet_name: str | None = Form(None),
    file: UploadFile = File(...),
) -> dict:
    """Read a file and show how its columns map to the dump type (no write)."""
    if dump_type not in DUMP_TYPES:
        raise HTTPException(400, f"Unknown dump type '{dump_type}'.")
    content = await file.read()
    try:
        df = FileConnector(
            content=content,
            filename=file.filename,
            sheet_name=int(sheet_name) if sheet_name and sheet_name.isdigit() else (sheet_name or 0),
        ).read()
    except ConnectorError as exc:
        raise HTTPException(400, str(exc)) from exc

    dump = get_dump_type(dump_type)
    column_map = build_column_map(df, dump)
    mapped = set(column_map.values())
    return {
        "filename": file.filename,
        "rows": int(len(df)),
        "source_columns": list(df.columns),
        "column_map": column_map,
        "missing_required": [f.name for f in dump.fields if f.required and f.name not in mapped],
        "sample": df.head(5).astype(str).to_dict(orient="records"),
    }


@router.post("/file")
async def ingest_file(
    dump_type: str = Form(...),
    mode: str = Form("replace"),
    sheet_name: str | None = Form(None),
    merge_keys: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Upload an Excel/CSV/JSON file and load it into the app database."""
    if dump_type not in DUMP_TYPES:
        raise HTTPException(400, f"Unknown dump type '{dump_type}'.")
    content = await file.read()
    keys = [k.strip() for k in merge_keys.split(",")] if merge_keys else None
    try:
        df = FileConnector(
            content=content,
            filename=file.filename,
            sheet_name=int(sheet_name) if sheet_name and sheet_name.isdigit() else (sheet_name or 0),
        ).read()
        report = load_dataframe(
            db, df, dump_type,
            source_type="file", source_name=file.filename or "upload", mode=mode,
            merge_keys=keys,
        )
    except ConnectorError as exc:
        raise HTTPException(400, str(exc)) from exc
    if report.get("status") == "error":
        raise HTTPException(400, {"message": "Ingestion failed", "report": report})
    return report


@router.post("/db/test")
def test_db(req: DBConnectionRequest) -> dict:
    """Test a database connection."""
    try:
        SQLConnector(_cfg(req), table="dummy").test_connection()
    except ConnectorError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"status": "ok", "message": "Connection successful."}


@router.post("/db/preview")
def preview_db(req: DBPreviewRequest) -> dict:
    """Run a query/table read against a DB source and preview mapping."""
    try:
        df = SQLConnector(
            _cfg(req), query=req.query, table=req.table, limit=req.limit or 100
        ).read()
    except ConnectorError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "rows": int(len(df)),
        "source_columns": list(df.columns),
        "sample": df.head(5).astype(str).to_dict(orient="records"),
    }


@router.post("/db")
def ingest_db(req: DBIngestRequest, db: Session = Depends(get_db)) -> dict:
    """Pull data from a database source and load it into the app database."""
    if req.dump_type not in DUMP_TYPES:
        raise HTTPException(400, f"Unknown dump type '{req.dump_type}'.")
    try:
        df = SQLConnector(
            _cfg(req), query=req.query, table=req.table, limit=req.limit
        ).read()
        report = load_dataframe(
            db, df, req.dump_type,
            source_type=req.source_type,
            source_name=req.table or (req.query or "")[:200],
            mode=req.mode,
            overrides=req.column_overrides,
            merge_keys=req.merge_keys,
        )
    except ConnectorError as exc:
        raise HTTPException(400, str(exc)) from exc
    if report.get("status") == "error":
        raise HTTPException(400, {"message": "Ingestion failed", "report": report})
    return report


@router.get("/log")
def ingestion_log(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(IngestionLog).order_by(IngestionLog.ingested_at.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "dump_type": r.dump_type,
            "source_type": r.source_type,
            "source_name": r.source_name,
            "rows_ingested": r.rows_ingested,
            "mode": r.mode,
            "status": r.status,
            "message": r.message,
            "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
        }
        for r in rows
    ]
