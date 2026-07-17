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
- Compare saved runs with `quant-lab compare-runs`.
- Filter and export the run index with `list-runs` options.

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

Status: planned.

Goal: make research conclusions harder to fool yourself with.

Detailed plan: [milestone-6-research-trustworthiness.md](milestone-6-research-trustworthiness.md)

Likely work:

- Dataset fingerprints in run metadata.
- Stronger data provenance in fetch/cache outputs.
- Data-quality severity levels and clearer trust warnings.
- Reproducibility checks that compare a run against the current input file.
- A small honest example workflow with artifacts and decisions.

Exit criteria:

- A user can tell whether a result used the intended data, whether that data
  changed later, and whether the result is too weak to trust yet.

## Milestone 7: Portfolio And Multi-Asset Research

Status: later.

Goal: move from single-symbol strategy checks toward portfolio-level research.

Likely work:

- Multi-symbol data loading.
- Portfolio allocation rules.
- Rebalancing logic.
- Per-symbol trade ledgers.
- Portfolio benchmark comparisons.

Exit criteria:

- The lab can test simple allocation strategies across more than one symbol.

## Near-Term Recommendation

Start Milestone 6 with dataset fingerprints.

Reason: the lab now records experiments and decisions well enough that the next
major risk is trusting a conclusion whose input data silently changed or was
never described clearly enough.
