# quant_lab

`quant_lab` is the project-specific layer above the generic backtester.

It owns:

- strategy JSON parsing,
- executable rule-based strategies,
- market data fetching,
- buy-and-hold benchmark comparison helpers,
- and the `quant-lab` CLI.

## Main Pieces

- `strategy_schema.py`: strict v1 schema validation for strategy JSON.
- `rule_based_strategy.py`: turns a validated strategy spec into an executable strategy.
- `benchmarks.py`: builds buy-and-hold benchmark curves and report sections.
- `data_fetch.py`: fetches and normalizes daily OHLCV data.
- `data_quality.py`: summarizes suspicious input-data conditions for artifacts.
- `research_index.py`: appends flat JSONL rows to the local research registry.
- `run_metadata.py`: defines the stable `run_metadata.json` artifact model.
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

List previous runs:

```bash
quant-lab list-runs --symbol QQQ --strategy-id sma_crossover --sort sharpe_ratio --limit 10
```

Inspect one run:

```bash
quant-lab show-run --metadata artifacts/run/run_metadata.json
```

Compare runs:

```bash
quant-lab compare-runs \
  --metadata artifacts/run_a/run_metadata.json \
  --metadata artifacts/run_b/run_metadata.json
```

## Sizing

The CLI supports:

- `fixed-shares`: buy a fixed `--quantity` on each entry signal.
- `percent-equity`: invest `--allocation` of available cash on each entry signal.

Percent-equity orders resolve at the next open, which keeps the same timing
model as the rest of the backtester.

## Transaction Costs

`run` and `sweep` support simple cost assumptions:

- `--commission-fixed`: flat cash commission per fill.
- `--commission-rate`: commission as a decimal fraction of trade value.
- `--slippage-bps`: one-way slippage in basis points.

The cost model is applied at the fill. Buys pay above the next open when
slippage is nonzero, sells receive below the next open, and commissions reduce
cash. Sweep summaries include the cost settings so result tables remain
auditable.

## Benchmarks

The CLI adds a buy-and-hold benchmark using the same CSV and initial cash. The
benchmark buys at the first close and marks equity at each later close. Sweep
summaries include benchmark and excess-return columns.

Run and sweep artifacts also include two PNG charts:

- `equity_curve.png`: strategy equity compared with buy-and-hold.
- `drawdown.png`: strategy drawdown compared with buy-and-hold.

Each run directory also includes `run_metadata.json`. The metadata file uses a
versioned nested schema so future fields can be added without changing the
basic structure. It records command tokens, strategy metadata, data range,
sizing, cost assumptions, Git commit, sweep parameters, and artifact paths.

Each run directory also includes `data_quality.json`, and `report.md` includes a
data-quality section. The report warns about suspicious-but-possibly-valid input
conditions; strict OHLCV validation still rejects data the backtester cannot use.

The CLI also appends one flat record per run to `artifacts/research_index.jsonl`
by default. `run_metadata.json` is the detailed per-run source of truth; the
JSONL index is the lab-level table for finding and comparing past runs. Override
the index location with `--index-path`.

`list-runs` reads that index and prints a compact table. It supports filtering
by symbol, strategy id, and run type; sorting by common metrics; ascending
order; row limits; and CSV output with `--csv`.

`show-run` reads one `run_metadata.json` file plus its linked `metrics.json`.
When the metadata points to a research index, it also shows benchmark and trade
count context from the matching index row.

`compare-runs` reads two or more metadata files and prints a compact comparison
table using the same metrics and index context.

## Notes For Future Work

- Consider splitting CLI helpers into smaller modules if `cli.py` keeps growing.
