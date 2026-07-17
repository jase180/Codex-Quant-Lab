"""Market data fetching and normalization helpers."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .run_metadata import fingerprint_file


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


def write_market_data_provenance(
    *,
    csv_path: str | Path,
    data: pd.DataFrame,
    symbol: str,
    requested_start: str,
    requested_end: str,
    interval: str,
    provider: str = "yfinance",
    fetched_at_utc: str | None = None,
) -> str:
    csv_file = Path(csv_path)
    provenance_path = csv_file.with_suffix(".provenance.json")
    payload = build_market_data_provenance(
        csv_path=csv_file,
        data=data,
        symbol=symbol,
        requested_start=requested_start,
        requested_end=requested_end,
        interval=interval,
        provider=provider,
        fetched_at_utc=fetched_at_utc,
    )
    provenance_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(provenance_path)


def build_market_data_provenance(
    *,
    csv_path: str | Path,
    data: pd.DataFrame,
    symbol: str,
    requested_start: str,
    requested_end: str,
    interval: str,
    provider: str = "yfinance",
    fetched_at_utc: str | None = None,
) -> dict:
    data_dates = pd.to_datetime(data["date"]) if "date" in data.columns and not data.empty else None
    fingerprint = fingerprint_file(csv_path)
    return {
        "provenance_schema_version": "market_data_provenance.v1",
        "provider": provider,
        "symbol": symbol.strip().upper(),
        "requested_start": requested_start,
        "requested_end": requested_end,
        "interval": interval,
        "fetched_at_utc": fetched_at_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "csv_path": str(csv_path),
        "row_count": int(len(data)),
        "data_start": _metadata_date(data_dates.min()) if data_dates is not None else None,
        "data_end": _metadata_date(data_dates.max()) if data_dates is not None else None,
        **fingerprint,
    }


def market_data_filename(symbol: str, start: str, end: str) -> str:
    safe_symbol = re.sub(r"[^A-Za-z0-9._-]+", "_", symbol.strip().upper())
    return f"{safe_symbol}_{start}_{end}.csv"


def _first_non_empty_string(values: tuple[object, ...]) -> str:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return str(values[0])


def _metadata_date(value: pd.Timestamp) -> str:
    return value.date().isoformat()
