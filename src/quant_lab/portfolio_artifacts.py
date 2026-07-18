"""Artifact and metadata persistence for portfolio backtests."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from metrics_reporting import build_equity_curve, build_metrics_summary
from metrics_reporting.metrics import RunMetrics
from quant_lab.costs import CostAssumptions
from quant_lab.portfolio_backtest import PortfolioBacktestResult
from quant_lab.portfolio_benchmarks import PortfolioBenchmarkComparison
from quant_lab.portfolio_data import MultiAssetDataSet
from quant_lab.portfolio_spec import PortfolioSpec
from quant_lab.run_artifacts import current_git_commit
from quant_lab.run_metadata import fingerprint_file


@dataclass(frozen=True)
class PortfolioSpecMetadata:
    path: str | None
    file_sha256: str | None
    file_size_bytes: int | None
    modified_at_utc: str | None


@dataclass(frozen=True)
class PortfolioSymbolMetadata:
    symbol: str
    path: str
    target_weight: float
    row_count: int
    aligned_row_count: int
    dropped_rows: int
    start: str | None
    end: str | None
    file_sha256: str | None
    file_size_bytes: int | None
    modified_at_utc: str | None
    quality_severity: str | None


@dataclass(frozen=True)
class PortfolioCostMetadata:
    preset: str
    commission_fixed: float
    commission_rate: float
    slippage_bps: float


@dataclass(frozen=True)
class PortfolioEnvironmentMetadata:
    git_commit: str


@dataclass(frozen=True)
class PortfolioBenchmarkMetadata:
    symbol: str
    data_path: str
    file_sha256: str
    file_size_bytes: int
    modified_at_utc: str
    ending_equity: float
    total_return: float
    cagr: float | None
    sharpe_ratio: float | None
    max_drawdown: float
    excess_total_return: float


@dataclass(frozen=True)
class PortfolioMetadata:
    metadata_schema_version: str
    run_type: str
    created_at_utc: str
    command: list[str]
    portfolio_id: str
    name: str
    schema_version: str
    alignment_policy: str
    rebalance_frequency: str
    initial_cash: float
    benchmark_symbol: str
    benchmark_data: str
    portfolio_spec: PortfolioSpecMetadata
    symbols: list[PortfolioSymbolMetadata]
    costs: PortfolioCostMetadata
    environment: PortfolioEnvironmentMetadata
    benchmark: PortfolioBenchmarkMetadata | None = None
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SavedPortfolioArtifacts:
    metrics: RunMetrics
    artifact_paths: dict[str, str]
    metadata: PortfolioMetadata


def save_portfolio_artifacts(
    *,
    portfolio: PortfolioSpec,
    dataset: MultiAssetDataSet,
    result: PortfolioBacktestResult,
    output_dir: str | Path,
    initial_cash: float,
    cost_assumptions: CostAssumptions,
    benchmark_comparison: PortfolioBenchmarkComparison | None = None,
    command: Sequence[str] = (),
) -> SavedPortfolioArtifacts:
    """Save the first portfolio artifact set and return paths plus metadata."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    equity_curve = _metrics_equity_curve(result)
    metrics = build_metrics_summary(equity_curve)
    artifact_paths = {
        "metrics": _save_json(destination / "portfolio_metrics.json", metrics.to_dict()),
        "equity_curve": _save_frame(result.equity_curve, destination / "portfolio_equity_curve.csv"),
        "positions": _save_frame(result.positions, destination / "portfolio_positions.csv"),
        "trades": _save_frame(result.trades, destination / "portfolio_trades.csv"),
        "allocation_drift": _save_frame(
            result.allocation_drift,
            destination / "portfolio_allocation_drift.csv",
        ),
    }
    if benchmark_comparison is not None:
        artifact_paths["benchmark_metrics"] = _save_json(
            destination / "portfolio_benchmark_metrics.json",
            benchmark_comparison.metrics.to_dict(),
        )
        artifact_paths["benchmark_equity_curve"] = _save_benchmark_curve(
            benchmark_comparison,
            destination / "portfolio_benchmark_equity_curve.csv",
        )
    report = build_portfolio_report(
        portfolio=portfolio,
        dataset=dataset,
        metrics=metrics,
        result=result,
        cost_assumptions=cost_assumptions,
        benchmark_comparison=benchmark_comparison,
    )
    artifact_paths["report"] = _save_text(destination / "portfolio_report.md", report)
    artifact_paths["metadata"] = str(destination / "portfolio_metadata.json")
    metadata = build_portfolio_metadata(
        portfolio=portfolio,
        dataset=dataset,
        initial_cash=initial_cash,
        cost_assumptions=cost_assumptions,
        benchmark_comparison=benchmark_comparison,
        artifact_paths=artifact_paths,
        command=command,
    )
    artifact_paths["metadata"] = save_portfolio_metadata(metadata, destination)
    return SavedPortfolioArtifacts(
        metrics=metrics,
        artifact_paths=artifact_paths,
        metadata=metadata,
    )


