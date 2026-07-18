# Milestone 8: Portfolio And Multi-Asset Research

## Status

In progress.

## Goal

Move the lab from single-symbol strategy checks to simple portfolio-level
research while preserving the same local, inspectable audit trail.

This milestone should answer questions like:

- What happens if I hold a static basket of symbols?
- How does a simple allocation compare with a benchmark?
- How much do costs and rebalance assumptions matter?
- Which symbol contributed most to the portfolio result?

It should not try to solve broad alpha discovery yet. The first useful version
is a portfolio research harness, not an automated hedge fund.

## Current Starting Point

The current engine is intentionally single-symbol:

- one OHLCV CSV,
- one strategy JSON,
- one portfolio cash/share ledger,
- next-bar-open fills,
- close-to-close equity reporting,
- local run artifacts and metadata.

Milestone 8 should keep those strengths. The hard part is not just loading more
CSV files; it is making the assumptions around date alignment, allocation,
rebalancing, costs, and metadata explicit enough that future research remains
trustworthy.

## Non-Goals

- No live trading.
- No broker integration.
- No database requirement.
- No intraday data.
- No margin, shorting, options, futures, or leverage in the first version.
- No automatic symbol discovery or web research in the first version.
- No portfolio optimizer in the first version.
- No machine-learning model selection in the first version.

Those can come later if the simpler portfolio workflow proves useful.

## Proposed First Data Model

Start with an explicit multi-symbol dataset object:

```text
MultiAssetDataSet
  symbols: dict[str, DataFrame]
  calendar: list[date]
  alignment_policy: "intersection"
  data_quality: dict[str, DataQualitySummary]
  fingerprints: dict[str, CsvFingerprint]
```

The first alignment policy should be `intersection`: only dates present for
every symbol are used. That is conservative and easy to reason about. Later, the
lab can add explicit missing-data policies such as forward-fill or symbol-level
cash parking, but those choices are too easy to hide accidentally if they arrive
first.

Each symbol should keep its own input fingerprint and data-quality summary in
the final metadata. A portfolio run is only reproducible if every component CSV
is accounted for.

## Proposed First Portfolio Spec

Use a small JSON file separate from the existing single-symbol strategy schema:

```json
{
  "schema_version": "portfolio_plan.v1",
  "portfolio_id": "qqq_spy_static_60_40",
  "name": "QQQ SPY Static 60/40",
  "description": "Static daily portfolio research example.",
  "symbols": [
    {
      "symbol": "QQQ",
      "data": "data/cache/QQQ_2015-01-01_2025-12-31.csv",
      "target_weight": 0.60
    },
    {
      "symbol": "SPY",
      "data": "data/cache/SPY_2015-01-01_2025-12-31.csv",
      "target_weight": 0.40
    }
  ],
  "rebalance": {
    "frequency": "monthly"
  },
  "benchmark": {
    "symbol": "SPY",
    "data": "data/cache/SPY_2015-01-01_2025-12-31.csv"
  }
}
```

This keeps portfolio construction explicit. The existing strategy JSON remains
focused on single-symbol signal rules. The portfolio spec owns allocation,
symbol inputs, and rebalance behavior.

## Accounting Rules

The first portfolio engine should use these rules:

- Initial cash starts as a single portfolio cash balance.
- Target weights are converted into target market values.
- Rebalance orders fill at the next available open after the rebalance signal.
- Valuation happens at each aligned date's close.
- Costs use the same commission and slippage model as single-symbol runs.
- Fractional shares can stay allowed if the current sizing model already permits
  that style in practice; otherwise use whole shares and record leftover cash.
- Final-bar rebalance orders do not fill because there is no next open.

The key principle is consistency with the current engine: decide with known
information, fill on the next bar, and record the assumption plainly.

## Proposed CLI

Start with one top-level command:

```bash
quant-lab portfolio-run \
  --portfolio data/portfolios/qqq_spy_static_60_40.json \
  --initial-cash 100000 \
  --cost-preset retail-liquid \
  --out artifacts/research/qqq_spy_static_60_40/baseline
```

A top-level `portfolio-run` command matches the existing CLI style and avoids
reworking parser structure before the feature needs it. If portfolio commands
multiply later, they can be grouped.

## Deliverables

### 1. Multi-Symbol Data Loader

Status: delivered.

Build a loader that accepts the portfolio spec, validates every CSV, normalizes
each symbol to the current OHLCV expectations, aligns dates, and returns a
multi-symbol dataset.

Acceptance criteria:

- Valid portfolio specs load into a typed object.
- Missing symbols, bad weights, bad CSV paths, duplicate symbols, and invalid
  OHLCV data fail with explicit errors.
- Date alignment is deterministic and documented.
- Unit tests cover happy path and failure cases.

Delivered implementation:

