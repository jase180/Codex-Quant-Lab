# quant_lab

`quant_lab` is the project-specific layer above the generic backtester.

It owns:

- strategy JSON parsing,
- executable rule-based strategies,
- market data fetching,
- and the `quant-lab` CLI.

## Main Pieces

- `strategy_schema.py`: strict v1 schema validation for strategy JSON.
- `rule_based_strategy.py`: turns a validated strategy spec into an executable strategy.
- `data_fetch.py`: fetches and normalizes daily OHLCV data.
- `cli.py`: implements `quant-lab fetch`, `quant-lab run`, and `quant-lab sweep`.

## Strategy Flow

```text
strategy JSON
  -> parse_strategy / load_strategy
  -> StrategySpec dataclasses
  -> RuleBasedStrategy
  -> BacktestEngine
```

The schema validates the shape of the idea. `RuleBasedStrategy` handles the
runtime behavior: indicator updates, condition checks, and order generation.

## Supported Indicators

- SMA
- EMA
- RSI

All indicators are close-based in v1.

## Supported Conditions

- `gt`
- `gte`
- `lt`
- `lte`
- `eq`
- `crosses_above`
- `crosses_below`

## CLI Commands

Fetch data:

```bash
quant-lab fetch --symbol QQQ --start 2015-01-01 --end 2025-12-31 --out data/cache
```

Run one strategy:

```bash
quant-lab run \
  --strategy data/strategies/sma_crossover.json \
  --data data/sample_ohlcv.csv \
  --sizing percent-equity \
  --allocation 1.0 \
  --out artifacts/run
```

Run a sweep:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/sample_ohlcv.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --sizing percent-equity \
  --allocation 1.0 \
  --out artifacts/research/sma_sweep
```

## Sizing

The CLI supports:

- `fixed-shares`: buy a fixed `--quantity` on each entry signal.
- `percent-equity`: invest `--allocation` of available cash on each entry signal.

Percent-equity orders resolve at the next open, which keeps the same timing
model as the rest of the backtester.

## Notes For Future Work

- Add automatic buy-and-hold benchmarks.
- Add transaction costs and slippage.
- Consider splitting CLI helpers into smaller modules if `cli.py` keeps growing.
