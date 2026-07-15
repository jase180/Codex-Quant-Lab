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

Create an experiment record for the hypothesis:

```bash
quant-lab new-experiment \
  --title "QQQ SMA crossover research" \
  --hypothesis "Faster moving-average windows may reduce drawdown, but may also underperform buy-and-hold during strong trends." \
  --tag QQQ \
  --tag sma \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv
```

The command prints an id such as `EXP-001`. Use that id on related `run` and
`sweep` commands so generated `run_metadata.json` files are linked back to the
experiment automatically.

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
  --benchmark buy-and-hold \
  --commission-rate 0.0005 \
  --slippage-bps 5 \
  --experiment-id EXP-001 \
  --note "Hypothesis: SMA crossovers may reduce drawdown but may underperform strong trends." \
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
research_note.md
```

The run also appends one row to:

```text
artifacts/research_index.jsonl
```

It also appends the generated `run_metadata.json` path to the experiment's
`linked_runs` when `--experiment-id` is provided.

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
  --benchmark buy-and-hold \
  --commission-rate 0.0005 \
  --slippage-bps 5 \
  --experiment-id EXP-001 \
  --note-file docs/local_notes/sma_qqq_hypothesis.md \
  --out artifacts/research/sma_qqq_2015_2025/sweep_001
```

Each sweep sub-run writes its own artifacts and appends its own row to the
research index. Each sub-run also links its metadata path to the experiment
record when `--experiment-id` is provided.

Use `--note` for a short inline hypothesis or `--note-file` when the note is
longer. The saved `research_note.md` should explain what you were trying to
learn before you inspect the result.

After the sweep, read `research.md` before picking a winner. It includes a
top-runs table and a parameter-stability heuristic. `supported` is better than
`isolated`, but none of these labels prove an edge.

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

## 6. Run A Train/Test Check

When a sweep looks promising, repeat the sweep with a train/test date split
before treating the result as meaningful:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --sizing percent-equity \
  --allocation 1.0 \
  --benchmark buy-and-hold \
  --cost-preset retail-liquid \
  --experiment-id EXP-001 \
  --train-end 2020-12-31 \
  --test-start 2021-01-01 \
  --select-by sharpe_ratio \
  --out artifacts/research/sma_qqq_2015_2025/train_test_001
```

This runs all parameter variants on the train period, chooses one winner by the
selection metric, and reruns only that selected variant on the test period. The
test result is out-of-sample relative to parameter selection, but it is still
only evidence. It can fail on another symbol, data provider, cost assumption, or
date range.

Inspect these files first:

```text
train_sweep/summary.csv
test_summary/summary.csv
test_selected/run_metadata.json
research.md
```

The train and test periods must not overlap. If you move the split date after
seeing the result, record that as a new experiment instead of overwriting the
old one.

## 7. Inspect One Run

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
- benchmark choice,
- total return,
- benchmark return,
- excess return,
- drawdown,
- Sharpe,
- trade count,
- artifact paths.

If the result looks promising, open the run's `report.md`, `trades.csv`,
`equity_curve.png`, and `drawdown.png`.

## 8. Run Walk-Forward Windows

If a single train/test split still looks interesting, run explicit
walk-forward windows:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --sizing percent-equity \
  --allocation 1.0 \
  --cost-preset retail-liquid \
  --experiment-id EXP-001 \
  --walk-forward-window 2015-01-01,2018-12-31,2019-01-01,2020-12-31 \
  --walk-forward-window 2017-01-01,2020-12-31,2021-01-01,2022-12-31 \
  --select-by sharpe_ratio \
  --out artifacts/research/sma_qqq_2015_2025/walk_forward_001
```

Read `walk_forward_summary.csv` and `research.md`. Do not move window dates
after seeing the output; use a new output folder for a new experiment.

## 9. Compare Runs

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

## 10. Summarize The Experiment Evidence

After the baseline, sweep, and validation runs are linked to the experiment,
summarize the whole evidence set:

```bash
quant-lab summarize-experiment \
  --experiment-id EXP-001 \
  --index-path artifacts/research_index.jsonl
```

Read the strongest and weakest excess-return lines together. A good research
decision should explain both, not only the best run. Also check the run type
breakdown so you can tell whether the support came from one broad sweep, a
train/test validation, or repeated walk-forward tests.

## 11. Write A Skeptic Pass

For any promising result, answer:

- Did the strategy beat buy-and-hold on the same dates?
- Would the interpretation change against `--benchmark cash`?
- Is the result driven by one or two trades?
- Are costs and slippage included?
- Is the sample long enough?
- Are nearby parameter values also good, or is the best result isolated?
- Does sweep `research.md` label the best run as `supported`, `mixed`,
  `isolated`, or `grid_too_sparse`?
- Did the selected train winner survive the later test period?
- Did test behavior stay consistent across walk-forward windows?
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

## 12. Decide The Next Experiment

Good next experiments are small:

- rerun the same idea on SPY,
- extend or shorten the date range,
- test nearby parameter windows,
- compare with no-cost and with-cost assumptions,
- inspect trades around major drawdowns.

Avoid jumping to a more complex strategy until the simple result is understood.

Record the decision while the evidence is fresh:

```bash
quant-lab decide-experiment \
  --experiment-id EXP-001 \
  --outcome continue \
  --rationale "The sweep improved drawdown, but the train/test check is not strong enough yet." \
  --supporting-run artifacts/research/sma_qqq_2015_2025/sweep_001/run_004/run_metadata.json \
  --contradicting-run artifacts/research/sma_qqq_2015_2025/train_test_001/test_selected/run_metadata.json \
  --next-action "Run walk-forward windows and test the same idea on SPY." \
  --tag needs-walk-forward
```

Use `accept` only when the evidence is strong enough to promote the idea to a
stricter validation or paper-trading phase. Use `reject` when the evidence does
not justify more time. Use `continue` when the next action is still research.

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
