# Portfolio Workflow

This workflow tests a simple static-weight portfolio across more than one daily
OHLCV CSV.

The first portfolio version is intentionally narrow:

- long-only symbols,
- static target weights,
- periodic rebalancing,
- date-intersection alignment,
- next-aligned-open rebalance fills,
- buy-and-hold benchmark comparison.

It is useful for allocation research. It is not yet an optimizer, live-trading
tool, or automated symbol researcher.

## 1. Fetch The Symbol Data

Fetch each symbol into `data/cache/`:

```bash
quant-lab fetch \
  --symbol QQQ \
  --start 2015-01-01 \
  --end 2025-12-31 \
  --out data/cache

quant-lab fetch \
  --symbol SPY \
  --start 2015-01-01 \
  --end 2025-12-31 \
  --out data/cache
```

The example portfolio spec expects these files:

```text
data/cache/QQQ_2015-01-01_2025-12-31.csv
data/cache/SPY_2015-01-01_2025-12-31.csv
```

## 2. Create Or Review The Portfolio Spec

List the built-in starter templates:

```bash
quant-lab list-portfolio-templates
```

Write the QQQ/SPY 60/40 starter spec:

```bash
quant-lab new-portfolio \
  --template qqq-spy-60-40 \
  --out data/portfolios/qqq_spy_static_60_40.json
```

`new-portfolio` validates the generated JSON with the strict portfolio parser
before writing it. It refuses to overwrite an existing file unless `--force` is
provided.

Start with:

[data/portfolios/qqq_spy_static_60_40.json](../data/portfolios/qqq_spy_static_60_40.json)

The important fields are:

- `symbols`: each portfolio component and its CSV path.
- `target_weight`: the desired static allocation weight.
- `rebalance.frequency`: `none`, `monthly`, `quarterly`, or `annually`.
- `benchmark`: one symbol CSV used for the buy-and-hold comparison.

Weights must sum to `1.0`.

## 3. Generate Weight Variants

Create a small set of allocation variants from the base spec:

```bash
quant-lab portfolio-variants \
  --portfolio data/portfolios/qqq_spy_static_60_40.json \
  --weights QQQ=0.50,SPY=0.50 \
  --weights QQQ=0.60,SPY=0.40 \
  --weights QQQ=0.70,SPY=0.30 \
  --rebalance none \
  --rebalance monthly \
  --rebalance quarterly \
  --out data/portfolios/variants/qqq_spy
```

Each generated file is a normal `portfolio_plan.v1` JSON file. The command
keeps the base spec's data paths and benchmark, then validates each generated
spec before writing it. Repeated `--weights` and repeated `--rebalance` values
produce every requested combination. If `--rebalance` is omitted, the command
keeps the base spec's rebalance frequency. It refuses to overwrite generated
files unless `--force` is provided.

Run generated variants by passing one generated JSON file to `portfolio-run`.

## 4. Generate Candidate Specs

For a broader but still capped search, generate a coarse candidate grid from
explicit symbols:

```bash
quant-lab portfolio-candidates \
  --symbols QQQ,SPY,TLT \
  --step 0.25 \
  --data-dir data/cache \
  --max-candidates 25 \
  --out data/portfolios/candidates/qqq_spy_tlt
```

The command requires at least two symbols, uses positive weights that sum to
`1.0`, and caps generated files with `--max-candidates`. It resolves data files
from `--data-dir` by first looking for `SYMBOL.csv`, then for exactly one
`SYMBOL_*.csv` match. It writes candidate specs only and does not run
backtests.

## 5. Run The Portfolio

```bash
quant-lab portfolio-run \
  --portfolio data/portfolios/qqq_spy_static_60_40.json \
  --initial-cash 100000 \
  --cost-preset retail-liquid \
  --out artifacts/research/qqq_spy_static_60_40/baseline
```

This writes:

```text
artifacts/research/qqq_spy_static_60_40/baseline/
  portfolio_metrics.json
  portfolio_equity_curve.csv
  portfolio_positions.csv
  portfolio_trades.csv
  portfolio_allocation_drift.csv
  portfolio_benchmark_metrics.json
  portfolio_benchmark_equity_curve.csv
  portfolio_report.md
  portfolio_metadata.json

artifacts/research_index.jsonl
```

