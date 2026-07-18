# quant_lab

`quant_lab` is the project-specific layer above the generic backtester.

It owns:

- strategy JSON parsing,
- executable rule-based strategies,
- market data fetching,
- benchmark comparison helpers,
- and the `quant-lab` CLI.

## Main Pieces

- `strategy_schema.py`: strict v1 schema validation for strategy JSON.
- `strategy_templates.py`: built-in starter strategy JSON templates.
- `rule_based_strategy.py`: turns a validated strategy spec into an executable strategy.
- `benchmarks.py`: builds benchmark curves and report sections.
- `data_fetch.py`: fetches and normalizes daily OHLCV data.
- `data_source.py`: inspects cached CSV data and fetch provenance sidecars.
- `data_quality.py`: summarizes suspicious input-data conditions for artifacts.
- `portfolio_spec.py`: validates explicit `portfolio_plan.v1` multi-symbol
  allocation JSON.
- `portfolio_data.py`: loads portfolio CSV inputs, fingerprints them, and aligns
  symbols to a shared date calendar.
- `portfolio_backtest.py`: runs static-weight portfolio simulations with
  next-open rebalance fills.
- `portfolio_benchmarks.py`: builds buy-and-hold benchmark comparisons over the
  same aligned portfolio dates.
- `portfolio_artifacts.py`: writes portfolio metrics, CSV outputs, reports, and
  metadata.
- `portfolio_execution.py`: shared portfolio-run execution and research-index
  persistence.
- `portfolio_metadata.py`: defines and writes the stable
  `portfolio_metadata.json` shape.
- `portfolio_report.py`: renders the portfolio markdown report.
- `portfolio_inspection.py`: loads and formats saved portfolio run summaries.
- `portfolio_batch.py`: writes dry-run manifests for batches of portfolio specs.
- `research_index.py`: appends flat JSONL rows to the local research registry.
- `run_metadata.py`: defines the stable `run_metadata.json` artifact model.
- `sweep_guardrails.py`: reads sweep `summary.csv` files and writes skeptical
  markdown guardrail reports.
- `cli.py`: implements `quant-lab fetch`, `quant-lab run`, `quant-lab sweep`,
  and run inspection commands.

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
- rolling_high
- rolling_low

All indicators are close-based in v1. `rolling_high` and `rolling_low` use the
prior `length` closes, excluding the current close, so breakout rules can compare
the current close against a level that was already known.

## Supported Conditions

- `gt`
- `gte`
- `lt`
- `lte`
- `eq`
- `crosses_above`
- `crosses_below`

## CLI Commands

List strategy templates:

```bash
quant-lab list-strategy-templates
```

Create a strategy JSON file:

```bash
quant-lab new-strategy \
  --template sma-crossover \
  --symbol QQQ \
  --strategy-id qqq_sma_crossover \
  --name "QQQ SMA Crossover" \
  --out data/strategies/qqq_sma_crossover.json
```

`new-strategy` validates the generated payload with the same strict v1 parser
used by backtests. It refuses to overwrite an existing file unless `--force` is
provided.

Built-in templates are `sma-crossover`, `ema-trend-follow`, `rsi-reversion`,
and `breakout-trend`.

Fetch data:

```bash
quant-lab fetch --symbol QQQ --start 2015-01-01 --end 2025-12-31 --out data/cache
```

Inspect one cached CSV and its provenance sidecar:

```bash
quant-lab show-data-source --data data/cache/QQQ_2015-01-01_2025-12-31.csv
```

Run one strategy:

```bash
quant-lab run \
  --strategy data/strategies/sma_crossover.json \
  --data data/sample_ohlcv.csv \
  --sizing percent-equity \
  --allocation 1.0 \
  --note "Hypothesis: test whether trend following reduces drawdown." \
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

Sweep `research.md` includes:

- a top-runs table,
- the selected benchmark return,
- a parameter-stability heuristic for the best row.

The stability heuristic checks one-parameter neighbors around the best run and
labels the result as `supported`, `mixed`, `isolated`, or `grid_too_sparse`.
This is only a research prompt; it is not statistical proof.

Write a guardrail report for an existing sweep summary:

```bash
quant-lab summarize-sweep-guardrails \
  --summary artifacts/research/sma_sweep/summary.csv
```

The report warns about broad grids, tiny trade counts, fragile parameter
winners, and benchmark underperformance. It does not rerun or change the sweep.

Run a train/test sweep:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/sample_ohlcv.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --train-end 2020-12-31 \
  --test-start 2021-01-01 \
  --select-by total_return \
  --out artifacts/research/sma_train_test
```

Providing `--train-end` and `--test-start` switches `sweep` into train/test
mode. The command runs every parameter variant on rows up to `--train-end`,
selects the best train row by `--select-by`, and reruns only that selected
variant on rows from `--test-start` onward. The dates must be disjoint:
`--train-end` must be earlier than `--test-start`.

