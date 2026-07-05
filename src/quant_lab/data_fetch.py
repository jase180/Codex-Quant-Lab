"""Market data fetching and normalization helpers."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def fetch_market_data(
    symbol: str,
    start: str,
    end: str,
    interval: str = "1d",
) -> pd.DataFrame:
    """Fetch market data with yfinance and normalize it to this repo's CSV shape."""

    if interval != "1d":
        raise ValueError("Only daily interval '1d' is supported for now.")

    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "yfinance is required for fetch. Install project dependencies with `python -m pip install -e .`."
        ) from exc

    raw_data = yf.download(
        symbol,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=True,
        actions=False,
        progress=False,
    )
    return normalize_ohlcv_frame(raw_data)


def normalize_ohlcv_frame(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Return daily OHLCV columns expected by the backtester.

    yfinance may return either normal columns like `Open` or MultiIndex columns
    like `("Open", "SPY")`. The MultiIndex case happens when provider output is
    shaped for one or more tickers, so we flatten it before selecting columns.
    """

    if raw_data.empty:
        raise ValueError("No market data returned for the requested symbol/date range.")

    normalized = raw_data.copy()
    if isinstance(normalized.columns, pd.MultiIndex):
        normalized.columns = [
            _first_non_empty_string(column_parts)
            for column_parts in normalized.columns.to_flat_index()
        ]

    column_map = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    missing_columns = [column for column in column_map if column not in normalized.columns]
    if missing_columns:
        raise ValueError(f"Market data is missing required columns: {missing_columns}")

    normalized = normalized.rename(columns=column_map)
    normalized = normalized.loc[:, ["open", "high", "low", "close", "volume"]]
    normalized = normalized.reset_index()
    date_column = "Date" if "Date" in normalized.columns else normalized.columns[0]
    normalized = normalized.rename(columns={date_column: "date"})

    # The backtester consumes ISO date strings. Keeping only the date avoids
    # timezone/time-of-day details leaking into a daily strategy workflow.
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
    normalized[["open", "high", "low", "close", "volume"]] = normalized[
        ["open", "high", "low", "close", "volume"]
    ].apply(pd.to_numeric, errors="raise")
    return normalized.loc[:, OHLCV_COLUMNS]


def write_market_data_csv(
    data: pd.DataFrame,
    symbol: str,
    start: str,
    end: str,
    output_dir: str | Path,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    csv_path = destination / market_data_filename(symbol, start, end)
    data.to_csv(csv_path, index=False)
    return str(csv_path)


def market_data_filename(symbol: str, start: str, end: str) -> str:
    safe_symbol = re.sub(r"[^A-Za-z0-9._-]+", "_", symbol.strip().upper())
    return f"{safe_symbol}_{start}_{end}.csv"


def _first_non_empty_string(values: tuple[object, ...]) -> str:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return str(values[0])
