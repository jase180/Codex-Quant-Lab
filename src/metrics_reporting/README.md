# metrics_reporting

`metrics_reporting` turns equity curves into metrics and simple artifacts.

## Included Metrics

- total return
- CAGR
- Sharpe ratio
- max drawdown
- starting equity
- ending equity
- observation count
- caveats for short samples

## Artifact Outputs

`save_run_artifacts(...)` writes:

- `metrics.json`
- `equity_curve.csv`
- `report.md`

The CLI adds `trades.csv` separately because trades belong to the backtest
result, not to the generic metrics module.

## Important Assumptions

- Equity observations are daily.
- Dates are ISO strings and strictly increasing.
- Equity values must be positive.
- CAGR uses 252 trading days per year.
- Sharpe uses daily returns and annualizes by `sqrt(252)`.

## Why This Module Is Separate

Keeping metrics separate from the backtester makes it easier to reuse the same
reporting code for:

- one-off runs,
- parameter sweeps,
- future benchmarks,
- and future imported equity curves.

The current CLI adds buy-and-hold benchmark sections outside this module. The
metrics here stay generic so they can apply to either a strategy curve or a
benchmark curve.
