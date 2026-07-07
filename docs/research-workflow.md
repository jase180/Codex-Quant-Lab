# Research Workflow

This guide shows one complete local research loop in Codex-Quant-Lab.

The goal is not to prove a trading edge. The goal is to create inspectable
evidence, compare it with a benchmark, and decide the next experiment.

## 1. Start From A Research Question

Example:

```text
Does a daily SMA crossover on QQQ improve risk-adjusted returns compared with
buy-and-hold over the same data range?
```

Write the hypothesis before running the sweep:

```text
Hypothesis: faster moving-average windows may reduce drawdown, but may also
underperform buy-and-hold if they exit during strong trends.
```

## 2. Fetch Or Choose Data

Fetch fresh data:

```bash
quant-lab fetch \
  --symbol QQQ \
  --start 2015-01-01 \
  --end 2025-12-31 \
  --out data/cache
```

Or use an existing cached file:

```text
data/cache/QQQ_2015-01-01_2025-12-31.csv
```

Market data is research input, not ground truth. Provider adjustments, missing
sessions, outages, and corporate actions can change conclusions.

## 3. Run A Baseline

Run the unmodified strategy before changing parameters:

```bash
quant-lab run \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --sizing percent-equity \
  --allocation 1.0 \
  --commission-rate 0.0005 \
  --slippage-bps 5 \
  --out artifacts/research/sma_qqq_2015_2025/baseline
```

The run directory should include:

```text
metrics.json
equity_curve.csv
equity_curve.png
drawdown.png
report.md
trades.csv
run_metadata.json
research_warnings.json
```

The run also appends one row to:

```text
artifacts/research_index.jsonl
```

## 4. Run A Controlled Sweep

Change a small set of parameters, and keep the data, sizing, commission, and
slippage assumptions the same as the baseline:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --sizing percent-equity \
  --allocation 1.0 \
  --commission-rate 0.0005 \
  --slippage-bps 5 \
  --out artifacts/research/sma_qqq_2015_2025/sweep_001
```

Each sweep sub-run writes its own artifacts and appends its own row to the
research index.

## 5. Find Candidate Runs

List the best QQQ runs by Sharpe ratio:

```bash
quant-lab list-runs \
  --symbol QQQ \
  --strategy-id sma_crossover \
  --sort sharpe_ratio \
  --limit 10
```

List only sweep runs:

```bash
quant-lab list-runs \
  --symbol QQQ \
  --strategy-id sma_crossover \
  --run-type sweep_run \
  --sort total_return \
  --limit 10
```

Export a filtered table for external analysis:

```bash
quant-lab list-runs \
  --symbol QQQ \
  --strategy-id sma_crossover \
  --run-type sweep_run \
  --sort total_return \
  --limit 20 \
  --csv
```

## 6. Inspect One Run

Use `show-run` on a candidate run:

```bash
quant-lab show-run \
  --metadata artifacts/research/sma_qqq_2015_2025/sweep_001/run_004/run_metadata.json
```

Check:

- data range,
- strategy id,
- parameter overrides,
- sizing,
- commission and slippage,
- total return,
- benchmark return,
- excess return,
- drawdown,
- Sharpe,
- trade count,
- artifact paths.

If the result looks promising, open the run's `report.md`, `trades.csv`,
`equity_curve.png`, and `drawdown.png`.

## 7. Compare Runs

Compare the baseline against a candidate sweep run:

```bash
quant-lab compare-runs \
  --metadata artifacts/research/sma_qqq_2015_2025/baseline/run_metadata.json \
  --metadata artifacts/research/sma_qqq_2015_2025/sweep_001/run_004/run_metadata.json
```

Compare several sweep candidates:

```bash
quant-lab compare-runs \
  --metadata artifacts/research/sma_qqq_2015_2025/sweep_001/run_001/run_metadata.json \
  --metadata artifacts/research/sma_qqq_2015_2025/sweep_001/run_004/run_metadata.json \
  --metadata artifacts/research/sma_qqq_2015_2025/sweep_001/run_009/run_metadata.json
```

Do not choose a run by total return alone. Look at drawdown, Sharpe, trade
count, and excess return over buy-and-hold.

## 8. Write A Skeptic Pass

For any promising result, answer:

- Did the strategy beat buy-and-hold on the same dates?
- Is the result driven by one or two trades?
- Are costs and slippage included?
- Is the sample long enough?
- Are nearby parameter values also good, or is the best result isolated?
- Would the conclusion change if the data range started or ended differently?
- Does the drawdown chart show behavior you would actually tolerate?

Example conclusion:

```text
Observation: run_004 had higher total return than the baseline and lower
drawdown than buy-and-hold, but it still underperformed buy-and-hold on total
return.

Conclusion: this is not evidence of an edge yet. Next, test whether nearby SMA
windows produce similar results and whether the result survives a different
date range.
```

## 9. Decide The Next Experiment

Good next experiments are small:

- rerun the same idea on SPY,
- extend or shorten the date range,
- test nearby parameter windows,
- compare with no-cost and with-cost assumptions,
- inspect trades around major drawdowns.

Avoid jumping to a more complex strategy until the simple result is understood.

## Artifact Rule

If a result matters, keep the artifact folder. Chat history is not the source of
truth. The source of truth is:

```text
run_metadata.json
research_warnings.json
metrics.json
trades.csv
equity_curve.csv
report.md
charts
research_index.jsonl
```
