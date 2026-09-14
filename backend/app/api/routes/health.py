"""Health & metadata endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.connectors import SOURCE_TYPES
from app.ingestion.dump_types import DUMP_TYPES

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "RRG-SCM", "version": __version__}


@router.get("/meta/dump-types")
def dump_types() -> list[dict]:
    """List the dump types the app understands, with their field specs."""
    out = []
    for key, dump in DUMP_TYPES.items():
        out.append(
            {
                "key": key,
                "label": dump.label,
                "description": dump.description,
                "fields": [
                    {
                        "name": f.name,
                        "aliases": list(f.aliases),
                        "dtype": f.dtype,
                        "required": f.required,
                    }
                    for f in dump.fields
                ],
            }
        )
    return out


@router.get("/meta/source-types")
def source_types() -> list[dict]:
    """List the data-source types the app can ingest from."""
    return [{"key": k, "label": v} for k, v in SOURCE_TYPES.items()]
