# Milestone 10: Portfolio Research Depth

## Status

Planned.

## Goal

Make portfolio research deeper without turning the lab into a black-box
optimizer.

Milestone 8 made simple static-weight portfolio backtests possible. Milestone 9
made those runs easier to create, inspect, compare, and guide. Milestone 10
should help a user explore portfolio variants deliberately: different weights,
different rebalance frequencies, compact portfolio evidence summaries, and
small candidate sets that remain easy to audit.

## Current Starting Point

Working portfolio capabilities:

- strict `portfolio_plan.v1` parsing,
- starter portfolio templates,
- static target weights,
- rebalance frequencies of `none`, `monthly`, `quarterly`, and `annually`,
- portfolio run artifacts and metadata,
- portfolio run inspection,
- portfolio run comparison,
- guided portfolio plans,
- research index rows for portfolio runs.

The main gap is repeatable portfolio variant research. Today, a user can compare
runs, but creating the variants and summarizing a whole experiment still takes
manual JSON edits and manual interpretation.

## Non-Goals

- No live trading.
- No broker integration.
- No claim of optimal allocation.
- No complex mean-variance optimizer yet.
- No database requirement.
- No broad UI work.
- No strategy-per-symbol portfolio engine.

The milestone should stay CLI-first and artifact-first.

## Deliverables

### 1. Portfolio Variant Generation

Add a command that creates multiple valid portfolio specs from one base
portfolio spec.

Possible command:

```bash
quant-lab portfolio-variants \
  --portfolio data/portfolios/qqq_spy_static_60_40.json \
  --weights QQQ=0.50,SPY=0.50 \
  --weights QQQ=0.60,SPY=0.40 \
  --weights QQQ=0.70,SPY=0.30 \
  --out data/portfolios/variants/qqq_spy
```

Acceptance criteria:

- Writes one valid `portfolio_plan.v1` JSON file per requested weight set.
- Refuses invalid or incomplete weight sets.
- Refuses weights that do not sum to `1.0`.
- Refuses to overwrite unless `--force` is provided.
- Keeps data paths, benchmark, and default rebalance rule from the base spec.
- Tests cover valid generation, invalid weights, and overwrite protection.

### 2. Rebalance Frequency Variants

Extend variant generation to create specs across rebalance frequencies.

Possible command:

```bash
quant-lab portfolio-variants \
  --portfolio data/portfolios/qqq_spy_static_60_40.json \
  --weights QQQ=0.60,SPY=0.40 \
  --rebalance none \
  --rebalance monthly \
  --rebalance quarterly \
  --out data/portfolios/variants/qqq_spy_rebalance
```

Acceptance criteria:

- Supports `none`, `monthly`, `quarterly`, and `annually`.
- Produces stable filenames that include weights and rebalance frequency.
- Validates every generated spec with the strict parser.
- Documents how to run the generated variants.

### 3. Portfolio Experiment Summary

Add a portfolio-specific evidence summary for one experiment.

Possible command:

```bash
quant-lab summarize-portfolio-experiment \
  --experiment-id EXP-001 \
  --experiments-path artifacts/experiments.jsonl \
  --index-path artifacts/research_index.jsonl \
  --out artifacts/research/qqq_spy_static_60_40/portfolio_summary.md
```

Acceptance criteria:

- Reads linked `portfolio_run` rows from the research index.
- Shows top runs by total return, excess return, Sharpe ratio, and max drawdown.
- Calls out benchmark underperformance and large drawdown in plain language.
- Includes enough metadata paths for a user to inspect source runs.
- Does not hide weak evidence behind a single score.
- Tests cover summary output with multiple linked portfolio runs.

### 4. Guided Plan Integration

Teach `portfolio-plan next` to recommend variant generation and portfolio
summaries when useful.

Acceptance criteria:

- If only one portfolio run exists, recommend inspect.
- If multiple portfolio runs exist but no summary artifact is known, recommend
  `summarize-portfolio-experiment`.
- If no variants exist and the base plan is still early, suggest
  `portfolio-variants`.
- Keep recommendations conservative and copyable.
- Tests cover the new next-step branches.

### 5. Small Candidate Generator

Add a deliberately simple candidate generator only after manual variants and
summary output are working.

Possible command:

```bash
quant-lab portfolio-candidates \
  --symbols QQQ,SPY,TLT \
  --step 0.25 \
  --data-dir data/cache \
  --out data/portfolios/candidates/qqq_spy_tlt
```

Acceptance criteria:

- Generates valid static-weight candidate specs on a coarse grid.
- Requires explicit symbols and a coarse step size.
- Caps candidate count unless `--max-candidates` is increased.
- Prints the number of generated specs and any skipped combinations.
- Validates generated specs before writing.
- Does not run backtests automatically.

## Build Order

1. Portfolio weight variants.
2. Rebalance-frequency variants.
3. Portfolio experiment summary.
4. Guided plan integration.
5. Small candidate generator.
6. README and workflow updates after each command becomes real.

## Design Notes

- Keep variant generation separate from backtesting. Creating candidate specs
  should not automatically run them.
- Prefer auditable JSON files over hidden in-memory candidate state.
- Reuse the strict portfolio parser for every generated spec.
- Reuse research index rows for summaries instead of inventing a new registry.
- Avoid a single magic ranking score. Show several metrics and let the user
  make a skeptical decision.
- Keep filenames stable and readable enough that a directory listing is useful.
- Avoid optimizer language until the implementation truly deserves it.

## Exit Criteria

Milestone 10 is done when a user can generate a small set of portfolio variants,
run them, summarize their evidence, and let the guided portfolio plan recommend
the next research step without manually editing every candidate spec.
