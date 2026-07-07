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
- Compare against buy-and-hold.
- Model simple commission and slippage assumptions.
- Save metrics, reports, trades, equity curves, charts, and metadata.
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

Status: planned.

Goal: reduce false confidence from unrealistic assumptions.

Likely work:

- Add cost presets for common broker assumptions.
- Add explicit data-quality checks for missing dates, zero volume, and suspicious prices.
- Add optional train/test or walk-forward split support.
- Add benchmark variants beyond buy-and-hold.
- Add warnings for tiny trade counts and short samples.

Exit criteria:

- A promising result has enough context to decide whether it deserves more research.

## Milestone 5: Strategy Research Expansion

Status: planned.

Goal: support a broader set of simple, inspectable strategy ideas.

Likely work:

- Add more indicators, such as ATR, rolling high/low, and volatility.
- Add more condition types.
- Add stop-loss and take-profit style exits.
- Add strategy templates or examples for common research patterns.
- Add richer parameter sweep controls.

Exit criteria:

- The lab can test several common daily-system ideas without code changes.

## Milestone 6: Portfolio And Multi-Asset Research

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

Start Milestone 4 next.

Reason: Milestone 3 now covers finding, inspecting, comparing, and documenting
local research runs. The next gap is better validation and realism.
