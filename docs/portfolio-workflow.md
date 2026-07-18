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

## 2. Review The Portfolio Spec

Start with:

[data/portfolios/qqq_spy_static_60_40.json](../data/portfolios/qqq_spy_static_60_40.json)

The important fields are:

- `symbols`: each portfolio component and its CSV path.
- `target_weight`: the desired static allocation weight.
- `rebalance.frequency`: `none`, `monthly`, `quarterly`, or `annually`.
- `benchmark`: one symbol CSV used for the buy-and-hold comparison.

Weights must sum to `1.0`.

## 3. Run The Portfolio

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

## 4. Read The Result

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

## 5. Compare Portfolio Runs

After you have two saved portfolio runs, compare them from metadata:

```bash
quant-lab compare-portfolio-runs \
  --metadata artifacts/research/portfolio_a/portfolio_metadata.json \
  --metadata artifacts/research/portfolio_b/portfolio_metadata.json
```

The comparison table shows portfolio id, symbols, rebalance frequency, total
return, benchmark return, excess return, max drawdown, Sharpe ratio, cost
preset, and output directory.

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
