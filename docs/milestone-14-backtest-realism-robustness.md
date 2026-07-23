# Milestone 14: Backtest Realism And Robustness

## Status

Completed.

## Goal

Make promising strategy and portfolio results harder to overtrust by rerunning
them under controlled, realistic perturbations.

Milestone 13 improved interpretation after evidence exists. Milestone 14 should
challenge that evidence before the lab nudges a user toward stronger confidence.
The practical question is:

```text
Does this idea still look decent if costs, dates, benchmarks, or nearby
parameters change?
```

The goal is not to prove robustness statistically. The goal is to create local,
repeatable stress checks that make fragility visible.

## Current Starting Point

Working capabilities:

- Daily strategy backtests with next-bar-open fills.
- Explicit commission and slippage assumptions.
- Named cost presets.
- Buy-and-hold and cash benchmarks for strategy runs.
- Train/test and walk-forward sweep workflows.
- Portfolio runs with static weights, rebalancing, costs, and explicit
  benchmarks.
- Data trust reports, evidence labels, and conservative decision drafts.

Main gaps:

- A promising result is still tied to one cost assumption unless the user reruns
  variants manually.
- Date-range sensitivity is a manual workflow.
- Benchmark substitution checks are not first-class.
- Parameter neighborhood information exists in sweep summaries, but there is no
  focused robustness artifact that summarizes whether nearby parameters also
  worked.
- Portfolio summaries call out skeptical notes, but there is no structured
  robustness pass for allocation ideas.

## Non-Goals

- No live trading or broker integration.
- No intraday simulation.
- No order book, liquidity, market impact, or partial-fill model.
- No optimizer that automatically picks a final strategy or allocation.
- No statistical proof claims.
- No new strategy schema version in this milestone.
- No project-wide session manifest work; that moves to a later milestone.

## Deliverables

### 1. Strategy Cost Sensitivity

Status: delivered for strategy cost-preset sensitivity.

Add a repeatable way to rerun one strategy setup across cost assumptions.

Proposed CLI:

```bash
quant-lab robustness cost-sensitivity \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --benchmark buy-and-hold \
  --cost-preset none \
  --cost-preset retail-liquid \
  --cost-preset retail-conservative \
  --cost-preset high-friction \
  --out artifacts/research/qqq_sma/robustness/costs
```

Acceptance criteria:

- Runs the same strategy/data/sizing setup once per requested cost preset.
- Writes normal run artifacts for each child run.
- Writes `cost_sensitivity_summary.csv`.
- Writes `cost_sensitivity_report.md`.
- The report calls out whether the result survives stricter costs.
- Tests cover command planning, execution, summary rows, and report warnings.

Delivered behavior:

- `quant-lab robustness cost-sensitivity` reruns one strategy setup once per
  repeated `--cost-preset`.
- Each child run writes normal run artifacts and appends a
  `cost_sensitivity_run` row to the research index.
- The command writes `cost_sensitivity_summary.csv` and
  `cost_sensitivity_report.md`.
- `list-runs --run-type cost_sensitivity_run` can filter the generated child
  runs.

### 2. Strategy Date-Range Sensitivity

Status: delivered for explicit strategy date windows.

Add explicit date-window checks for one strategy.

Proposed CLI:

```bash
quant-lab robustness date-sensitivity \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --window 2015-01-01,2018-12-31 \
  --window 2019-01-01,2021-12-31 \
  --window 2022-01-01,2025-12-31 \
  --benchmark buy-and-hold \
  --cost-preset retail-liquid \
  --out artifacts/research/qqq_sma/robustness/dates
```

Acceptance criteria:

- Requires explicit non-empty date windows.
- Rejects invalid date ranges before running.
- Runs each window with the same strategy, sizing, benchmark, and costs.
- Writes `date_sensitivity_summary.csv`.
- Writes `date_sensitivity_report.md`.
- The report highlights windows that underperform the benchmark.

Delivered behavior:

- `quant-lab robustness date-sensitivity` reruns one strategy setup once per
  repeated `--window start,end`.
- Each child run writes normal run artifacts and appends a
  `date_sensitivity_run` row to the research index.
- Each child run metadata file records the requested `window_start` and
  `window_end` parameters.
- The command writes `date_sensitivity_summary.csv` and
  `date_sensitivity_report.md`.
- The command rejects invalid, empty, and one-row windows before treating the
  check as successful.
- `list-runs --run-type date_sensitivity_run` can filter the generated child
  runs.

### 3. Benchmark Substitution Checks

Status: delivered for strategy benchmark substitution.

Make benchmark substitution an intentional robustness check instead of a manual
rerun habit.

Proposed CLI:

```bash
quant-lab robustness benchmark-sensitivity \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --benchmark buy-and-hold \
  --benchmark cash \
  --cost-preset retail-liquid \
  --out artifacts/research/qqq_sma/robustness/benchmarks
```

Acceptance criteria:

- Runs the same strategy setup once per benchmark.
- Writes `benchmark_sensitivity_summary.csv`.
- Writes `benchmark_sensitivity_report.md`.
- The report makes clear when a result only looks good against cash but not
  buy-and-hold.

Delivered behavior:

- `quant-lab robustness benchmark-sensitivity` reruns one strategy setup once
  per repeated `--benchmark`.
