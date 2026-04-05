# Sample Strategy Run

## Summary

| Metric | Value |
| --- | ---: |
| Start Date | 2026-03-30 |
| End Date | 2026-04-03 |
| Starting Equity | 100000.00 |
| Ending Equity | 106900.00 |
| Total Return | 6.90% |
| CAGR | 6580.43% |
| Sharpe Ratio | 29.8441 |
| Max Drawdown | 0.00% |
| Observations | 5 |

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

- CAGR is annualized from fewer than 252 trading days, so short samples can look extreme.

## Equity Curve Snapshot

| Date | Equity |
| --- | ---: |
| 2026-03-30 | 100000.00 |
| 2026-03-31 | 102000.00 |
| 2026-04-01 | 103500.00 |
| 2026-04-02 | 105250.00 |
| 2026-04-03 | 106900.00 |
