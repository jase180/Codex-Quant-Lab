# Codex-Quant-Lab Agent Notes

## Project Overview

This is a small Python quant research lab centered on:

- `backtester_core`: a daily OHLCV backtester with next-bar-open market order fills.
- `quant_lab`: strict v1 JSON strategy schema parsing and validation.
- `metrics_reporting`: equity curve metrics, markdown reports, and run artifact persistence.

## Local Setup

- Python 3.10+ is required.
- The package dependency is `pandas>=2.0`.
- Tests are written with `unittest`.

## Tooling Preference

- Prefer WSL for Python, test, package, and development commands in this repo.
- Use PowerShell only when the task specifically needs Windows shell behavior or simple Windows filesystem inspection.
- The Windows checkout path maps to WSL as `/mnt/c/Users/jase1/Documents/Codex/2026-07-04/let-s-get-familiar-with-one`.

Run tests with:

```powershell
python -m unittest discover -s tests
```

If using WSL from this Windows checkout:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Development Guidance

- Keep the backtester simple and deterministic.
- Preserve the current execution rule: signals from bar `t` fill at bar `t+1` open.
- Do not introduce lookahead into strategy evaluation.
- Keep schema validation strict and errors explicit.
- Add focused tests for behavior changes, especially around fills, portfolio accounting, schema validation, and metrics formulas.

## Collaboration Preference

- The repo owner is a junior Go engineer who can read basic Python but is still learning Python practices, idioms, and frameworks.
- Add explanatory comments when code uses Python-specific idioms, non-obvious standard library behavior, pandas conventions, packaging patterns, or backtesting assumptions.
- Prefer comments that explain why a block exists or how data flows through it. Avoid comments that merely restate obvious assignments.
- In final summaries, call out important Python or project-structure choices in plain language when they affect future maintenance.

## Known Environment Note

The Windows shell in this workspace may not expose `python` or `py` on `PATH`. WSL currently has Python 3.12, but the full backtester test suite requires `pandas` to be installed there.
