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

`ExecutionModel` can also apply a `TransactionCostModel`:

- fixed commission per fill,
- percent commission based on trade value,
- one-way slippage in basis points.

Slippage changes the fill price before portfolio accounting sees the fill. Buy
orders pay above the next open, and sell orders receive below the next open.
Commission is stored on the fill and deducted from cash by the portfolio.

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
- `trades`: fill ledger, including fill price and commission
- `final_cash`
- `final_position`
- `final_equity`
- `total_return`

## Notes For Future Work

- Position sizing mostly lives above the engine, but allocation-style orders are resolved by the execution model at the next open.
- The engine is single-symbol and long-only in current workflows.
- Transaction costs are intentionally simple and deterministic; there is no market-impact model.
- Keep timing tests strict when changing execution behavior.
