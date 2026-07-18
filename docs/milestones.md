# Codex-Quant-Lab Milestones

This document tracks the practical build plan for the lab. It is intentionally
plain: each milestone should leave the project more useful for actual research,
not just more complex.

## Current Status

The project has completed its first foundation phase: a reproducible local
research loop.

Working capabilities:

- Fetch and cache daily OHLCV data.
- Validate strict v1 JSON strategies.
- Run SMA, EMA, and RSI rule-based strategies.
- Backtest with next-bar-open fills.
- Run parameter sweeps.
- Compare against explicit benchmarks.
- Model simple commission and slippage assumptions.
- Save metrics, reports, trades, equity curves, charts, and metadata.
- Save research notes with run and sweep artifacts.
- Append every run to a local JSONL research index.
- List previous runs with `quant-lab list-runs`.
- Inspect one saved run with `quant-lab show-run`.
- Verify that a saved run still matches its local input CSV with
  `quant-lab verify-run`.
- Compare saved runs with `quant-lab compare-runs`.
- Filter and export the run index with `list-runs` options.
- Track experiments, summarize linked evidence, draft decisions, and record
  structured research decisions.

## Milestone 1: Reproducible Backtesting Foundation

Status: complete.

Goal: make one backtest deterministic, inspectable, and easy to repeat.

Delivered:

- deterministic daily backtester,
- strict OHLCV validation,
- strict strategy schema,
- CLI `run`,
- report and metrics artifacts,
- trade ledger,
- unit tests around fills, accounting, metrics, and schema validation.

## Milestone 2: Research Artifacts And Registry

Status: complete.

Goal: make experiments easy to audit after the chat is gone.

Delivered:

- buy-and-hold benchmark outputs,
- parameter sweep CLI,
- sweep summaries,
- equity and drawdown PNG charts,
- transaction costs and slippage,
- `run_metadata.json` per run,
- append-only `artifacts/research_index.jsonl`,
- `quant-lab list-runs` for reading the index.

## Milestone 3: Research Usability

Status: complete.

Goal: make it easier to compare and interpret runs without opening many files.

Detailed plan: [milestone-3-research-usability.md](milestone-3-research-usability.md)

Delivered:

- `quant-lab show-run --metadata` prints one run's metadata, metrics, costs,
  benchmark context when available, and artifact paths.
- `quant-lab compare-runs --metadata` compares two or more runs in one table.
- `quant-lab list-runs` supports strategy id filtering, run-type filtering, and
  CSV output.
- [research-workflow.md](research-workflow.md) documents the full research loop.

Exit criteria:

- A user can find a run, inspect it, and compare it to another run from the CLI.

## Milestone 4: Better Validation And Realism

Status: complete.

Goal: reduce false confidence from unrealistic assumptions.

Detailed plan: [milestone-4-validation-realism.md](milestone-4-validation-realism.md)

Delivered:

- Data-quality artifacts for runs and sweeps.
- Cost presets for common broker assumptions.
- Research warnings for weak samples and tiny trade counts.
- Basic train/test sweep workflow.
- Explicit benchmark selection with buy-and-hold default and cash baseline.

Exit criteria:

- A promising result has enough context to decide whether it deserves more research.

## Milestone 5: Strategy Research Depth

Status: complete.

Goal: make the lab better at forming, documenting, and comparing strategy ideas.

Detailed plan: [milestone-5-strategy-research-depth.md](milestone-5-strategy-research-depth.md)

Delivered:

- Built-in starter strategy templates.
- `quant-lab list-strategy-templates`.
- `quant-lab new-strategy`.
- Optional `--note` and `--note-file` artifacts for runs and sweeps.
- Sweep `research.md` top-runs and parameter-stability summaries.
- Explicit walk-forward windows with `walk_forward_summary.csv`.
- Rolling high/low indicators plus a breakout strategy example and template.
- Local experiment records with linked run metadata.
- Evidence summaries, conservative decision drafts, and structured experiment
  decisions.

