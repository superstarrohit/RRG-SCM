"""Schemas for ingestion & connection endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DBConnectionRequest(BaseModel):
    source_type: str = Field(..., description="sqlserver | mysql | postgres | access | odbc")
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    odbc_driver: str | None = None
    dsn: str | None = None
    file_path: str | None = None


class DBPreviewRequest(DBConnectionRequest):
    query: str | None = None
    table: str | None = None
    limit: int | None = 100


class DBIngestRequest(DBPreviewRequest):
    dump_type: str = Field(..., description="Target dump type key, e.g. 'open_pos'")
    mode: str = Field("replace", description="replace | append")
    column_overrides: dict[str, str] | None = Field(
        default=None,
        description="Force mapping: {canonical_field: source_column}",
    )
