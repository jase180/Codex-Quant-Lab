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
- Save reports, metrics, equity curves, trades, and sweep summaries.
- Follow a written research protocol in [AUTORESEARCH.md](AUTORESEARCH.md).

## Project Map

```text
data/
  sample_ohlcv.csv              Small sample dataset.
  strategies/                   Example strategy JSON files.
docs/
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
  --out artifacts/qqq_sma_crossover
```

Outputs:

```text
artifacts/qqq_sma_crossover/
  metrics.json
  equity_curve.csv
  report.md
  trades.csv
```

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
    report.md
    trades.csv
    strategy.json
```

`summary.csv` is sorted by total return, best first.

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

## First Research Lesson

The first real QQQ SMA sweep showed why benchmarks and sizing matter.

With fixed 100-share sizing, the best tested SMA crossover was smoother than
buy-and-hold but underperformed it substantially during the 2015-2025 QQQ
sample:

```text
Best SMA variant: about 48% total return with lower drawdown.
QQQ buy-and-hold: about 553% total return with larger drawdown.
```

That does not make the SMA idea useless. It means the current lab needs a
benchmark feature before results are easy to interpret:

- automatic buy-and-hold benchmark comparisons

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

- No automatic buy-and-hold benchmark in reports yet.
- No transaction costs or slippage.
- No short selling.
- No multi-symbol portfolio support.
- No charts yet.
- `yfinance` data is convenient but should not be treated as institutional-grade
  data without verification.

## Near-Term Roadmap

1. Add buy-and-hold benchmark metrics to `run` and `sweep`.
2. Add charts for equity curve and drawdown.
3. Add transaction costs and slippage.
4. Add richer research summaries.
