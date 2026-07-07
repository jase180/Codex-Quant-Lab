# Codex-Quant-Lab

Codex-Quant-Lab is a small Python quant research lab for testing simple trading
ideas against daily OHLCV market data.

The current project is intentionally modest: it is not a production trading
system, and it is not trying to predict markets. It is a learning and research
tool that makes backtest assumptions visible.

## What Works Today

- Fetch daily market data with `yfinance`.
- Cache normalized OHLCV CSV files locally.
- Define rule-based strategies in strict JSON.
- Execute SMA, EMA, and RSI-based long-only strategies.
- Run one backtest from the CLI.
- Run parameter sweeps from the CLI.
- Save reports, metrics, equity curves, drawdown charts, trades, and sweep summaries.
- Write data-quality summaries for run inputs.
- Compare strategy results with an automatic buy-and-hold benchmark.
- Follow a written research protocol in [AUTORESEARCH.md](AUTORESEARCH.md).

## Project Map

```text
data/
  sample_ohlcv.csv              Small sample dataset.
  strategies/                   Example strategy JSON files.
docs/
  milestone-4-validation-realism.md  Detailed Milestone 4 plan.
  milestones.md                  Project milestone plan.
  research-workflow.md           End-to-end research workflow.
  strategy-schema.md            Strategy schema notes.
src/
  backtester_core/              Backtest engine, portfolio, execution, data validation.
  quant_lab/                    Strategy schema, executable rules, CLI, data fetch.
  metrics_reporting/            Metrics, markdown reports, artifact persistence.
tests/                          Unit and CLI tests.
artifacts/                      Ignored local run outputs.
data/cache/                     Ignored local market-data cache.
```

More detailed module notes:

- [docs/milestones.md](docs/milestones.md)
- [docs/milestone-4-validation-realism.md](docs/milestone-4-validation-realism.md)
- [docs/research-workflow.md](docs/research-workflow.md)
- [src/backtester_core/README.md](src/backtester_core/README.md)
- [src/quant_lab/README.md](src/quant_lab/README.md)
- [src/metrics_reporting/README.md](src/metrics_reporting/README.md)

## Setup

Python 3.10+ is required. In this checkout, prefer WSL for Python commands.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Run the test suite:

```bash
. .venv/bin/activate
python -m unittest discover -s tests
```

The tests avoid live market-data calls. Live fetching is done manually through
the CLI.

## Core Concepts

### Daily OHLCV Data

The backtester expects one row per daily bar:

```text
date,open,high,low,close,volume
```

Fetched data is written under `data/cache/`, which is ignored by Git.

### Signal Timing

The engine uses a conservative daily flow:

- A strategy reads bar `t` at that day's close.
- Orders generated from bar `t` are queued.
- Queued orders fill at bar `t+1` open.
- Portfolio value is recorded at each bar close.
- Final-bar signals do not fill because there is no next open.

This rule is important because it avoids pretending a strategy can trade at a
price that was not known when the signal was generated.

### Strategy JSON

Strategies live in `data/strategies/`. Example:

- [data/strategies/sma_crossover.json](data/strategies/sma_crossover.json)
- [data/strategies/rsi_reversion.json](data/strategies/rsi_reversion.json)
- [data/strategies/ema_trend_follow.json](data/strategies/ema_trend_follow.json)

The v1 schema supports:

- `sma`
- `ema`
- `rsi`
- comparison operators like `gt`, `gte`, `lt`, `lte`, `eq`
- crossover operators like `crosses_above` and `crosses_below`

Schema details are in [docs/strategy-schema.md](docs/strategy-schema.md).

## CLI Usage

### Fetch Data

```bash
quant-lab fetch \
  --symbol QQQ \
  --start 2015-01-01 \
  --end 2025-12-31 \
  --out data/cache
```

Output:

```text
data/cache/QQQ_2015-01-01_2025-12-31.csv
```

The fetch command currently uses adjusted daily prices from `yfinance`. Provider
data can have outages, missing sessions, and corporate-action assumptions, so
treat cached data as research input that may need verification.

### Run One Backtest

```bash
quant-lab run \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --sizing percent-equity \
  --allocation 1.0 \
  --cost-preset retail-liquid \
  --out artifacts/qqq_sma_crossover
```

Outputs:

```text
artifacts/qqq_sma_crossover/
  metrics.json
  equity_curve.csv
  equity_curve.png
  drawdown.png
  data_quality.json
  report.md
  trades.csv
  run_metadata.json

artifacts/research_index.jsonl
```

`report.md` includes a buy-and-hold benchmark section built from the same CSV
date range and initial cash. The PNG charts plot the strategy beside that same
benchmark so the path of returns and drawdowns is easier to inspect than raw
CSV rows.

