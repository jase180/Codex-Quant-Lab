"""Utilities for daily OHLCV input data."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class MarketBar:
    """Represents a single daily market bar."""

    timestamp: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float


def validate_ohlcv_data(data: pd.DataFrame) -> pd.DataFrame:
    """Return a normalized daily OHLCV DataFrame."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing_columns:
        raise ValueError(f"data is missing required columns: {missing_columns}")

    normalized = data.copy()
    if not isinstance(normalized.index, pd.DatetimeIndex):
        if "date" in normalized.columns:
            normalized["date"] = pd.to_datetime(normalized["date"])
            normalized = normalized.set_index("date")
        else:
            raise ValueError("data must use a DatetimeIndex or include a 'date' column")

    normalized.index = pd.to_datetime(normalized.index)
    normalized = normalized.sort_index()

    if normalized.index.has_duplicates:
        raise ValueError("data index must not contain duplicate dates")

    numeric_columns = list(REQUIRED_COLUMNS)
    normalized[numeric_columns] = normalized[numeric_columns].apply(pd.to_numeric, errors="raise")

    if normalized.empty:
        raise ValueError("data must not be empty")

    return normalized.loc[:, list(REQUIRED_COLUMNS)]


def iter_market_bars(data: pd.DataFrame) -> list[MarketBar]:
    """Convert a normalized DataFrame into market bars."""
    return [
        MarketBar(
            timestamp=index,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
        for index, row in data.iterrows()
    ]