Train/test output uses this shape:

```text
artifacts/research/sma_train_test/
  research.md
  train_sweep/
    summary.csv
    run_001/
  test_summary/
    summary.csv
  test_selected/
    run_metadata.json
```

The selected test run is recorded with run type `test_selected_run`. Its
metadata parameters include the split dates, the selection metric, and the
selected train run id.

Plan a dry-run portfolio batch:

```bash
quant-lab portfolio-batch plan \
  --portfolios data/portfolios/candidates/qqq_spy_tlt \
  --out artifacts/research/qqq_spy_tlt/batch_001 \
  --initial-cash 100000 \
  --cost-preset retail-liquid
```

The batch planner validates each portfolio JSON file and writes
`portfolio_batch_manifest.json`. It records planned `portfolio-run` command
tokens but does not execute them.

Run a saved portfolio batch manifest:

```bash
quant-lab portfolio-batch run \
  --manifest artifacts/research/qqq_spy_tlt/batch_001/portfolio_batch_manifest.json \
  --experiment-id EXP-001
```

The runner executes each manifest item sequentially through the same portfolio
artifact path as `portfolio-run`. It writes `portfolio_batch_result.json` with
completed, failed, and skipped item statuses.

Summarize a portfolio batch:

```bash
quant-lab portfolio-batch summarize \
  --manifest artifacts/research/qqq_spy_tlt/batch_001/portfolio_batch_manifest.json
```

The summary command writes `portfolio_batch_summary.md` with batch counts and
guardrail warnings. It can summarize a dry-run manifest before execution, but
will warn that no performance evidence exists yet.

`portfolio-plan next` can recommend the same batch sequence when a guided
portfolio research directory contains candidate specs, a batch manifest, or a
batch result that still needs a guardrail summary.

Run walk-forward windows:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/sample_ohlcv.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --walk-forward-window 2015-01-01,2018-12-31,2019-01-01,2020-12-31 \
  --walk-forward-window 2017-01-01,2020-12-31,2021-01-01,2022-12-31 \
  --select-by sharpe_ratio \
  --out artifacts/research/sma_walk_forward
```

Each `--walk-forward-window` value is `train_start,train_end,test_start,test_end`.
The command writes `walk_forward_summary.csv`, root `research.md`, and one
`window_###/` artifact directory per window. Each test run is recorded with run
type `walk_forward_test_run`.

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

- `--cost-preset`: named cost preset.
- `--commission-fixed`: flat cash commission per fill.
- `--commission-rate`: commission as a decimal fraction of trade value.
- `--slippage-bps`: one-way slippage in basis points.

The cost model is applied at the fill. Buys pay above the next open when
slippage is nonzero, sells receive below the next open, and commissions reduce
cash. Sweep summaries include the cost settings so result tables remain
auditable.

Available presets are `none`, `retail-liquid`, `retail-conservative`, and
`high-friction`. Explicit numeric cost flags override preset values.

## Benchmarks

The CLI adds a benchmark using the same CSV and initial cash. Buy-and-hold is
the default and buys at the first close, then marks equity at each later close.
`--benchmark cash` uses a flat cash curve over the same dates. Sweep summaries
include benchmark name, benchmark metrics, and excess-return columns.

Run and sweep artifacts also include two PNG charts:

- `equity_curve.png`: strategy equity compared with the selected benchmark.
- `drawdown.png`: strategy drawdown compared with the selected benchmark.

Each run directory also includes `run_metadata.json`. The metadata file uses a
versioned nested schema so future fields can be added without changing the
basic structure. It records command tokens, strategy metadata, data range,
sizing, cost assumptions, benchmark choice, Git commit, sweep parameters, and
artifact paths.

Each run directory also includes `data_quality.json`, and `report.md` includes a
data-quality section. The report warns about suspicious-but-possibly-valid input
conditions; strict OHLCV validation still rejects data the backtester cannot use.

Each run also includes `research_warnings.json`. These warnings call out weak
evidence conditions such as short samples, tiny trade counts, no trades, no
completed exits, and drawdown that is large relative to return. They are meant
to guide skepticism, not reject runs automatically.

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

## Research Notes

`run` and `sweep` accept one optional note source:

- `--note`: inline note text.
- `--note-file`: path to a markdown or text file.

The note is saved as `research_note.md`. For one run, the note is saved in that
run directory. For sweeps, the note is saved at the sweep root and each sub-run
metadata links to it. This keeps the hypothesis or conclusion attached to the
artifacts that produced the result.

## Notes For Future Work

- Consider splitting CLI helpers into smaller modules if `cli.py` keeps growing.
