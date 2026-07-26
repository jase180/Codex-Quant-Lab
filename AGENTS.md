# Codex-Quant-Lab Agent Notes

## Project Overview

This is a small Python quant research lab centered on:

- `backtester_core`: a daily OHLCV backtester with next-bar-open market order fills.
- `quant_lab`: strict v1 JSON strategy schema parsing and validation.
- `metrics_reporting`: equity curve metrics, markdown reports, and run artifact persistence.

## Local Setup

- Python 3.10+ is required.
- Runtime dependencies are listed in `pyproject.toml`: `pandas`, `matplotlib`, and `yfinance`.
- Tests are written with `unittest`.
- The verified local Windows environment is `.venv-win`.

## Tooling Preference

- Prefer WSL for Python, test, package, and development commands when its dependencies are installed.
- In the current checkout, `.venv-win` is the verified working environment; use it when WSL is missing project dependencies.
- Use PowerShell when working from the verified Windows venv, when the task needs Windows shell behavior, or for simple Windows filesystem inspection.
- The Windows checkout path maps to WSL as `/mnt/c/Users/jase1/Documents/Codex/2026-07-04/let-s-get-familiar-with-one`.

Run tests with:

```powershell
$env:MPLCONFIGDIR='artifacts/matplotlib-cache'
.\.venv-win\Scripts\python.exe -m unittest discover -s tests
```

If using WSL from this Windows checkout:

```bash
MPLCONFIGDIR=artifacts/matplotlib-cache python -m unittest discover -s tests
```

## Development Guidance

- Keep the backtester simple and deterministic.
- Preserve the current execution rule: signals from bar `t` fill at bar `t+1` open.
- Do not introduce lookahead into strategy evaluation.
- Keep schema validation strict and errors explicit.
- Add focused tests for behavior changes, especially around fills, portfolio accounting, schema validation, and metrics formulas.
- Keep root and module README files current when behavior, commands, or module responsibilities change.

## Collaboration Preference

- The repo owner is a junior Go engineer who can read basic Python but is still learning Python practices, idioms, and frameworks.
- Add explanatory comments when code uses Python-specific idioms, non-obvious standard library behavior, pandas conventions, packaging patterns, or backtesting assumptions.
- Prefer comments that explain why a block exists or how data flows through it. Avoid comments that merely restate obvious assignments.
- In final summaries, call out important Python or project-structure choices in plain language when they affect future maintenance.

## Known Environment Note

- The Windows shell in this workspace may not expose `python` or `py` on `PATH`; use `.\.venv-win\Scripts\python.exe` for repo commands.
- `quant-lab doctor` has passed in the Windows venv with Python, pandas, matplotlib, yfinance, package imports, writable artifacts, and cached data checks.
- WSL is still preferred for general development when its dependencies are installed, but do not assume WSL has the full Python environment ready.

## Local Agent Runtime

- Ollama for Windows has been installed in the user profile.
- The Ollama executable may not appear on `PATH` in already-open shells. Use `C:\Users\jase1\AppData\Local\Programs\Ollama\ollama.exe` if `ollama` is not found.
- The tested default local advisor model for this repo is `llama3.1:8b`.
- `qwen3:8b` is also installed, but it failed the strict `agent_recommendation.v1` contract during initial integration tests.
- Prefer this model-backed recommendation command when a session manifest exists:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli agent suggest `
  --manifest artifacts\<experiment>\session_manifest.json `
  --provider openai-compatible `
  --base-url http://localhost:11434/v1 `
  --model llama3.1:8b
```
