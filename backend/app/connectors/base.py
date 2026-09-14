"""Connector abstractions.

A *connector* knows how to pull a tabular dataset from a particular kind of
source and return it as a pandas DataFrame. The rest of the app (mapping,
validation, loading) is source-agnostic.
"""
from __future__ import annotations

import abc

import pandas as pd


class Connector(abc.ABC):
    """Base class for all data-source connectors."""

    #: short identifier, e.g. "file", "sqlserver"
    source_type: str = "base"

    @abc.abstractmethod
    def read(self) -> pd.DataFrame:
        """Return the source data as a DataFrame."""
        raise NotImplementedError


class ConnectorError(RuntimeError):
    """Raised when a connector cannot read its source."""
