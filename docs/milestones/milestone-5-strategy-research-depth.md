# Milestone 5: Strategy Research Depth

## Purpose

Make the lab better at forming, documenting, and comparing strategy ideas after
Milestone 4 made the backtests more skeptical.

The priority is still a small daily single-symbol research lab. This milestone
should improve the research loop without adding live trading, broker behavior,
or a large optimization framework.

## Current Starting Point

Already available:

- strict v1 JSON strategy schema,
- example SMA, EMA, and RSI strategy files,
- run and sweep CLI workflows,
- train/test sweep mode,
- data-quality artifacts,
- cost presets,
- research warnings,
- explicit benchmark selection,
- run metadata and a research index.

Main gaps:

- Creating a new valid strategy JSON still requires hand-editing examples.
- The research question or hypothesis is not saved with run artifacts.
- Sweep summaries rank rows, but do not yet explain parameter stability.
- There is only one train/test split, not repeated walk-forward checks.
- Strategy primitives are limited to SMA, EMA, RSI, and simple comparisons.

## User Stories

1. As a learner, I can create a valid starter strategy from a named template.
2. As a researcher, I can save my hypothesis or notes beside the run artifacts.
3. As a researcher, I can see whether top sweep results are stable or isolated.
4. As a researcher, I can run a simple repeated train/test workflow.
5. As a builder, I can add strategy primitives without weakening schema checks.

## Non-Goals

Do not build these in this milestone:

- live trading,
- broker integration,
- intraday execution,
- portfolio optimization,
- machine learning model search,
- a web dashboard,
- a broad plugin system.

## Deliverable 1: Strategy Templates And Research Notes

Status: delivered.

Goal: make it easy to start a valid strategy idea and preserve the research
intent beside the artifacts.

Proposed CLI:

```bash
quant-lab new-strategy \
  --template sma-crossover \
  --symbol QQQ \
  --out data/strategies/qqq_sma_crossover.json
```

```bash
quant-lab run \
  --strategy data/strategies/qqq_sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --note "Hypothesis: trend following may reduce drawdown versus buy-and-hold." \
  --out artifacts/research/qqq_sma_note_001
```

Implementation notes:

- Start with templates that match current schema support. Delivered.
- Validate generated strategy JSON before writing it. Delivered.
- Do not overwrite an existing strategy unless `--force` is provided. Delivered.
- Save notes as `research_note.md`. Delivered.
- Add the note artifact path to `run_metadata.json` when present. Delivered.

Acceptance criteria:

- CLI can list available templates. Delivered.
- CLI can generate a valid strategy JSON from a template. Delivered.
- CLI refuses to overwrite an existing strategy without `--force`. Delivered.
- Runs and sweeps can save a research note artifact. Delivered.
- Tests cover template generation and note persistence. Delivered.

## Deliverable 2: Sweep Stability Summary

Status: delivered.

Goal: help distinguish robust parameter regions from isolated winners.

First version:

- include top N rows in `research.md`. Delivered.
- show whether the best run's nearby parameter values were also strong. Delivered.
- flag when the winner is isolated relative to the sweep grid. Delivered.

Delivered heuristic:

- Treat rows that differ from the best run by exactly one parameter as
  one-parameter neighbors.
- Mark a neighbor as strong when its total return is within 5 percentage points
  of the best run, or within 25% of the best return magnitude, whichever is
  wider.
- Report `supported`, `mixed`, `isolated`, or `grid_too_sparse`.

Acceptance criteria:

- Sweep `research.md` includes top-run context. Delivered.
- Tests cover stable and isolated grids. Delivered.
- Docs explain that this is a heuristic, not statistical proof. Delivered.

## Deliverable 3: Walk-Forward Lite

Status: delivered.

Goal: repeat the train/test idea across multiple ordered windows.

First version:

- accept explicit split windows. Delivered.
- run the same parameter grid across each window. Delivered.
- summarize selected train winner and test result per window. Delivered.

Delivered CLI:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --walk-forward-window 2015-01-01,2018-12-31,2019-01-01,2020-12-31 \
  --walk-forward-window 2017-01-01,2020-12-31,2021-01-01,2022-12-31 \
  --out artifacts/research/sma_walk_forward_001
```

Delivered output:

```text
walk_forward_summary.csv
research.md
window_001/
  train_sweep/
  test_selected/
  test_summary/
```

Acceptance criteria:

- Workflow writes one summary row per test window. Delivered.
- Metadata records window dates. Delivered.
- Docs explain how to avoid moving windows after seeing results. Delivered.

## Deliverable 4: Additional Strategy Primitives

Status: delivered.

Goal: expand strategy ideas while preserving strict validation.

Candidate primitives:

- ATR,
- highest high. Delivered as `rolling_high`.
- lowest low. Delivered as `rolling_low`.
- simple breakout conditions. Delivered through the `breakout_trend` example and template.
- optional volatility filter.

Acceptance criteria:

- Schema validation stays explicit. Delivered.
- Rule engine tests cover each primitive. Delivered.
- Example strategies and templates are updated. Delivered.

## Suggested Build Order

1. strategy templates and research notes,
2. sweep stability summary,
3. walk-forward lite,
4. additional strategy primitives.

Reasoning:

- Templates and notes improve daily usability with low execution risk.
- Stability summaries improve interpretation before adding more search power.
- Walk-forward is more invasive and should come after summaries are stronger.
- More indicators are useful, but they should not arrive before the research
  workflow can document and evaluate them cleanly.
