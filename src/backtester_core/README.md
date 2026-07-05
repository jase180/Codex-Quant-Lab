# backtester_core

`backtester_core` contains the small deterministic backtesting engine.

## Main Pieces

- `data.py`: validates OHLCV data and converts rows into `MarketBar` objects.
- `strategy.py`: defines the base `Strategy` class and order helpers.
- `execution.py`: turns queued orders into fills.
- `portfolio.py`: tracks cash, position, trades, and equity history.
- `engine.py`: runs the bar-by-bar loop.
- `reporting.py`: adapts `BacktestResult` objects into metrics/report artifacts.

## Execution Model

The core rule is:

```text
signal at bar t close -> fill at bar t+1 open
```

That means a strategy cannot see a close price and magically trade at that same
close. The order waits until the next bar open.

## Data Shape

The engine expects daily OHLCV data:

```text
date,open,high,low,close,volume
```

The `date` column is converted into a pandas `DatetimeIndex`. The engine sorts
the data by date and rejects duplicate dates.

## Result Shape

`BacktestEngine.run(...)` returns a `BacktestResult` with:

- `portfolio_history`: end-of-day cash, position, holdings value, and total value
- `trades`: fill ledger
- `final_cash`
- `final_position`
- `final_equity`
- `total_return`

## Notes For Future Work

- Position sizing currently lives above the engine, mostly in strategy behavior.
- The engine is single-symbol and long-only in current workflows.
- Transaction costs and slippage are not modeled yet.
- Keep timing tests strict when changing execution behavior.