def build_portfolio_metadata(
    *,
    portfolio: PortfolioSpec,
    dataset: MultiAssetDataSet,
    initial_cash: float,
    cost_assumptions: CostAssumptions,
    benchmark_comparison: PortfolioBenchmarkComparison | None = None,
    artifact_paths: Mapping[str, str],
    command: Sequence[str] = (),
) -> PortfolioMetadata:
    return PortfolioMetadata(
        metadata_schema_version="portfolio_metadata.v1",
        run_type="portfolio_run",
        created_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        command=[str(token) for token in command],
        portfolio_id=portfolio.portfolio_id,
        name=portfolio.name,
        schema_version=portfolio.schema_version,
        alignment_policy=dataset.alignment_policy,
        rebalance_frequency=portfolio.rebalance.frequency,
        initial_cash=float(initial_cash),
        benchmark_symbol=portfolio.benchmark.symbol,
        benchmark_data=portfolio.benchmark.data,
        portfolio_spec=_portfolio_spec_metadata(portfolio),
        symbols=_symbol_metadata(portfolio, dataset),
        costs=PortfolioCostMetadata(
            preset=cost_assumptions.preset,
            commission_fixed=float(cost_assumptions.commission_fixed),
            commission_rate=float(cost_assumptions.commission_rate),
            slippage_bps=float(cost_assumptions.slippage_bps),
        ),
        environment=PortfolioEnvironmentMetadata(git_commit=current_git_commit()),
        benchmark=_benchmark_metadata(benchmark_comparison),
        artifacts=dict(artifact_paths),
    )