Exit criteria:

- The lab can create, document, and evaluate several common daily-system ideas
  without code changes.

## Milestone 6: Research Trustworthiness

Status: complete.

Goal: make research conclusions harder to fool yourself with.

Detailed plan: [milestone-6-research-trustworthiness.md](milestone-6-research-trustworthiness.md)

Delivered:

- Dataset fingerprints in run metadata.
- Stronger data provenance in fetch/cache outputs.
- Data-quality severity levels and clearer trust warnings.
- Reproducibility checks that compare a run against the current input file.
- A small honest example workflow with artifacts and decisions.

Exit criteria:

- A user can tell whether a result used the intended data, whether that data
  changed later, and whether the result is too weak to trust yet.

## Milestone 7: Guided Research Workflow

Status: complete.

Goal: turn the existing research primitives into a guided workflow for one
research question.

Detailed plan:
[milestone-7-guided-research-workflow.md](milestone-7-guided-research-workflow.md)

Delivered:

- local `research_plan.json` and `research_plan.md` files,
- `quant-lab research-plan init`,
- baseline command recommendation,
- `quant-lab research-plan next`,
- simple next-step logic based on plan state, experiment records, and run index
  rows,
- docs for guided versus manual research workflows.

Exit criteria:

- A user can start from a hypothesis and get a durable local plan plus the next
  recommended command without hiding the normal run, sweep, validation, summary,
  and decision artifacts.

## Milestone 8: Portfolio And Multi-Asset Research

Status: complete.

Goal: move from single-symbol strategy checks toward portfolio-level research.

Detailed plan:
[milestone-8-portfolio-multi-asset-research.md](milestone-8-portfolio-multi-asset-research.md)

Delivered:

- Multi-symbol data loading.
- Strict portfolio spec parsing and validation.
- Static-weight allocation rules.
- Periodic rebalancing logic.
- Per-symbol holdings, trades, and allocation drift artifacts.
- Portfolio metadata with per-symbol data fingerprints.
- Portfolio benchmark comparisons on the same aligned date range.
- `quant-lab portfolio-run`.
- [portfolio-workflow.md](portfolio-workflow.md).

Exit criteria:

- The lab can run and inspect a simple static-weight portfolio across multiple
  symbols, with local metadata that makes every data input, allocation
  assumption, rebalance rule, cost model, benchmark comparison, and output
  artifact clear.

## Milestone 9: Portfolio Usability And Research Loops

Status: planned.

Goal: make portfolio runs easier to inspect, compare, repeat, and fold into
normal research decisions.

Detailed plan:
[milestone-9-portfolio-usability-research-loops.md](milestone-9-portfolio-usability-research-loops.md)

Planned work:

- `quant-lab show-portfolio-run`.
- `quant-lab compare-portfolio-runs`.
- Portfolio templates.
- Guided portfolio research plans.
- README and workflow updates for the portfolio research loop.

Exit criteria:

- A user can create, run, inspect, compare, and reuse a simple portfolio idea
  from the CLI without needing to manually inspect every artifact file.

## Maintenance: CLI And Workflow Organization

Status: complete.

Detailed note:
[maintenance-cli-workflow-organization.md](maintenance-cli-workflow-organization.md)

Goal: make the codebase easier to extend before starting larger product work.

Delivered:

- command-focused CLI handler modules,
- grouped parser setup in `quant_lab.cli`,
- shared sweep setup and sweep variant execution helpers,
- shared train-sweep selection and selected test-run helpers,
- shared run metadata, experiment linking, and research-index persistence,
- shared backtest execution plus artifact-saving helper.

Exit criteria:

- Future product work can add commands, metadata fields, or sweep workflows
  without copying core artifact plumbing.

## Near-Term Recommendation

Build Milestone 9 deliverable 1: `quant-lab show-portfolio-run`.

Reason: portfolio runs now save rich metadata, but the user still has to open
several files to understand one saved result. A focused inspection command is
the fastest way to make portfolio research feel usable.
