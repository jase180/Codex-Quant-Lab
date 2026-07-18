# Milestone 7: Guided Research Workflow

## Purpose

Turn the existing research primitives into a guided workflow for one research
question.

The lab can already create experiments, run baselines, sweep parameters, run
train/test and walk-forward checks, summarize evidence, draft decisions, and
record final decisions. The problem is that a new user still has to know the
right command sequence and folder conventions.

This milestone should make the lab feel more like a small research assistant:
it should help a user start from a hypothesis, create a consistent workspace,
and produce the next recommended command without hiding the underlying files.

## User Stories

1. As a learner, I can start a research question without remembering every CLI
   command.
2. As a researcher, I can create a consistent experiment folder layout for
   baseline, sweep, validation, and decisions.
3. As a researcher, I can see the next recommended command for the current
   experiment state.
4. As a researcher, I can keep the workflow transparent: every generated command
   should still be copyable and every artifact should remain local.
5. As a future Codex agent, I can inspect one workflow state file and understand
   what has been done and what should happen next.

## Non-Goals

Do not build these in this milestone:

- a GUI,
- live trading,
- automatic market recommendations,
- automatic strategy discovery,
- hidden execution that runs many expensive commands without user intent,
- portfolio or multi-asset backtesting.

The workflow can suggest commands and optionally run carefully scoped steps, but
it should not pretend to know whether an idea is good.

## Proposed CLI Shape

First command group:

```bash
quant-lab research-plan init \
  --title "QQQ SMA crossover trust check" \
  --hypothesis "A daily SMA crossover may reduce drawdown versus buy-and-hold." \
  --strategy data/strategies/qqq_sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --symbol QQQ \
  --tag sma \
  --out artifacts/research/qqq_sma_trust
```

Expected first version behavior:

- create a workflow directory,
- write `research_plan.json`,
- write `research_plan.md`,
- create or reference an experiment id,
- print the recommended baseline `quant-lab run` command.

Follow-up command:

```bash
quant-lab research-plan next \
  --plan artifacts/research/qqq_sma_trust/research_plan.json
```

Expected first version behavior:

- inspect the plan file,
- inspect linked experiment evidence when available,
- print the next recommended command,
- explain the reason in plain text.

## State Model

The workflow state should be a local JSON file. Keep it boring and explicit.

Proposed `research_plan.json` fields:

```json
{
  "schema_version": "research_plan.v1",
  "title": "QQQ SMA crossover trust check",
  "hypothesis": "A daily SMA crossover may reduce drawdown versus buy-and-hold.",
  "strategy_path": "data/strategies/qqq_sma_crossover.json",
  "data_path": "data/cache/QQQ_2015-01-01_2025-12-31.csv",
  "symbol": "QQQ",
  "experiment_id": "EXP-001",
  "experiments_path": "artifacts/experiments.jsonl",
  "index_path": "artifacts/research_index.jsonl",
  "output_dir": "artifacts/research/qqq_sma_trust",
  "recommended_steps": [
    "baseline",
    "sweep",
    "train_test",
    "walk_forward",
    "summarize",
    "decide"
  ],
  "created_at_utc": "2026-07-17T00:00:00Z"
}
```

The plan should store paths and intent, not computed results. Results belong in
run metadata, research index rows, experiment records, and summary artifacts.

## Deliverable 1: Research Plan Files

Status: delivered.

Goal: create a durable local plan file for one research question.

Acceptance criteria:

- `research-plan init` writes `research_plan.json`.
- `research-plan init` writes a readable `research_plan.md`.
- The JSON includes hypothesis, strategy path, data path, output directory,
  experiment id, experiment registry path, and research index path.
- Tests cover required fields and stable serialization.

## Deliverable 2: Baseline Command Recommendation

Status: delivered.

Goal: make the first action obvious after creating a plan.

Acceptance criteria:

- `research-plan init` prints a copyable `quant-lab run` command.
- The command includes strategy, data, output path, experiment id, index path,
  experiments path, benchmark, sizing, and cost assumptions.
- The command writes baseline artifacts under the plan output directory.
- README or workflow docs show the command.

## Deliverable 3: Next-Step Recommendation

Status: planned.

Goal: inspect a plan and tell the user what to do next.

First version logic can stay simple:

- no linked baseline run: recommend baseline,
- baseline exists but no sweep run: recommend sweep,
- sweep exists but no validation run: recommend train/test,
- validation exists but no evidence summary: recommend summarize,
- summary exists but no decision: recommend draft/decide.

Acceptance criteria:

- `research-plan next --plan ...` prints a recommended command and reason.
- Tests cover at least empty plan, baseline-only, and sweep-present states.
- The logic uses existing run index and experiment records where possible.

## Deliverable 4: Documentation

Status: in progress.

Goal: make the guided workflow easy to learn.

Acceptance criteria:

- README lists the guided workflow command.
- `docs/research-workflow.md` explains when to use the guided workflow versus
  manual commands.
- The docs keep the skeptical framing: the workflow organizes research; it does
  not prove a trading edge.

## Suggested Build Order

1. Add `research_plan.py` with the state dataclass and serialization helpers.
2. Add `cli_research_plan.py` with `init` command handling.
3. Wire `research-plan init` into the parser.
4. Add tests for plan creation and printed baseline command.
5. Add `research-plan next`.
6. Update README and workflow docs.

Reasoning:

- The state file is the contract, so make it solid first.
- `init` is useful by itself because it creates a durable plan and first
  command.
- `next` becomes safer once there is a real plan format to inspect.
