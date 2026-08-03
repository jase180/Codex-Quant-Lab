# Milestone 11: Research Automation And Guardrails

## Status

Complete.

## Goal

Make repeated research runs easier without making it easier to fool ourselves.

Milestone 10 added portfolio variants, candidate generation, portfolio evidence
summaries, and guided next-step recommendations. Milestone 11 should automate
the boring parts of running batches while keeping the workflow skeptical:
explicit inputs, capped batch sizes, dry runs, saved manifests, warning summaries,
and no hidden optimization.

## Current Starting Point

Working capabilities:

- single-strategy runs and sweeps,
- portfolio runs,
- portfolio variant and candidate spec generation,
- local experiment registry,
- research index rows,
- run inspection and comparison,
- portfolio evidence summaries,
- guided strategy and portfolio research plans.

The main gap is execution automation. The lab can generate many candidate specs,
but a user still has to run each candidate one at a time and then manually check
whether the batch was too broad, too weak, or too easy to overfit.

## Non-Goals

- No live trading.
- No broker integration.
- No automatic “best portfolio” promotion.
- No hidden optimizer.
- No multiprocessing until simple sequential execution is proven.
- No database requirement.
- No cloud queue or service.
- No broad UI work.

This milestone should stay local, explicit, and auditable.

## Deliverables

### 1. Portfolio Batch Run Manifest

Status: delivered.

Add a dry-run command that turns a directory of portfolio specs into a durable
batch manifest.

Possible command:

```bash
quant-lab portfolio-batch plan \
  --portfolios data/portfolios/candidates/qqq_spy_tlt \
  --out artifacts/research/qqq_spy_tlt/batch_001
```

Acceptance criteria:

- Finds portfolio JSON specs in a directory.
- Validates each spec with the strict parser.
- Writes `portfolio_batch_manifest.json`.
- Includes each planned spec path, output path, command tokens, and status.
- Refuses an empty candidate directory.
- Does not run backtests.
- Tests cover manifest creation and invalid/empty directories.

### 2. Sequential Portfolio Batch Runner

Status: delivered.

Execute a saved manifest one portfolio run at a time.

Possible command:

```bash
quant-lab portfolio-batch run \
  --manifest artifacts/research/qqq_spy_tlt/batch_001/portfolio_batch_manifest.json \
  --experiment-id EXP-001
```

Acceptance criteria:

- Runs each manifest item through the existing portfolio-run path.
- Writes each run into its planned output directory.
- Appends normal `portfolio_run` rows to the research index.
- Records per-item success or failure in a manifest result file.
- Stops on first failure by default, with an explicit `--continue-on-error`.
- Tests cover success, failure recording, and no duplicate hidden behavior.

### 3. Batch Guardrail Summary

Status: delivered.

Add a summary that explains batch breadth and evidence quality before a user
tries to pick winners.

Possible command:

```bash
quant-lab portfolio-batch summarize \
  --manifest artifacts/research/qqq_spy_tlt/batch_001/portfolio_batch_manifest.json
```

Acceptance criteria:

- Reports number of planned, completed, failed, and skipped runs.
- Reports candidate count versus configured cap.
- Flags very large batches as overfitting risk.
- Flags too few completed runs as weak evidence.
- Links to portfolio experiment summary if available.
- Writes Markdown and prints a concise terminal summary.

### 4. Guided Plan Integration For Batches

Status: delivered.

Teach `portfolio-plan next` to recommend batch planning, batch running, and
batch summaries when candidate specs exist.

Acceptance criteria:

- If candidate specs exist but no manifest exists, recommend `portfolio-batch plan`.
- If a manifest exists with pending items, recommend `portfolio-batch run`.
- If a manifest has completed items but no batch summary exists, recommend
  `portfolio-batch summarize`.
- Keep commands copyable and conservative.
- Tests cover each new branch.

### 5. Strategy Sweep Guardrails

Status: delivered.

Add a lightweight guardrail report for existing strategy sweeps.

Possible command:

```bash
quant-lab summarize-sweep-guardrails \
  --summary artifacts/research/qqq_sma/sweep_001/sweep_summary.csv
```

Acceptance criteria:

- Reads existing sweep outputs.
- Flags large parameter grids, tiny trade counts, fragile winners, and benchmark
  underperformance.
- Does not change sweep execution.
- Produces a concise Markdown warning report.

## Build Order

1. Portfolio batch manifest.
2. Sequential portfolio batch runner.
3. Batch guardrail summary.
4. Guided plan integration for batches.
5. Strategy sweep guardrails.
6. README and workflow updates after each command becomes real.

## Design Notes

- Prefer manifests over implicit directory scans at execution time.
- Keep batch execution sequential and boring first.
- Reuse existing `portfolio-run` behavior instead of making a second backtest
  path.
- Save enough command tokens to reproduce every item.
- Make dry-run planning the first step so a user can inspect what will happen.
- Use caps and warnings as friction against accidental overfitting.
- Do not rank candidates with a single magic score.

## Exit Criteria

Milestone 11 is done. A user can plan, run, and summarize a small batch of
portfolio candidates locally, with enough guardrails to see when the batch is too
broad or the evidence is too weak to trust. A user can also write a lightweight
guardrail report for existing strategy sweep summaries.
