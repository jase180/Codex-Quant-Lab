# Milestone 9: Portfolio Usability And Research Loops

## Status

Planned.

## Goal

Make portfolio runs easier to inspect, compare, repeat, and fold into normal
research decisions.

Milestone 8 made simple static-weight portfolio backtests possible. Milestone 9
should make them pleasant to use after the run is saved, without forcing the
user to open every CSV and JSON file manually.

## Current Starting Point

Working portfolio capabilities:

- strict `portfolio_plan.v1` parsing,
- multi-symbol OHLCV loading,
- date-intersection alignment,
- static target weights,
- periodic rebalancing,
- next-aligned-open fills,
- per-symbol positions, trades, and allocation drift,
- benchmark comparison over the same aligned dates,
- local artifacts and `portfolio_metadata.json`,
- `quant-lab portfolio-run`,
- `portfolio_run` rows in the research index.

The main gap is usability after the run exists.

## Non-Goals

- No portfolio optimizer yet.
- No automated asset discovery yet.
- No strategy-per-symbol portfolio engine yet.
- No database requirement.
- No charts unless the CLI/reporting workflow clearly needs them.
- No broad UI work.

This milestone should deepen the local CLI research loop first.

## Deliverables

### 1. Inspect One Portfolio Run

Status: delivered.

Add:

```bash
quant-lab show-portfolio-run \
  --metadata artifacts/research/qqq_spy_static_60_40/baseline/portfolio_metadata.json
```

Acceptance criteria:

- Prints portfolio id, name, run type, date range, initial cash, costs, git
  commit, benchmark return, excess return, and artifact paths.
- Prints each symbol's target weight, aligned rows, dropped rows, data-quality
  severity, and data fingerprint prefix.
- Prints clear missing-file errors when metadata or referenced artifacts are
  absent.
- Tests cover normal output and missing metadata.

Delivered implementation:

- `quant-lab show-portfolio-run --metadata ...`.
- `quant_lab.portfolio_inspection` loads portfolio metadata and metrics,
  formats identity, setup, results, symbols, artifacts, and command.
- `tests/test_portfolio_inspection.py` covers normal output, CLI output,
  missing metadata, and missing metrics.

### 2. Compare Portfolio Runs

Status: delivered.

Add:

```bash
quant-lab compare-portfolio-runs \
  --metadata first/portfolio_metadata.json \
  --metadata second/portfolio_metadata.json
```

Acceptance criteria:

- Requires at least two metadata paths.
- Shows portfolio id, symbols, rebalance frequency, total return, benchmark
  return, excess return, max drawdown, Sharpe ratio, cost preset, and output
  directory.
- Handles missing optional metrics gracefully.
- Tests cover comparison output and validation.

Delivered implementation:

- `quant-lab compare-portfolio-runs --metadata ... --metadata ...`.
- `quant_lab.portfolio_inspection` loads multiple portfolio run summaries and
  formats a compact comparison table.
- Tests cover CLI output and validation that at least two metadata paths are
  required.

### 3. Portfolio Templates

Status: not started.

Add starter portfolio JSON generation:

```bash
quant-lab list-portfolio-templates

quant-lab new-portfolio \
  --template qqq-spy-60-40 \
  --out data/portfolios/qqq_spy_static_60_40.json
```

Acceptance criteria:

- Provides at least one starter template that matches the existing example.
- Refuses to overwrite unless `--force` is provided.
- Validates generated JSON with the strict portfolio parser before writing.
- README links the portfolio template workflow.

### 4. Guided Portfolio Research Plan

Status: not started.

Extend the guided research idea to portfolios only after inspection and
comparison are in place.

Possible command:

```bash
quant-lab portfolio-plan init \
  --title "QQQ SPY 60/40 allocation check" \
  --hypothesis "A 60/40 QQQ/SPY allocation may improve return versus SPY buy-and-hold." \
  --portfolio data/portfolios/qqq_spy_static_60_40.json \
  --out artifacts/research/qqq_spy_static_60_40
```

Acceptance criteria:

- Creates a durable local plan around one portfolio hypothesis.
- Prints the recommended `portfolio-run` command.
- Recommends inspect, compare, or decision steps based on local artifacts.

This is intentionally last. It needs good inspection output to be worth adding.

## Build Order

1. `show-portfolio-run`.
2. `compare-portfolio-runs`.
3. Portfolio templates.
4. Guided portfolio plans.
5. README and workflow updates after each command becomes real.

## Design Notes

- Reuse `portfolio_metadata.py` instead of reparsing raw JSON ad hoc in every
  command.
- Keep output compact enough to scan in a terminal.
- Keep portfolio run index rows compatible with existing `list-runs`.
- Prefer explicit artifact paths over clever discovery.
- Keep portfolio concepts separate from single-symbol strategy schema until a
  future milestone has a clear reason to combine them.

## Exit Criteria

Milestone 9 is done when a user can create, run, inspect, compare, and reuse a
simple portfolio idea from the CLI without needing to manually inspect every
artifact file.
