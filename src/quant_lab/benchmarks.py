"""Benchmark equity curves for strategy comparison."""

from __future__ import annotations

import pandas as pd

from metrics_reporting import RunMetrics, build_metrics_summary


def buy_and_hold_equity_curve(
    data: pd.DataFrame,
    initial_cash: float,
) -> list[dict[str, float | str]]:
    """Build a fully invested buy-and-hold curve from the first close.

    The benchmark uses the same daily rows as the strategy run. It buys at the
    first close and marks the position at each later close. That keeps the
    benchmark simple and reproducible while avoiding intraday assumptions.
    """

    if initial_cash <= 0:
        raise ValueError("initial_cash must be positive.")
    if "date" not in data.columns or "close" not in data.columns:
        raise ValueError("benchmark data must include date and close columns.")

    normalized = data.loc[:, ["date", "close"]].copy()
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
    normalized["close"] = pd.to_numeric(normalized["close"], errors="raise")
    if normalized.empty:
        raise ValueError("benchmark data must not be empty.")

    first_close = float(normalized.iloc[0]["close"])
    if first_close <= 0:
        raise ValueError("first close must be positive.")

    shares = initial_cash / first_close
    return [
        {
            "date": row["date"],
            "equity": shares * float(row["close"]),
        }
        for _, row in normalized.iterrows()
    ]


def buy_and_hold_metrics(data: pd.DataFrame, initial_cash: float) -> RunMetrics:
    return build_metrics_summary(buy_and_hold_equity_curve(data, initial_cash))


def benchmark_summary_fields(metrics: RunMetrics) -> dict[str, float | None]:
    return {
        "benchmark_final_equity": metrics.ending_equity,
        "benchmark_total_return": metrics.total_return,
        "benchmark_cagr": metrics.cagr,
        "benchmark_sharpe_ratio": metrics.sharpe_ratio,
        "benchmark_max_drawdown": metrics.max_drawdown,
    }


def excess_total_return(strategy_total_return: float, benchmark_total_return: float) -> float:
    return strategy_total_return - benchmark_total_return


def benchmark_report_section(metrics: RunMetrics, strategy_total_return: float) -> str:
    excess_return = excess_total_return(strategy_total_return, metrics.total_return)
    return f"""## Benchmark: Buy And Hold

| Metric | Value |
| --- | ---: |
| Final Equity | {metrics.ending_equity:.2f} |
| Total Return | {metrics.total_return:.2%} |
| CAGR | {_format_optional_pct(metrics.cagr)} |
| Sharpe Ratio | {_format_optional_num(metrics.sharpe_ratio)} |
| Max Drawdown | {metrics.max_drawdown:.2%} |
| Excess Total Return | {excess_return:.2%} |
"""


def append_benchmark_section(report: str, metrics: RunMetrics, strategy_total_return: float) -> str:
    return (
        report.rstrip()
        + "\n\n"
        + benchmark_report_section(metrics, strategy_total_return)
        + "\n\n"
        + chart_artifacts_section()
    )


def chart_artifacts_section() -> str:
    return """## Chart Artifacts

- `equity_curve.png`
- `drawdown.png`
"""


def _format_optional_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


def _format_optional_num(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}"