- Each child run writes normal run artifacts and appends a
  `benchmark_sensitivity_run` row to the research index.
- Each child run metadata file records the requested benchmark parameter.
- The command writes `benchmark_sensitivity_summary.csv` and
  `benchmark_sensitivity_report.md`.
- The report treats beating cash as weaker evidence than beating buy-and-hold.
- `list-runs --run-type benchmark_sensitivity_run` can filter the generated
  child runs.

### 4. Parameter Neighborhood Robustness

Status: delivered for sweep summary neighborhood reports.

Upgrade sweep interpretation so a single winning parameter set is not treated
as robust by itself.

Acceptance criteria:

- Adds a focused neighborhood summary for sweep results.
- For numeric parameters, reports whether nearby values also beat the benchmark.
- Calls out isolated winners.
- Integrates with existing sweep guardrail reports instead of replacing them.
- Tests cover stable neighborhoods, isolated winners, and missing/non-numeric
  parameter values.

Delivered behavior:

- `quant-lab robustness parameter-neighborhood` reads an existing sweep
  `summary.csv`.
- The command writes `parameter_neighborhood_summary.csv` and
  `parameter_neighborhood_report.md`.
- The report treats the top total-return row as the best row and checks each
  numeric parameter's one-parameter neighbors.
- Neighbor support is based on benchmark excess return, not only closeness to
  the best total return.
- Non-numeric parameters are listed as skipped, and rows with missing parameter
  keys are counted as incompatible.
- The existing `summarize-sweep-guardrails` command remains available as the
  broader sweep warning report.

### 5. Portfolio Robustness Notes

Status: delivered for portfolio summary and batch guidance.

Apply the same robustness language to portfolio allocation research without
building a full optimizer.

Acceptance criteria:

- Portfolio evidence summaries can mention cost sensitivity and benchmark
  sensitivity artifacts when they exist.
- Portfolio batch summaries call out whether winners survive stricter costs when
  those runs are linked.
- Docs explain how to run simple allocation robustness checks with existing
  portfolio commands before any new portfolio-specific automation is added.

Delivered behavior:

- Portfolio experiment summaries now list represented cost presets and
  benchmark names for linked `portfolio_run` rows.
- Portfolio experiment summaries explicitly call out when linked evidence does
  not show portfolio cost sensitivity or benchmark substitution.
- Portfolio batch summaries now include robustness notes explaining that a
  batch compares allocation candidates, not full cost/benchmark robustness by
  itself.
- Portfolio workflow docs explain how to create simple robustness evidence
  today by rerunning comparable portfolio candidates under stricter costs or
  alternate benchmark specs.

### 6. Guided Workflow Integration

Status: delivered for strategy and portfolio guided plans.

Teach guided plans when to suggest robustness checks.

Acceptance criteria:

- `research-plan next` recommends robustness checks after a promising or mixed
  evidence summary and before final acceptance.
- `portfolio-plan next` recommends robustness review before compare/decision
  when portfolio evidence exists.
- Recommendations remain conservative and do not automatically promote results.

Delivered behavior:

- `research-plan next` now inserts strategy robustness recommendations after
  evidence summary and before decision drafting.
- Strategy guided plans recommend cost sensitivity, date sensitivity, benchmark
  sensitivity, and parameter-neighborhood reporting when the relevant evidence
  is missing.
- `portfolio-plan next` now pauses after portfolio summaries when linked runs do
  not show both cost-preset diversity and benchmark diversity.
- Portfolio guided plans print a stricter-cost `portfolio-run` command when cost
  robustness is missing, while leaving benchmark substitution as an explicit
  portfolio-spec review step.
- Guided recommendations remain conservative and never convert robustness into
  an automatic accept/reject decision.

## Build Order

1. Strategy cost sensitivity.
2. Strategy date-range sensitivity.
3. Benchmark substitution checks.
4. Parameter neighborhood robustness.
5. Portfolio robustness notes.
6. Guided workflow and docs integration.

## Design Notes

- Reuse existing run execution and artifact persistence instead of adding a
  second backtest path.
- Every robustness child run should still be a normal indexed run where
  practical.
- Reports should emphasize failure modes, not just best rows.
- Keep inputs explicit. Hidden generated windows or cost assumptions make the
  result harder for a beginner to audit.
- Prefer small CSV and Markdown artifacts over complex nested schemas.
- Keep labels humble: `robustness` means "survived these checks," not "will work
  in the future."

## Exit Criteria

Milestone 14 is done when a user can take a promising strategy or portfolio
idea, run a small set of cost/date/benchmark/parameter checks, and read a local
report that clearly says where the idea survived, where it failed, and what
should be tested next.

## Closeout

Milestone 14 is complete. Strategy robustness now has first-class commands for
cost presets, explicit date windows, benchmark substitution, and sweep
parameter neighborhoods. Portfolio workflows now surface whether linked runs
show cost and benchmark robustness evidence. Guided strategy and portfolio
plans recommend these checks before decision steps, while keeping the language
skeptical and local to the tested artifacts.

Remaining caveat: portfolio robustness is still mostly a guided workflow over
existing `portfolio-run` and portfolio-spec variants, not a single automated
portfolio robustness runner. That is intentional for this milestone; a later
portfolio-realism milestone can add deeper automation if the data model proves
stable.