The cost flags are optional. `--commission-fixed` charges a flat amount per
fill, `--commission-rate` charges a fraction of trade value, and
`--slippage-bps` moves buy fills above the next open and sell fills below the
next open. For example, `--slippage-bps 5` means 0.05% one-way slippage.
Use `--cost-preset` for named assumptions such as `none`, `retail-liquid`,
`retail-conservative`, and `high-friction`. Explicit cost flags override preset
values.

`run_metadata.json` records the command, strategy identity, data range, sizing,
cost assumptions, Git commit, and artifact paths. Treat it as the source of
truth for how a run folder was produced.

`data_quality.json` summarizes suspicious input-data conditions such as missing
OHLCV values, duplicate dates, zero volume, non-positive prices, and large gaps.
These warnings are prompts for review, not automatic proof that the data is bad.

`research_warnings.json` flags weak evidence such as short samples, tiny trade
counts, no trades, no completed exits, and drawdown that is large relative to
return.

Each run also appends one flat JSON line to `artifacts/research_index.jsonl` by
default. Use `--index-path` to write the registry somewhere else.

### List Previous Runs

```bash
quant-lab list-runs \
  --symbol QQQ \
  --strategy-id sma_crossover \
  --run-type sweep_run \
  --sort sharpe_ratio \
  --limit 10
```

This reads `artifacts/research_index.jsonl` by default and prints a compact
table of past runs. Use `--index-path` to inspect a different registry, and
`--csv` when you want comma-separated output.

Inspect one saved run:

```bash
quant-lab show-run --metadata artifacts/qqq_sma_crossover/run_metadata.json
```

This prints the run identity, data range, metrics, benchmark comparison when
available, cost assumptions, artifact paths, and original command.

Compare saved runs:

```bash
quant-lab compare-runs \
  --metadata artifacts/run_a/run_metadata.json \
  --metadata artifacts/run_b/run_metadata.json
```

This prints a compact table with returns, benchmark context, drawdown, Sharpe,
trade count, cost assumptions, and output directories.

### Run A Parameter Sweep

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --sizing percent-equity \
  --allocation 1.0 \
  --out artifacts/research/qqq_sma_crossover_2015_2025
```

Outputs:

```text
artifacts/research/qqq_sma_crossover_2015_2025/
  summary.csv
  research.md
  run_001/
    metrics.json
    equity_curve.csv
    equity_curve.png
    drawdown.png
    data_quality.json
    report.md
    trades.csv
    run_metadata.json
    strategy.json

artifacts/research_index.jsonl
```

`summary.csv` is sorted by total return, best first.

Sweep summaries include buy-and-hold benchmark columns:

```text
benchmark_total_return
benchmark_max_drawdown
excess_total_return
commission_fixed
commission_rate
slippage_bps
```

### Sizing Modes

The CLI supports two sizing modes:

```bash
--sizing fixed-shares --quantity 100
```

Fixed-share sizing buys the same number of shares on every entry signal.

```bash
--sizing percent-equity --allocation 1.0
```

Percent-equity sizing invests a fraction of available cash at the next open.
`--allocation 1.0` means 100% of available cash, while `--allocation 0.5`
means 50%. This mode allows fractional shares internally because it is meant for
research, not broker-order simulation.

For percent-equity buys, the engine sizes the order so the requested allocation
can cover fill price plus commission. This avoids accidentally spending more
cash than the allocation allows.

## First Research Lesson

The first real QQQ SMA sweep showed why benchmarks and sizing matter.

With fixed 100-share sizing, the best tested SMA crossover was smoother than
buy-and-hold but underperformed it substantially during the 2015-2025 QQQ
sample:

```text
Best SMA variant: about 48% total return with lower drawdown.
QQQ buy-and-hold: about 553% total return with larger drawdown.
```

That does not make the SMA idea useless. It shows why every strategy result
needs benchmark context before interpretation.

## Research Workflow

Use [AUTORESEARCH.md](AUTORESEARCH.md) before interpreting results.

Short version:

1. State the research question.
2. Fetch or choose the data.
3. Run a baseline.
4. Run one controlled variation or sweep.
5. Compare against a benchmark.
6. Inspect trades and drawdowns.
7. Decide the next experiment.

Avoid treating a good-looking backtest as proof. Use it as evidence to decide
what to test next.

## Current Limitations

- No short selling.
- No multi-symbol portfolio support.
- Charts are intentionally simple PNG artifacts, not an interactive dashboard.
- `yfinance` data is convenient but should not be treated as institutional-grade
  data without verification.

## Near-Term Roadmap

1. Add richer research summaries.
2. Add more benchmark options.
3. Add optional cost presets for common broker assumptions.
