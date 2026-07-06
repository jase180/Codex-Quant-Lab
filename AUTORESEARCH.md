# Auto Research Protocol

This document defines how Codex should help research trading ideas in this repo.
It is inspired by the human-in-the-loop research assistant style: make fewer
assumptions, show evidence, ask when uncertain, and help the repo owner learn
while the work gets done. It is adapted specifically for quant backtesting.

## Purpose

Use Codex-Quant-Lab to test strategy ideas reproducibly and skeptically.

The goal is not to produce impressive-looking backtests. The goal is to learn
which assumptions matter, which strategy variants are fragile, and which ideas
deserve more careful research.

## Research Loop

Every research task should follow this loop:

1. State the research question.
2. Define the data, date range, instrument, timeframe, and strategy.
3. Run a baseline before variants.
4. Change one thing at a time when possible.
5. Save artifacts for every run.
6. Compare metrics across runs.
7. Perform a skeptic pass.
8. End with the next concrete experiment.

## Research Question Format

Start with a plain-language question:

```text
Does a short/long SMA crossover improve risk-adjusted returns on QQQ daily data
compared with buy-and-hold over the same period?
```

Then write the hypothesis:

```text
Hypothesis: shorter fast windows will react sooner, raising total return, but
may increase drawdown and reduce Sharpe due to more false signals.
```

## Required Run Metadata

Each research run should record:

- strategy file
- data source or CSV path
- symbol
- timeframe
- date range
- initial cash
- sizing mode
- order quantity or allocation
- commission and slippage assumptions
- parameter overrides
- output directory
- Git commit hash
- command used to produce the run

This metadata should be easy to recover from artifacts without relying on chat
history.

## Baseline First

Before a sweep or optimization, run a baseline:

- the unmodified strategy file,
- a simple benchmark if available,
- and the same data range used for variants.

Do not evaluate parameter changes without knowing what they improved over.

## Evidence Artifacts

Every run should write:

- `metrics.json`
- `equity_curve.csv`
- `equity_curve.png`
- `drawdown.png`
- `report.md`
- `trades.csv`
- `run_metadata.json`

Reports and sweep summaries should include buy-and-hold benchmark metrics from
the same data range whenever possible.

`run_metadata.json` is the reproducibility anchor for a run. Prefer reading it
over relying on chat history when reconstructing command inputs, sizing,
commission, slippage, Git commit, or artifact paths.

Fetched market data should be cached under `data/cache/` using normalized daily
OHLCV CSV files. Keep raw provider assumptions in mind: adjusted prices, missing
sessions, provider outages, and corporate action handling can all affect results.

Sweep-style research should also write:

- `summary.csv`
- one subdirectory per run
- a short `research.md` summary when interpretation is needed

## Metrics To Compare

Use these first:

- total return
- CAGR
- Sharpe ratio
- max drawdown
- final equity
- trade count

For strategy debugging, inspect trades directly. A high return with one lucky
trade is not the same kind of evidence as a result supported by many trades.
Use the PNG charts for quick visual inspection, then use the CSV and JSON files
when exact numbers matter.

## Backtesting Guardrails

- No lookahead: signals may only use data available at the current bar close.
- Preserve the current fill rule: signals from bar `t` fill at bar `t+1` open.
- Final-bar signals do not fill because there is no next bar open.
- Compare strategies on the same data range.
- Record whether costs and slippage were enabled before interpreting returns.
- Be skeptical of short samples and tiny trade counts.
- Do not silently change strategy rules while analyzing results.
- Treat missing data, split adjustments, and survivorship bias as research risks.

## Skeptic Pass

After any promising result, ask:

- Did the strategy use future data accidentally?
- Is the result driven by one or two trades?
- Is the sample too short?
- Would costs, slippage, or taxes change the conclusion?
- Did the parameter sweep overfit to this one dataset?
- Did the benchmark use the same dates and assumptions?
- Are the best parameters near other good parameters, or isolated outliers?
- Do the equity and drawdown charts show one isolated event driving the result?

Promising results should be described as candidates for more research, not as
proven edges.

## Agent Behavior

When Codex performs research in this repo:

- Explain assumptions before running commands.
- Prefer small, inspectable experiments.
- Show the command used for important runs.
- Save artifacts instead of relying on chat output.
- Make fewer assumptions and ask when a choice would materially change the result.
- Explain Python, pandas, packaging, and backtesting idioms in plain language when they matter.
- Separate observations from conclusions.
- End each research cycle with one concrete next step.

## Research Directory Convention

Use this shape for larger research tasks:

```text
artifacts/research/<research_id>/
  research.md
  baseline/
  sweep_001/
    summary.csv
    run_001/
    run_002/
```

The `research_id` should be short and descriptive, for example:

```text
sma_crossover_qqq_daily_2015_2025
```

## Sweep Command

Parameter sweeps are available through:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/sample_ohlcv.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=30,50,100 \
  --out artifacts/research/sma_crossover_sweep_001
```

That command should produce per-run artifacts plus a `summary.csv` suitable for
ranking and skeptic-pass inspection.

For now, sweep overrides support indicator input paths such as:

```text
sma_20.inputs.length=5,10,20
```

Keep sweep sizes small until the strategy, data, and baseline are understood.