## 6. Read The Result

Start with the CLI summary:

```bash
quant-lab show-portfolio-run \
  --metadata artifacts/research/qqq_spy_static_60_40/baseline/portfolio_metadata.json
```

Then read `portfolio_report.md`.

Then inspect:

- `portfolio_metadata.json` for data fingerprints, costs, rebalance settings,
  benchmark input, command tokens, and git commit.
- `portfolio_trades.csv` for next-open rebalance fills.
- `portfolio_positions.csv` for per-symbol holdings and weights.
- `portfolio_allocation_drift.csv` for target-versus-actual weight drift.
- `portfolio_benchmark_metrics.json` for the buy-and-hold benchmark result.

Before comparing variants, write a per-symbol data trust report:

```bash
quant-lab summarize-portfolio-data-trust \
  --metadata artifacts/research/qqq_spy_static_60_40/baseline/portfolio_metadata.json
```

The report verifies every symbol CSV and benchmark input against saved
fingerprints, then summarizes quality severity, aligned rows, dropped rows, and
provenance status.

## 7. Compare Portfolio Runs

After you have two saved portfolio runs, compare them from metadata:

```bash
quant-lab compare-portfolio-runs \
  --metadata artifacts/research/portfolio_a/portfolio_metadata.json \
  --metadata artifacts/research/portfolio_b/portfolio_metadata.json
```

The comparison table shows portfolio id, symbols, rebalance frequency, total
return, benchmark return, excess return, max drawdown, Sharpe ratio, cost
preset, and output directory.

## 8. Summarize Portfolio Evidence

After multiple portfolio runs are linked to one experiment, write a
portfolio-specific evidence note:

```bash
quant-lab summarize-portfolio-experiment \
  --experiment-id EXP-001 \
  --out artifacts/research/qqq_spy_static_60_40/portfolio_summary.md
```

The summary ranks linked `portfolio_run` rows by excess return, total return,
Sharpe ratio, and drawdown. It also calls out benchmark underperformers and
large drawdowns so the evidence stays skeptical instead of becoming a single
magic score.

## 9. Use A Guided Portfolio Plan

When you have a portfolio hypothesis, create a durable local plan before
running the baseline:

```bash
quant-lab portfolio-plan init \
  --title "QQQ SPY allocation check" \
  --hypothesis "A 60/40 QQQ/SPY allocation may improve return versus SPY buy-and-hold." \
  --portfolio data/portfolios/qqq_spy_static_60_40.json \
  --tag QQQ \
  --tag SPY \
  --cost-preset retail-liquid \
  --out artifacts/research/qqq_spy_static_60_40
```

This writes:

```text
artifacts/research/qqq_spy_static_60_40/
  portfolio_research_plan.json
  portfolio_research_plan.md
```

It also creates or references an experiment id and prints the first
`portfolio-run` command. After each run, ask for the next step:

```bash
quant-lab portfolio-plan next \
  --plan artifacts/research/qqq_spy_static_60_40/portfolio_research_plan.json
```

The first version recommends:

- `portfolio-run` when no linked portfolio run exists.
- `summarize-portfolio-data-trust` when a linked portfolio run exists but its
  data trust report has not been written.
- `show-portfolio-run` when one linked portfolio run exists and data trust has
  already been checked.
- `summarize-portfolio-experiment` when multiple linked portfolio runs exist
  and `portfolio_summary.md` is not present.
- `portfolio-variants` when a summary exists but no generated variants are known
  under `portfolio_variants/*.json`.
- `compare-portfolio-runs` when variants and a summary are both known.
- `done` after the experiment has a recorded decision.

## Assumptions To Remember

- Symbols are aligned by date intersection. Rows missing from any symbol are
  dropped from the run window.
- Rebalance decisions use close prices and fill at the next aligned open.
- The first available aligned session in a rebalance period can trigger the
  rebalance decision.
- Final-bar rebalance signals do not fill.
- Benchmark data must cover every aligned portfolio date.
- Data files are local research inputs. If a CSV changes, the saved fingerprints
  make that visible.
