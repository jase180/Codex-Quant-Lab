"""Benchmark comparison helpers for portfolio runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtester_core.data import validate_ohlcv_data
from metrics_reporting import RunMetrics, build_equity_curve, build_metrics_summary
from quant_lab.portfolio_backtest import PortfolioBacktestResult
from quant_lab.portfolio_data import MultiAssetDataSet
from quant_lab.portfolio_spec import PortfolioSpec
from quant_lab.run_metadata import fingerprint_file


class PortfolioBenchmarkError(ValueError):
    """Raised when a portfolio benchmark cannot be built fairly."""


@dataclass(frozen=True)
class PortfolioBenchmarkComparison:
    symbol: str
    data_path: str
    curve: list[dict[str, float | str]]
    metrics: RunMetrics
    excess_total_return: float
    file_sha256: str
    file_size_bytes: int
    modified_at_utc: str


def build_portfolio_benchmark_comparison(
    *,
    portfolio: PortfolioSpec,
    dataset: MultiAssetDataSet,
    result: PortfolioBacktestResult,
    initial_cash: float,
    base_dir: str | Path | None = None,
) -> PortfolioBenchmarkComparison:
    """Build a buy-and-hold benchmark over the portfolio's aligned date range."""

    if initial_cash <= 0:
        raise PortfolioBenchmarkError("initial_cash must be positive.")

    benchmark_path = _resolve_benchmark_path(portfolio, base_dir)
    try:
        raw_data = pd.read_csv(benchmark_path)
        normalized = validate_ohlcv_data(raw_data)
    except FileNotFoundError as exc:
        raise PortfolioBenchmarkError(
            f"Benchmark data file does not exist: {benchmark_path}"
        ) from exc
    except Exception as exc:
        raise PortfolioBenchmarkError(f"Could not load benchmark data: {exc}") from exc

    missing_dates = dataset.calendar.difference(normalized.index)
    if not missing_dates.empty:
        first_missing = missing_dates[0].date().isoformat()
        raise PortfolioBenchmarkError(
            "Benchmark data must cover every aligned portfolio date; "
            f"first missing date is {first_missing}."
        )

    benchmark_data = normalized.loc[dataset.calendar]
    curve = _buy_and_hold_curve(benchmark_data, initial_cash)
    metrics = build_metrics_summary(curve)
    fingerprint = fingerprint_file(benchmark_path)

    return PortfolioBenchmarkComparison(
        symbol=portfolio.benchmark.symbol,
        data_path=str(benchmark_path),
        curve=curve,
        metrics=metrics,
        excess_total_return=result.total_return - metrics.total_return,
        file_sha256=str(fingerprint["file_sha256"]),
        file_size_bytes=int(fingerprint["file_size_bytes"]),
        modified_at_utc=str(fingerprint["modified_at_utc"]),
    )


def _buy_and_hold_curve(
    benchmark_data: pd.DataFrame,
    initial_cash: float,
) -> list[dict[str, float | str]]:
    first_close = float(benchmark_data.iloc[0].close)
    if first_close <= 0:
        raise PortfolioBenchmarkError("Benchmark first close must be positive.")

    shares = initial_cash / first_close
    dates = [timestamp.date().isoformat() for timestamp in benchmark_data.index]
    values = [shares * float(close) for close in benchmark_data["close"]]
    return build_equity_curve(dates, values)


def _resolve_benchmark_path(portfolio: PortfolioSpec, base_dir: str | Path | None) -> Path:
    benchmark_path = Path(portfolio.benchmark.data)
    if benchmark_path.is_absolute():
        return benchmark_path

    if base_dir is not None:
        return Path(base_dir) / benchmark_path
    if portfolio.source_path is not None:
        return Path(portfolio.source_path).parent / benchmark_path
    return Path.cwd() / benchmark_path
