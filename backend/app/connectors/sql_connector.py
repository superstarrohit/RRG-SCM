"""Database connectors: SQL Server, MySQL/Workbench, PostgreSQL, MS Access, ODBC.

Each of these is reached through SQLAlchemy using a driver-specific URL. Drivers
are optional dependencies (see requirements.txt); we import them lazily so the
app runs without them and only errors if you actually use that source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

from app.connectors.base import Connector, ConnectorError

# Supported database source types -> human label + required pip driver.
DB_SOURCE_TYPES: dict[str, dict[str, str]] = {
    "sqlserver": {"label": "Microsoft SQL Server", "driver": "pyodbc"},
    "mysql": {"label": "MySQL / MySQL Workbench", "driver": "PyMySQL"},
    "postgres": {"label": "PostgreSQL", "driver": "psycopg2-binary"},
    "access": {"label": "Microsoft Access", "driver": "pyodbc"},
    "odbc": {"label": "Generic ODBC (DSN)", "driver": "pyodbc"},
    "sap_hana": {"label": "SAP HANA", "driver": "sqlalchemy-hana hdbcli"},
    "sap_odbc": {"label": "SAP (ERP/BW via ODBC/DSN)", "driver": "pyodbc"},
}


@dataclass
class DBConnectionConfig:
    """Everything needed to reach a database source."""

    source_type: str  # one of DB_SOURCE_TYPES
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    # SQL Server / Access / ODBC extras
    odbc_driver: str | None = None  # e.g. "ODBC Driver 17 for SQL Server"
    dsn: str | None = None  # for generic ODBC
    file_path: str | None = None  # for MS Access .accdb/.mdb
    extra: dict[str, str] = field(default_factory=dict)


def build_url(cfg: DBConnectionConfig) -> str:
    """Build a SQLAlchemy connection URL from a connection config."""
    st = cfg.source_type
    if st not in DB_SOURCE_TYPES:
        raise ConnectorError(f"Unknown database source type '{st}'.")

    user = quote_plus(cfg.username) if cfg.username else ""
    pwd = quote_plus(cfg.password) if cfg.password else ""
    auth = f"{user}:{pwd}@" if user else ""

    if st == "postgres":
        port = cfg.port or 5432
        return f"postgresql+psycopg2://{auth}{cfg.host}:{port}/{cfg.database}"

    if st == "mysql":
        port = cfg.port or 3306
        return f"mysql+pymysql://{auth}{cfg.host}:{port}/{cfg.database}"

    if st == "sqlserver":
        port = cfg.port or 1433
        driver = quote_plus(cfg.odbc_driver or "ODBC Driver 17 for SQL Server")
        return (
            f"mssql+pyodbc://{auth}{cfg.host}:{port}/{cfg.database}"
            f"?driver={driver}"
        )

    if st == "access":
        if not cfg.file_path:
            raise ConnectorError("MS Access source requires 'file_path'.")
        driver = cfg.odbc_driver or "Microsoft Access Driver (*.mdb, *.accdb)"
        conn = quote_plus(
            f"DRIVER={{{driver}}};DBQ={cfg.file_path};"
        )
        return f"access+pyodbc:///?odbc_connect={conn}"

    if st == "sap_hana":
        # SAP HANA via the sqlalchemy-hana dialect (needs the hdbcli driver).
        port = cfg.port or 30015
        return f"hana://{auth}{cfg.host}:{port}"

    if st == "sap_odbc":
        # SAP ERP/BW is typically reached through an ODBC DSN (e.g. an SAP HANA
        # or Connector/ODBC DSN configured on the host).
        if not cfg.dsn:
            raise ConnectorError("SAP (ODBC) source requires a configured 'dsn'.")
        conn = quote_plus(
            f"DSN={cfg.dsn};UID={cfg.username or ''};PWD={cfg.password or ''};"
        )
        return f"mssql+pyodbc:///?odbc_connect={conn}"

    if st == "odbc":
        if cfg.dsn:
            conn = quote_plus(f"DSN={cfg.dsn};UID={cfg.username or ''};PWD={cfg.password or ''}")
        elif cfg.odbc_driver:
            parts = [f"DRIVER={{{cfg.odbc_driver}}}"]
            if cfg.host:
                parts.append(f"SERVER={cfg.host}")
            if cfg.database:
                parts.append(f"DATABASE={cfg.database}")
            if cfg.username:
                parts.append(f"UID={cfg.username}")
            if cfg.password:
                parts.append(f"PWD={cfg.password}")
            conn = quote_plus(";".join(parts) + ";")
        else:
            raise ConnectorError("ODBC source requires a 'dsn' or 'odbc_driver'.")
        return f"mssql+pyodbc:///?odbc_connect={conn}"

    raise ConnectorError(f"Unsupported source type '{st}'.")  # pragma: no cover


class SQLConnector(Connector):
    """Reads a DataFrame from a database table or SQL query."""

    def __init__(
        self,
        cfg: DBConnectionConfig,
        *,
        query: str | None = None,
        table: str | None = None,
        limit: int | None = None,
    ) -> None:
        if not query and not table:
            raise ConnectorError("Provide either a 'query' or a 'table' to read.")
        self.cfg = cfg
        self.source_type = cfg.source_type
        self.query = query
        self.table = table
        self.limit = limit

    def _resolve_query(self) -> str:
        if self.query:
            return self.query
        # Basic identifier guard for table-name reads.
        table = self.table or ""
        if not all(c.isalnum() or c in "_.[]\"" for c in table):
            raise ConnectorError(f"Invalid table name '{table}'.")
        top = f"TOP {int(self.limit)} " if self.limit and self.source_type in {"sqlserver", "access", "odbc", "sap_odbc"} else ""
        tail = f" LIMIT {int(self.limit)}" if self.limit and self.source_type in {"postgres", "mysql", "sap_hana"} else ""
        return f"SELECT {top}* FROM {table}{tail}"

    def test_connection(self) -> None:
        """Open and close a connection to verify credentials."""
        engine = create_engine(build_url(self.cfg))
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # pragma: no cover - environment dependent
            raise ConnectorError(f"Connection test failed: {exc}") from exc
        finally:
            engine.dispose()

    def read(self) -> pd.DataFrame:
        try:
            engine = create_engine(build_url(self.cfg))
        except ModuleNotFoundError as exc:  # driver not installed
            driver = DB_SOURCE_TYPES[self.source_type]["driver"]
            raise ConnectorError(
                f"Driver for '{self.source_type}' not installed. "
                f"Run: pip install {driver}"
            ) from exc
        try:
            with engine.connect() as conn:
                return pd.read_sql(text(self._resolve_query()), conn)
        except ConnectorError:
            raise
        except Exception as exc:  # pragma: no cover - environment dependent
            raise ConnectorError(f"Query failed: {exc}") from exc
        finally:
            engine.dispose()
