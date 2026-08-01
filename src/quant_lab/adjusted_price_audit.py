"""Audit provider-adjusted prices against raw provider corporate-action data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .data_fetch import configure_yfinance_cache


@dataclass(frozen=True)
class AdjustedPriceAudit:
    symbol: str
    start: str
    end: str
    provider: str
    fetched_at_utc: str
    rows: int
    compared_rows: int
    max_close_difference: float | None
    missing_expected_dividends: list[str]
    missing_expected_splits: list[str]
    event_rows: int
    result: str
    warnings: list[str]
    comparison_path: str
    json_path: str
    markdown_path: str


def fetch_yfinance_adjustment_sample(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Download adjusted and raw/action views for one provider/date window.

    yfinance exposes adjusted OHLCV through `auto_adjust=True`, while
    `auto_adjust=False, actions=True` includes `Adj Close`, dividends, and stock
    split columns. Comparing those two views is not a second-source validation,
    but it catches accidental fetch-policy drift and makes corporate-action
    dates visible before a research run depends on them.
    """

    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "yfinance is required for adjusted-price audits. Install project dependencies with `python -m pip install -e .`."
        ) from exc

    configure_yfinance_cache()
    adjusted = yf.download(
        symbol,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=True,
        actions=False,
        progress=False,
    )
    raw = yf.download(
        symbol,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=False,
        actions=True,
        progress=False,
    )
    return build_adjusted_price_comparison(adjusted=adjusted, raw=raw)


