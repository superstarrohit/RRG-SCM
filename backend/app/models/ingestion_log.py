"""Audit log of every dump ingested into the app."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IngestionLog(Base):
    """One row per ingestion run (file upload or DB pull)."""

    __tablename__ = "ingestion_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dump_type: Mapped[str] = mapped_column(String(64), index=True)
    source_type: Mapped[str] = mapped_column(String(32))  # file / sqlserver / ...
    source_name: Mapped[str | None] = mapped_column(String(512))
    rows_ingested: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(16), default="replace")  # replace/append
    status: Mapped[str] = mapped_column(String(16), default="success")
    message: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
