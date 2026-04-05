# Codex-Quant-Lab

## Strategy schema

This repo now includes a strict v1 strategy representation for simple rule-based trading ideas:

- Parser and validation: [src/quant_lab/strategy_schema.py](/C:/Users/jase1/repos/Codex-Quant-Lab/src/quant_lab/strategy_schema.py)
- Example strategies: [data/strategies/rsi_reversion.json](/C:/Users/jase1/repos/Codex-Quant-Lab/data/strategies/rsi_reversion.json)
- Schema notes: [docs/strategy-schema.md](/C:/Users/jase1/repos/Codex-Quant-Lab/docs/strategy-schema.md)

Run the tests with:

```powershell
python -m unittest discover -s tests
```

## Backtester Core v1

The default backtester flow is intentionally simple and uses daily OHLCV input for a single instrument.

- A strategy sees one daily bar at a time and can return `buy` or `sell` market orders.
- Orders generated from bar `t` are queued and filled on bar `t+1` at the next bar open.
- End-of-day portfolio history is recorded at each bar close after any queued fill for that day.
- Signals generated on the final bar are not filled because there is no next bar open available.

## Metrics Reporting v1

This repo now includes a small Python module for transparent daily backtest metrics and run reporting under `src/metrics_reporting`, plus thin adapters in `src/backtester_core/reporting.py` for existing `BacktestResult` objects.

### Included metrics

- Sharpe ratio using daily returns and annualization by `sqrt(252)`
- Max drawdown from the running peak of the equity curve
- Total return from first equity value to last equity value
- CAGR using `252` trading days per year
- Markdown report generation
- Artifact persistence to disk as `metrics.json`, `equity_curve.csv`, and `report.md`

### Formula summary

- Daily return: `(equity_t / equity_t-1) - 1`
- Sharpe ratio: `mean(excess daily returns) / stdev(excess daily returns) * sqrt(252)`
- Max drawdown: minimum of `(equity / running_peak) - 1`
- Total return: `(ending_equity / starting_equity) - 1`
- CAGR: `(ending_equity / starting_equity) ** (252 / trading_days) - 1`

### Assumptions

- Inputs are daily observations ordered oldest to newest.
- Equity values are positive.
- Default risk-free rate is `0.0`.
- CAGR uses `252` trading days per year.

### Example usage

```python
from metrics_reporting import (
    build_equity_curve,
    build_markdown_report,
    build_metrics_summary,
    save_run_artifacts,
)

equity_curve = build_equity_curve(
    dates=["2026-03-30", "2026-03-31", "2026-04-01"],
    equity_values=[100000.0, 101250.0, 102800.0],
)

metrics = build_metrics_summary(equity_curve)
report = build_markdown_report("Example Run", metrics, equity_curve)
save_run_artifacts("artifacts/example_run", metrics, equity_curve, report)
```

### Backtester integration

```python
from backtester_core import BacktestEngine, build_run_report, save_run_report_artifacts

result = BacktestEngine(initial_cash=100_000).run(data, strategy)
report = build_run_report(result, run_name="My Backtest")
paths = save_run_report_artifacts(result, "artifacts/my_backtest", run_name="My Backtest")
```
