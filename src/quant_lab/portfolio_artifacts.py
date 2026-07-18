"""Artifact and metadata persistence for portfolio backtests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd

from metrics_reporting import build_equity_curve, build_metrics_summary
from metrics_reporting.metrics import RunMetrics
from quant_lab.costs import CostAssumptions
from quant_lab.portfolio_backtest import PortfolioBacktestResult
from quant_lab.portfolio_benchmarks import PortfolioBenchmarkComparison
from quant_lab.portfolio_data import MultiAssetDataSet
from quant_lab.portfolio_metadata import (
    PortfolioMetadata,
    build_portfolio_metadata,
    save_portfolio_metadata,
)
from quant_lab.portfolio_report import build_portfolio_report
from quant_lab.portfolio_spec import PortfolioSpec


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


def _metrics_equity_curve(result: PortfolioBacktestResult) -> list[dict[str, float | str]]:
    dates = [timestamp.date().isoformat() for timestamp in result.equity_curve.index]
    values = [float(value) for value in result.equity_curve["total_value"]]
    return build_equity_curve(dates, values)


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
