from __future__ import annotations

from typing import Sequence

from .metrics import RunMetrics, validate_equity_curve


def _format_pct(value: float) -> str:
    return f"{value:.2%}"


def _format_num(value: float) -> str:
    return f"{value:.4f}"


def _format_optional_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return _format_pct(value)


def _format_optional_num(value: float | None) -> str:
    if value is None:
        return "N/A"
    return _format_num(value)


def build_markdown_report(
    run_name: str,
    metrics: RunMetrics,
    equity_curve: Sequence[dict[str, float | str]],
) -> str:
    validated_curve = validate_equity_curve(equity_curve)
    start_date = validated_curve[0]["date"]
    end_date = validated_curve[-1]["date"]
    latest_rows = validated_curve[-5:]
    table_rows = "\n".join(
        f"| {point['date']} | {float(point['equity']):.2f} |"
        for point in latest_rows
    )
    caveat_lines = "\n".join(f"- {caveat}" for caveat in metrics.caveats)
    if not caveat_lines:
        caveat_lines = "- None."

    return f"""# {run_name}

## Summary

| Metric | Value |
| --- | ---: |
| Start Date | {start_date} |
| End Date | {end_date} |
| Starting Equity | {metrics.starting_equity:.2f} |
| Ending Equity | {metrics.ending_equity:.2f} |
| Total Return | {_format_pct(metrics.total_return)} |
| CAGR | {_format_optional_pct(metrics.cagr)} |
| Sharpe Ratio | {_format_optional_num(metrics.sharpe_ratio)} |
| Max Drawdown | {_format_pct(metrics.max_drawdown)} |
| Observations | {metrics.observations} |

## Formula Notes

- Daily return: `(equity_t / equity_t-1) - 1`
- Sharpe ratio: `mean(excess daily returns) / stdev(excess daily returns) * sqrt(252)`
- Max drawdown: minimum of `(equity / running_peak) - 1`
- Total return: `(ending_equity / starting_equity) - 1`
- CAGR: `(ending_equity / starting_equity) ** (252 / trading_days) - 1`

## Assumptions

- The input series is daily, uses ISO-8601 dates, and is ordered strictly oldest to newest.
- Dates must be unique.
- Equity values are positive and already reflect strategy PnL.
- The default risk-free rate is `0.0`.
- CAGR uses `252` trading days per year.

## Caveats

{caveat_lines}

## Equity Curve Snapshot

| Date | Equity |
| --- | ---: |
{table_rows}
"""