def save_portfolio_metadata(metadata: PortfolioMetadata, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    metadata_path = destination / "portfolio_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(metadata_path)


def build_portfolio_report(
    *,
    portfolio: PortfolioSpec,
    dataset: MultiAssetDataSet,
    metrics: RunMetrics,
    result: PortfolioBacktestResult,
    cost_assumptions: CostAssumptions,
    benchmark_comparison: PortfolioBenchmarkComparison | None = None,
) -> str:
    symbols_table = "\n".join(
        "| {symbol} | {weight:.2%} | {rows} | {dropped} | {severity} |".format(
            symbol=symbol.symbol,
            weight=symbol.target_weight,
            rows=len(dataset.symbols[symbol.symbol]),
            dropped=dataset.dropped_rows_by_symbol[symbol.symbol],
            severity=dataset.data_quality[symbol.symbol].worst_severity,
        )
        for symbol in portfolio.symbols
    )
    caveat_lines = "\n".join(f"- {caveat}" for caveat in metrics.caveats) or "- None."
    benchmark_section = _benchmark_report_section(benchmark_comparison)

    return f"""# {portfolio.name}

## Summary

| Metric | Value |
| --- | ---: |
| Portfolio ID | {portfolio.portfolio_id} |
| Starting Equity | {metrics.starting_equity:.2f} |
| Ending Equity | {metrics.ending_equity:.2f} |
| Total Return | {metrics.total_return:.2%} |
| CAGR | {_optional_percent(metrics.cagr)} |
| Sharpe Ratio | {_optional_number(metrics.sharpe_ratio)} |
| Max Drawdown | {metrics.max_drawdown:.2%} |
| Observations | {metrics.observations} |
| Final Cash | {result.final_cash:.2f} |

## Portfolio Inputs

| Symbol | Target Weight | Aligned Rows | Dropped Rows | Data Quality |
| --- | ---: | ---: | ---: | --- |
{symbols_table}

## Assumptions

- Alignment policy: `{dataset.alignment_policy}`.
- Rebalance frequency: `{portfolio.rebalance.frequency}`.
- Rebalance decisions use close prices and fill at the next aligned open.
- Costs: `{cost_assumptions.preset}`, fixed commission {cost_assumptions.commission_fixed:.4f},
  rate {cost_assumptions.commission_rate:.6f}, slippage {cost_assumptions.slippage_bps:.2f} bps.
- Benchmark input: `{portfolio.benchmark.symbol}` from `{portfolio.benchmark.data}`.

{benchmark_section}

## Caveats

{caveat_lines}
"""


def _metrics_equity_curve(result: PortfolioBacktestResult) -> list[dict[str, float | str]]:
    dates = [timestamp.date().isoformat() for timestamp in result.equity_curve.index]
    values = [float(value) for value in result.equity_curve["total_value"]]
    return build_equity_curve(dates, values)


def _portfolio_spec_metadata(portfolio: PortfolioSpec) -> PortfolioSpecMetadata:
    if portfolio.source_path is None:
        return PortfolioSpecMetadata(
            path=None,
            file_sha256=None,
            file_size_bytes=None,
            modified_at_utc=None,
        )

    fingerprint = fingerprint_file(portfolio.source_path)
    return PortfolioSpecMetadata(
        path=str(portfolio.source_path),
        file_sha256=str(fingerprint["file_sha256"]),
        file_size_bytes=int(fingerprint["file_size_bytes"]),
        modified_at_utc=str(fingerprint["modified_at_utc"]),
    )


def _symbol_metadata(
    portfolio: PortfolioSpec,
    dataset: MultiAssetDataSet,
) -> list[PortfolioSymbolMetadata]:
    metadata: list[PortfolioSymbolMetadata] = []
    for symbol in portfolio.symbols:
        quality = dataset.data_quality[symbol.symbol]
        fingerprint = dataset.fingerprints[symbol.symbol]
        metadata.append(
            PortfolioSymbolMetadata(
                symbol=symbol.symbol,
                path=symbol.data,
                target_weight=float(symbol.target_weight),
                row_count=quality.row_count,
                aligned_row_count=int(len(dataset.symbols[symbol.symbol])),
                dropped_rows=dataset.dropped_rows_by_symbol[symbol.symbol],
                start=quality.start,
                end=quality.end,
                file_sha256=str(fingerprint.get("file_sha256")),
                file_size_bytes=int(fingerprint["file_size_bytes"]),
                modified_at_utc=str(fingerprint.get("modified_at_utc")),
                quality_severity=quality.worst_severity,
            )
        )
    return metadata


def _benchmark_metadata(
    benchmark: PortfolioBenchmarkComparison | None,
) -> PortfolioBenchmarkMetadata | None:
    if benchmark is None:
        return None
    return PortfolioBenchmarkMetadata(
        symbol=benchmark.symbol,
        data_path=benchmark.data_path,
        file_sha256=benchmark.file_sha256,
        file_size_bytes=benchmark.file_size_bytes,
        modified_at_utc=benchmark.modified_at_utc,
        ending_equity=benchmark.metrics.ending_equity,
        total_return=benchmark.metrics.total_return,
        cagr=benchmark.metrics.cagr,
        sharpe_ratio=benchmark.metrics.sharpe_ratio,
        max_drawdown=benchmark.metrics.max_drawdown,
        excess_total_return=benchmark.excess_total_return,
    )


def _benchmark_report_section(benchmark: PortfolioBenchmarkComparison | None) -> str:
    if benchmark is None:
        return "## Benchmark\n\n- Not computed."

    return f"""## Benchmark: Buy And Hold {benchmark.symbol}

| Metric | Value |
| --- | ---: |
| Final Equity | {benchmark.metrics.ending_equity:.2f} |
| Total Return | {benchmark.metrics.total_return:.2%} |
| CAGR | {_optional_percent(benchmark.metrics.cagr)} |
| Sharpe Ratio | {_optional_number(benchmark.metrics.sharpe_ratio)} |
| Max Drawdown | {benchmark.metrics.max_drawdown:.2%} |
| Excess Total Return | {benchmark.excess_total_return:.2%} |"""


def _save_json(path: Path, payload: dict) -> str:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(path)


def _save_text(path: Path, content: str) -> str:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return str(path)


def _save_frame(frame, path: Path) -> str:
    frame.to_csv(path)
    return str(path)


def _save_benchmark_curve(benchmark: PortfolioBenchmarkComparison, path: Path) -> str:
    pd.DataFrame(benchmark.curve).to_csv(path, index=False)
    return str(path)


def _optional_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


def _optional_number(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}"
