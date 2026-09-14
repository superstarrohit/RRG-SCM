"""File connectors for Excel and CSV/TSV uploads."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from app.connectors.base import Connector, ConnectorError


class FileConnector(Connector):
    """Reads a DataFrame from an Excel (.xlsx/.xls) or CSV/TSV file.

    The source can be a filesystem path or raw bytes (e.g. an upload).
    """

    source_type = "file"

    def __init__(
        self,
        *,
        path: str | Path | None = None,
        content: bytes | None = None,
        filename: str | None = None,
        sheet_name: str | int | None = 0,
        delimiter: str | None = None,
    ) -> None:
        if path is None and content is None:
            raise ConnectorError("FileConnector needs either a path or content.")
        self.path = Path(path) if path else None
        self.content = content
        self.filename = filename or (self.path.name if self.path else "upload")
        self.sheet_name = sheet_name
        self.delimiter = delimiter

    @property
    def _suffix(self) -> str:
        return Path(self.filename).suffix.lower()

    def _buffer(self):
        if self.content is not None:
            return io.BytesIO(self.content)
        return self.path

    def read(self) -> pd.DataFrame:
        suffix = self._suffix
        try:
            if suffix in {".xlsx", ".xlsm", ".xls"}:
                engine = "xlrd" if suffix == ".xls" else "openpyxl"
                df = pd.read_excel(
                    self._buffer(), sheet_name=self.sheet_name, engine=engine
                )
            elif suffix in {".csv", ".txt", ".tsv"}:
                sep = self.delimiter or ("\t" if suffix == ".tsv" else ",")
                df = pd.read_csv(self._buffer(), sep=sep)
            else:
                raise ConnectorError(
                    f"Unsupported file type '{suffix}'. "
                    "Use .xlsx, .xls, .csv, .tsv or .txt."
                )
        except ConnectorError:
            raise
        except Exception as exc:  # pragma: no cover - surfaced to the API
            raise ConnectorError(f"Failed to read file '{self.filename}': {exc}") from exc

        # A multi-sheet read returns a dict; take the first sheet in that case.
        if isinstance(df, dict):
            df = next(iter(df.values()))
        return df
