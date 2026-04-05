"""Reporting helpers for backtest results."""

from __future__ import annotations

from pathlib import Path

from metrics_reporting import (
    RunMetrics,
    build_markdown_report,
    build_metrics_summary,
    save_run_artifacts,
)

from .engine import BacktestResult


def equity_curve_from_result(result: BacktestResult) -> list[dict[str, float | str]]:
    history = result.portfolio_history.reset_index()
    return [
        {
            "date": row["timestamp"].strftime("%Y-%m-%d"),
            "equity": float(row["total_value"]),
        }
        for _, row in history.iterrows()
    ]


def summarize_run_metrics(result: BacktestResult) -> RunMetrics:
    equity_curve = equity_curve_from_result(result)
    return build_metrics_summary(equity_curve)


def build_run_report(result: BacktestResult, run_name: str = "Backtest Run") -> str:
    equity_curve = equity_curve_from_result(result)
    metrics = build_metrics_summary(equity_curve)
    return build_markdown_report(run_name, metrics, equity_curve)


def save_run_report_artifacts(
    result: BacktestResult,
    output_dir: str | Path,
    run_name: str = "Backtest Run",
) -> dict[str, str]:
    equity_curve = equity_curve_from_result(result)
    metrics = build_metrics_summary(equity_curve)
    report = build_markdown_report(run_name, metrics, equity_curve)
    return save_run_artifacts(output_dir, metrics, equity_curve, report)
