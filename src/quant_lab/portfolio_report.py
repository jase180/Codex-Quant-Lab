"""Markdown report rendering for portfolio research runs."""

from __future__ import annotations

from metrics_reporting.metrics import RunMetrics
from quant_lab.costs import CostAssumptions
from quant_lab.portfolio_backtest import PortfolioBacktestResult
from quant_lab.portfolio_benchmarks import PortfolioBenchmarkComparison
from quant_lab.portfolio_data import MultiAssetDataSet
from quant_lab.portfolio_spec import PortfolioSpec


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


def _optional_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


def _optional_number(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}"
