"""Multi-symbol data loading for portfolio research."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtester_core.data import validate_ohlcv_data
from quant_lab.data_quality import DataQualityReport, build_data_quality_report
from quant_lab.portfolio_spec import PortfolioSpec, PortfolioSymbolSpec
from quant_lab.run_metadata import fingerprint_file


class PortfolioDataError(ValueError):
    """Raised when portfolio data cannot be loaded into one aligned dataset."""


@dataclass(frozen=True)
class MultiAssetDataSet:
    """Normalized OHLCV data for every symbol in a portfolio spec.

    The first portfolio milestone uses intersection alignment: each symbol is
    trimmed to the exact same dates before any portfolio accounting is allowed.
    That keeps later equity math simple and makes missing-date assumptions
    visible instead of accidental.
    """

    symbols: dict[str, pd.DataFrame]
    calendar: pd.DatetimeIndex
    alignment_policy: str
    data_quality: dict[str, DataQualityReport]
    fingerprints: dict[str, dict[str, str | int]]
    dropped_rows_by_symbol: dict[str, int]


def load_multi_asset_dataset(
    portfolio: PortfolioSpec,
    *,
    base_dir: str | Path | None = None,
    alignment_policy: str = "intersection",
) -> MultiAssetDataSet:
    """Load, validate, and align every symbol CSV in a portfolio spec."""

    if alignment_policy != "intersection":
        raise PortfolioDataError("Only intersection alignment is supported in portfolio_plan.v1.")

    resolved_base_dir = _resolve_base_dir(portfolio, base_dir)
    normalized_by_symbol: dict[str, pd.DataFrame] = {}
    quality_by_symbol: dict[str, DataQualityReport] = {}
    fingerprints_by_symbol: dict[str, dict[str, str | int]] = {}

    for symbol_spec in portfolio.symbols:
        data_path = _resolve_data_path(symbol_spec, resolved_base_dir)
        try:
            raw_data = pd.read_csv(data_path)
            normalized = validate_ohlcv_data(raw_data)
        except FileNotFoundError as exc:
            raise PortfolioDataError(
                f"Data file for {symbol_spec.symbol} does not exist: {data_path}"
            ) from exc
        except Exception as exc:
            raise PortfolioDataError(
                f"Could not load data for {symbol_spec.symbol}: {exc}"
            ) from exc

        normalized_by_symbol[symbol_spec.symbol] = normalized
        quality_by_symbol[symbol_spec.symbol] = build_data_quality_report(raw_data)
        fingerprints_by_symbol[symbol_spec.symbol] = fingerprint_file(data_path)

    calendar = _intersection_calendar(normalized_by_symbol)
    if calendar.empty:
        raise PortfolioDataError("Portfolio symbols do not share any overlapping dates.")

    aligned_by_symbol = {
        symbol: data.loc[calendar].copy()
        for symbol, data in normalized_by_symbol.items()
    }
    dropped_rows_by_symbol = {
        symbol: int(len(data) - len(aligned_by_symbol[symbol]))
        for symbol, data in normalized_by_symbol.items()
    }

    return MultiAssetDataSet(
        symbols=aligned_by_symbol,
        calendar=calendar,
        alignment_policy=alignment_policy,
        data_quality=quality_by_symbol,
        fingerprints=fingerprints_by_symbol,
        dropped_rows_by_symbol=dropped_rows_by_symbol,
    )


def _resolve_base_dir(portfolio: PortfolioSpec, base_dir: str | Path | None) -> Path:
    if base_dir is not None:
        return Path(base_dir)
    if portfolio.source_path is not None:
        return Path(portfolio.source_path).parent
    return Path.cwd()


def _resolve_data_path(symbol_spec: PortfolioSymbolSpec, base_dir: Path) -> Path:
    data_path = Path(symbol_spec.data)
    if data_path.is_absolute():
        return data_path
    return base_dir / data_path


def _intersection_calendar(data_by_symbol: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    calendars = [data.index for data in data_by_symbol.values()]
    common_dates = calendars[0]
    for calendar in calendars[1:]:
        common_dates = common_dates.intersection(calendar)
    return common_dates.sort_values()
