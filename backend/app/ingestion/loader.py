"""Load transformed dump records into the application database."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ingestion.dump_types import DumpType, get_dump_type
from app.ingestion.mapper import transform
from app.models import IngestionLog


def load_dataframe(
    db: Session,
    df: pd.DataFrame,
    dump_type_key: str,
    *,
    source_type: str,
    source_name: str,
    mode: str = "replace",
    overrides: dict[str, str] | None = None,
) -> dict:
    """Map ``df`` to the dump type, write rows, and record an ingestion log.

    ``mode`` is 'replace' (truncate the table first) or 'append'.
    Returns the mapping/validation report enriched with load results.
    """
    dump: DumpType = get_dump_type(dump_type_key)
    records, report = transform(df, dump, overrides)

    if report["missing_required"]:
        _log(
            db,
            dump=dump,
            source_type=source_type,
            source_name=source_name,
            mode=mode,
            rows=0,
            status="error",
            message=f"Missing required columns: {report['missing_required']}",
        )
        report["status"] = "error"
        report["rows_ingested"] = 0
        return report

    if mode == "replace":
        db.execute(delete(dump.model))

    objects = [dump.model(**rec) for rec in records]
    db.add_all(objects)
    db.flush()

    _log(
        db,
        dump=dump,
        source_type=source_type,
        source_name=source_name,
        mode=mode,
        rows=len(objects),
        status="success",
        message=f"Loaded {len(objects)} rows ({mode}).",
    )
    db.commit()

    report["status"] = "success"
    report["rows_ingested"] = len(objects)
    return report


def _log(db: Session, *, dump, source_type, source_name, mode, rows, status, message):
    db.add(
        IngestionLog(
            dump_type=dump.key,
            source_type=source_type,
            source_name=source_name,
            rows_ingested=rows,
            mode=mode,
            status=status,
            message=message,
        )
    )
    db.flush()
