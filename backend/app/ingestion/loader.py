"""Load transformed dump records into the application database."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import delete, select
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
    merge_keys: list[str] | None = None,
) -> dict:
    """Map ``df`` to the dump type, write rows, and record an ingestion log.

    ``mode`` is:
      - 'replace'  truncate the table then insert,
      - 'append'   insert alongside existing rows,
      - 'merge'    upsert on ``merge_keys`` (update matches, insert the rest).
    Returns the mapping/validation report enriched with load results.
    """
    dump: DumpType = get_dump_type(dump_type_key)
    records, report = transform(df, dump, overrides)

    if report["missing_required"]:
        _log(
            db, dump=dump, source_type=source_type, source_name=source_name,
            mode=mode, rows=0, status="error",
            message=f"Missing required columns: {report['missing_required']}",
        )
        report["status"] = "error"
        report["rows_ingested"] = 0
        return report

    if mode == "merge":
        inserted, updated = _merge(db, dump, records, merge_keys or _default_keys(dump))
        report["inserted"], report["updated"] = inserted, updated
        rows = inserted + updated
        msg = f"Merged {rows} rows ({inserted} inserted, {updated} updated)."
    else:
        if mode == "replace":
            db.execute(delete(dump.model))
        db.add_all([dump.model(**rec) for rec in records])
        db.flush()
        rows = len(records)
        msg = f"Loaded {rows} rows ({mode})."

    _log(
        db, dump=dump, source_type=source_type, source_name=source_name,
        mode=mode, rows=rows, status="success", message=msg,
    )
    db.commit()

    report["status"] = "success"
    report["rows_ingested"] = rows
    return report


def _default_keys(dump: DumpType) -> list[str]:
    """Sensible default merge keys: the dump's required fields."""
    return [f.name for f in dump.fields if f.required]


def _merge(db: Session, dump: DumpType, records: list[dict], keys: list[str]):
    """Upsert records into the dump's table matching on ``keys``."""
    model = dump.model
    valid = {c.name for c in model.__table__.columns}
    keys = [k for k in keys if k in valid] or _default_keys(dump)
    inserted = updated = 0
    for rec in records:
        conds = [getattr(model, k) == rec.get(k) for k in keys]
        existing = db.execute(select(model).where(*conds)).scalars().first()
        if existing:
            for field, val in rec.items():
                setattr(existing, field, val)
            updated += 1
        else:
            db.add(model(**rec))
            inserted += 1
    db.flush()
    return inserted, updated


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