def build_adjusted_price_comparison(*, adjusted: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    if adjusted.empty:
        raise ValueError("No adjusted market data returned for the requested symbol/date range.")
    if raw.empty:
        raise ValueError("No raw/action market data returned for the requested symbol/date range.")

    adjusted_frame = _flatten_provider_columns(adjusted)
    raw_frame = _flatten_provider_columns(raw)
    _require_columns(adjusted_frame, ["Close"], "adjusted")
    _require_columns(raw_frame, ["Close", "Adj Close"], "raw/action")

    comparison = pd.DataFrame(
        {
            "date": _date_strings(adjusted_frame.index),
            "auto_adjust_close": pd.to_numeric(adjusted_frame["Close"], errors="raise").to_numpy(),
        }
    )
    raw_comparison = pd.DataFrame(
        {
            "date": _date_strings(raw_frame.index),
            "raw_close": pd.to_numeric(raw_frame["Close"], errors="raise").to_numpy(),
            "adj_close": pd.to_numeric(raw_frame["Adj Close"], errors="raise").to_numpy(),
            "dividend": _numeric_or_zero(raw_frame, "Dividends"),
            "stock_split": _numeric_or_zero(raw_frame, "Stock Splits"),
        }
    )
    merged = comparison.merge(raw_comparison, on="date", how="inner")
    if merged.empty:
        raise ValueError("Adjusted and raw/action market data have no overlapping dates.")

    merged["close_difference"] = (merged["auto_adjust_close"] - merged["adj_close"]).abs()
    return merged.loc[
        :,
        [
            "date",
            "auto_adjust_close",
            "adj_close",
            "raw_close",
            "close_difference",
            "dividend",
            "stock_split",
        ],
    ]


def write_adjusted_price_audit(
    *,
    comparison: pd.DataFrame,
    symbol: str,
    start: str,
    end: str,
    out_dir: str | Path,
    expected_dividend_dates: list[str] | None = None,
    expected_split_dates: list[str] | None = None,
    tolerance: float = 0.01,
    provider: str = "yfinance",
    fetched_at_utc: str | None = None,
) -> AdjustedPriceAudit:
    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    normalized_symbol = symbol.strip().upper()
    fetched_at = fetched_at_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    expected_dividends = expected_dividend_dates or []
    expected_splits = expected_split_dates or []

    comparison_path = destination / "adjusted_price_comparison.csv"
    json_path = destination / "adjusted_price_audit.json"
    markdown_path = destination / "adjusted_price_audit.md"
    comparison.to_csv(comparison_path, index=False)

    max_difference = _max_close_difference(comparison)
    missing_dividends = _missing_event_dates(comparison, "dividend", expected_dividends)
    missing_splits = _missing_event_dates(comparison, "stock_split", expected_splits)
    event_rows = _event_row_count(comparison)
    warnings = _audit_warnings(
        max_difference=max_difference,
        tolerance=tolerance,
        missing_dividends=missing_dividends,
        missing_splits=missing_splits,
        event_rows=event_rows,
        expected_dividends=expected_dividends,
        expected_splits=expected_splits,
    )
    result = "pass" if not warnings else "warning"
    payload: dict[str, Any] = {
        "schema_version": "adjusted_price_audit.v1",
        "symbol": normalized_symbol,
        "provider": provider,
        "start": start,
        "end": end,
        "fetched_at_utc": fetched_at,
        "rows": int(len(comparison)),
        "compared_rows": int(comparison["close_difference"].notna().sum()),
        "max_close_difference": max_difference,
        "tolerance": tolerance,
        "expected_dividend_dates": expected_dividends,
        "expected_split_dates": expected_splits,
        "missing_expected_dividends": missing_dividends,
        "missing_expected_splits": missing_splits,
        "event_rows": event_rows,
        "result": result,
        "warnings": warnings,
        "comparison_path": str(comparison_path),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_audit_markdown(payload), encoding="utf-8")

    return AdjustedPriceAudit(
        symbol=normalized_symbol,
        start=start,
        end=end,
        provider=provider,
        fetched_at_utc=fetched_at,
        rows=int(payload["rows"]),
        compared_rows=int(payload["compared_rows"]),
        max_close_difference=max_difference,
        missing_expected_dividends=missing_dividends,
        missing_expected_splits=missing_splits,
        event_rows=event_rows,
        result=result,
        warnings=warnings,
        comparison_path=str(comparison_path),
        json_path=str(json_path),
        markdown_path=str(markdown_path),
    )


def _render_audit_markdown(payload: dict[str, Any]) -> str:
    warnings = payload["warnings"] or ["None"]
    return "\n".join(
        [
            "# Adjusted Price Audit",
            "",
            "Report role: supporting interpretation.",
            "",
            "## Summary",
            "",
            f"- Symbol: {payload['symbol']}",
            f"- Provider: {payload['provider']}",
            f"- Range: {payload['start']} to {payload['end']}",
            f"- Result: {payload['result']}",
            f"- Rows compared: {payload['compared_rows']}",
            f"- Max close difference: {payload['max_close_difference']}",
            f"- Tolerance: {payload['tolerance']}",
            f"- Corporate-action rows: {payload['event_rows']}",
            f"- Comparison CSV: `{payload['comparison_path']}`",
            "",
            "## Expected Events",
            "",
            f"- Expected dividend dates: {_list_or_none(payload['expected_dividend_dates'])}",
            f"- Missing expected dividends: {_list_or_none(payload['missing_expected_dividends'])}",
            f"- Expected split dates: {_list_or_none(payload['expected_split_dates'])}",
            f"- Missing expected splits: {_list_or_none(payload['missing_expected_splits'])}",
            "",
            "## Warnings",
            "",
            *[f"- {warning}" for warning in warnings],
            "",
        ]
    )


def _flatten_provider_columns(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [_first_non_empty_string(column_parts) for column_parts in frame.columns.to_flat_index()]
    return frame


def _first_non_empty_string(values: tuple[object, ...]) -> str:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return str(values[0])


def _require_columns(data: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"{label} market data is missing required columns: {missing}")


def _date_strings(index: pd.Index) -> pd.Series:
    return pd.to_datetime(index).strftime("%Y-%m-%d")


def _numeric_or_zero(data: pd.DataFrame, column: str) -> pd.Series:
    if column not in data.columns:
        return pd.Series([0.0] * len(data), index=data.index)
    return pd.to_numeric(data[column], errors="raise").fillna(0.0)


def _max_close_difference(comparison: pd.DataFrame) -> float | None:
    if comparison.empty:
        return None
    return float(comparison["close_difference"].max())


def _missing_event_dates(comparison: pd.DataFrame, column: str, expected_dates: list[str]) -> list[str]:
    event_dates = set(comparison.loc[comparison[column] != 0, "date"].astype(str))
    return [date for date in expected_dates if date not in event_dates]


def _event_row_count(comparison: pd.DataFrame) -> int:
    return int(((comparison["dividend"] != 0) | (comparison["stock_split"] != 0)).sum())


def _audit_warnings(
    *,
    max_difference: float | None,
    tolerance: float,
    missing_dividends: list[str],
    missing_splits: list[str],
    event_rows: int,
    expected_dividends: list[str],
    expected_splits: list[str],
) -> list[str]:
    warnings: list[str] = []
    if max_difference is None:
        warnings.append("no comparable adjusted close rows")
    elif max_difference > tolerance:
        warnings.append(f"auto-adjusted close differs from Adj Close by more than {tolerance}")
    if missing_dividends:
        warnings.append(f"missing expected dividend dates: {', '.join(missing_dividends)}")
    if missing_splits:
        warnings.append(f"missing expected split dates: {', '.join(missing_splits)}")
    if (expected_dividends or expected_splits) and event_rows == 0:
        warnings.append("no corporate-action rows found in the audited window")
    return warnings


def _list_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "None"