- `quant_lab.portfolio_spec` validates strict `portfolio_plan.v1` JSON.
- `quant_lab.portfolio_data` loads symbol CSVs, validates OHLCV shape,
  fingerprints each input file, summarizes per-symbol data quality, and aligns
  symbols by date intersection.
- `tests/test_portfolio_spec.py` and `tests/test_portfolio_data.py` cover the
  first parser and loader behavior.

### 2. Static-Weight Portfolio Backtest

Status: delivered.

Build the first portfolio engine around static target weights and periodic
rebalancing.

Acceptance criteria:

- The engine can run a two-symbol static allocation.
- Rebalance orders fill at the next open.
- Equity is valued at close on aligned dates.
- Cash, per-symbol holdings, portfolio value, and allocation drift are recorded.
- Tests cover fills, valuation, costs, and final-bar order behavior.

Delivered implementation:

- `quant_lab.portfolio_backtest` runs static-weight portfolio simulations.
- Rebalance orders are generated from close-price allocation drift and filled at
  the next aligned open.
- Monthly, quarterly, and annual rebalances trigger on the first available
  aligned session in that period.
- Sells execute before buys so rebalance proceeds can fund new allocations.
- The result includes an equity curve, positions, trades, allocation drift,
  final cash, final equity, and total return.
- `tests/test_portfolio_backtest.py` covers next-open fills, no-rebalance
  behavior, final-bar signals, transaction costs, and symbol validation.

### 3. Portfolio Artifacts And Metadata

Status: delivered.

Persist portfolio outputs beside normal run artifacts.

Suggested artifacts:

```text
portfolio_metadata.json
portfolio_metrics.json
portfolio_equity_curve.csv
portfolio_positions.csv
portfolio_trades.csv
portfolio_report.md
portfolio_allocation_drift.csv
```

Acceptance criteria:

- Metadata records the portfolio spec fingerprint.
- Metadata records every input CSV fingerprint.
- Report includes allocation, rebalance, benchmark, cost, and data-quality
  assumptions.
- Research index rows can distinguish portfolio runs from single-symbol runs.

Delivered implementation:

- `quant_lab.portfolio_artifacts` writes portfolio metrics, equity curve,
  positions, trades, allocation drift, report, and metadata artifacts.
- `portfolio_metadata.json` records the portfolio spec fingerprint when a source
  file exists, every symbol input fingerprint, target weights, row counts,
  dropped rows, data-quality severity, costs, benchmark input, command tokens,
  and git commit.
- `tests/test_portfolio_artifacts.py` covers artifact writing, metadata shape,
  metrics persistence, report content, and in-memory specs without a source
  file.

### 4. Portfolio Benchmark Comparison

Status: delivered.

Compare the portfolio equity curve against an explicit benchmark.

Acceptance criteria:

- The benchmark uses the same aligned date range.
- Metrics make clear whether the portfolio beat the benchmark after costs.
- Missing benchmark data fails explicitly instead of silently skipping
  comparison.

Delivered implementation:

- `quant_lab.portfolio_benchmarks` builds buy-and-hold benchmark curves over the
  same aligned dates used by the portfolio run.
- Missing benchmark rows fail with an explicit error naming the first missing
  aligned date.
- `quant_lab.portfolio_artifacts` can save benchmark metrics, benchmark equity
  curve, benchmark metadata, and a benchmark report section.
- `tests/test_portfolio_benchmarks.py` and `tests/test_portfolio_artifacts.py`
  cover same-date comparison, excess total return, benchmark persistence, and
  missing-date failures.

### 5. Example Workflow And Docs

Status: not started.

Add one copyable example portfolio workflow.

Acceptance criteria:

- README links the portfolio workflow.
- The example shows fetch, portfolio spec, run, inspect, and compare steps.
- The docs explain what this version can and cannot tell the user.

## Build Order

1. Add portfolio spec parsing and validation.
2. Add multi-symbol data loading and date alignment.
3. Add a small static-weight portfolio engine.
4. Add artifacts and metadata persistence.
5. Add CLI wiring.
6. Add benchmark comparison.
7. Add example docs.

The first implementation slice should stop after deliverable 1. That gives the
rest of the milestone a stable foundation and makes the future engine easier to
test.

## Risks To Watch

- **Date alignment:** different symbols can have different missing days. The
  first version should use intersection alignment and report dropped rows.
- **Corporate actions:** cached adjusted data may differ by provider/version.
  Keep per-symbol fingerprints in metadata.
- **Rebalancing assumptions:** monthly means nothing unless the exact rebalance
  date rule is documented. Use first available aligned session of each month.
- **Benchmark fairness:** benchmark metrics must use the same date range as the
  portfolio.
- **False precision:** portfolio backtests can look sophisticated while still
  being simple historical simulations. Reports should keep assumptions visible.

## Exit Criteria

Milestone 8 is done when the lab can run and inspect a simple static-weight
portfolio across multiple symbols, with local metadata that makes every data
input, allocation assumption, rebalance rule, cost model, benchmark comparison,
and output artifact clear.
