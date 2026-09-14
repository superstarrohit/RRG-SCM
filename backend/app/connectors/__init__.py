"""Data-source connectors."""
from app.connectors.base import Connector, ConnectorError
from app.connectors.file_connector import FileConnector
from app.connectors.sql_connector import (
    DB_SOURCE_TYPES,
    DBConnectionConfig,
    SQLConnector,
    build_url,
)

#: All source types the app advertises to the UI.
SOURCE_TYPES: dict[str, str] = {
    "file": "Excel / CSV file upload",
    **{k: v["label"] for k, v in DB_SOURCE_TYPES.items()},
}

__all__ = [
    "Connector",
    "ConnectorError",
    "FileConnector",
    "SQLConnector",
    "DBConnectionConfig",
    "DB_SOURCE_TYPES",
    "SOURCE_TYPES",
    "build_url",
]
