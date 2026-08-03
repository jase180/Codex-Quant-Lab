# Milestone 15 State Review

## Decision

Do not add session manifests inside Milestone 15. Promote them to Milestone 16.

Session manifests are useful, but adding them now would risk creating another
human-facing report that competes with `experiment_conclusion.md`. The right
shape is clearer after the SPY walkthrough: the conclusion should stay the main
source of truth, while a manifest should be an index of the plan, commands,
artifacts, decision, and next step.

## Current State

Milestone 15 is substantially delivered:

- The README now leads with one default workflow.
- The lab can write `experiment_conclusion.md` and
  `experiment_conclusion.json`.
- The conclusion command writes `agent_context.md` for a local agent or future
  Codex session.
- Guided strategy research plans recommend a conclusion before decision steps.
- Human-facing reports are labeled as main, supporting, or raw/audit.
- The core backtest assumptions are documented in
  `core-backtest-assumption-audit.md`.
- A complete SPY long/cash trend experiment was run and documented in
  `spy-long-cash-trend-experiment.md`.

The project is usable as a small local research lab for simple daily long/cash
strategy questions. It is no longer just a proof of concept, because the CLI can
produce a baseline, trust checks, sweeps, evidence summaries, decisions, and a
canonical conclusion. It is still not a mature quant platform: the strategy
language is limited, artifacts are local-only, and the research workflow still
requires a careful operator.

## What Still Feels Awkward

- A single experiment can still produce many files, and a beginner may not know
  which ones are current unless they read the conclusion first.
- Some supporting reports can become stale if they are generated before the
  final decision or conclusion.
- The research plan knows the next command, but it does not yet preserve a full
  session-level history of what was actually run.
- Ignored local artifacts are correct for Git hygiene, but tracked docs need to
  preserve the lesson from important experiments.
- Portfolio workflows do not yet share the same conclusion-first default path as
  strategy workflows.

## Session Manifest Judgment

Session manifests should become Milestone 16 because they solve a different
problem than Milestone 15:

- Milestone 15 answers: "What did this experiment teach us?"
- Milestone 16 should answer: "Where is everything, what happened, and how do I
  resume or replay the plan?"

The manifest should be machine-readable, lightweight, and subordinate to the
conclusion. It should point to `experiment_conclusion.md` and
`experiment_conclusion.json`, not summarize the experiment independently.

## Close Criteria

Milestone 15 can be treated as closed once the docs say clearly that:

- `experiment_conclusion.md` is the first human-facing artifact to read.
- `experiment_conclusion.json` is the first local-agent artifact to read.
- session manifests are the next milestone, not unfinished Milestone 15 work.
- the SPY walkthrough is the example that proves the default workflow can run
  end to end.
