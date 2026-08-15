# Research Workflow

This guide shows one complete local research loop in Codex-Quant-Lab.

The goal is not to prove a trading edge. The goal is to create inspectable
evidence, compare it with a benchmark, and decide the next experiment.

For a copyable command sequence with the trust checks included, see
[trustworthy-example-workflow.md](trustworthy-example-workflow.md).

## 1. Start From A Research Question

Example:

```text
Does a daily SPY 200-day SMA long/cash rule improve drawdown-adjusted
performance versus SPY buy-and-hold after realistic costs?
```

Write the hypothesis and pass/fail idea before running anything:

```text
Hypothesis: a daily SPY close-above-200-day-SMA long/cash rule may reduce
max drawdown versus buy-and-hold while retaining enough total return to be
useful after realistic costs.

Prespecified criteria:
- retain at least 80% of buy-and-hold CAGR,
- reduce maximum drawdown by at least 25% relative,
- remain acceptable after retail-liquid costs.
```

## 2. Fetch Or Choose Data

Fetch fresh data:

```bash
quant-lab fetch \
  --symbol SPY \
  --start 2015-01-01 \
  --end 2025-12-31 \
  --out data/cache
```

Or use an existing cached file:

```text
data/cache/SPY_2015-01-01_2025-12-31.csv
```

Market data is research input, not ground truth. Provider adjustments, missing
sessions, outages, and corporate actions can change conclusions.

## 3. Optional: Inspect Mechanism Raw Material

If the research question starts from a market mechanism instead of a ready
strategy, inspect the raw-material dataset before creating strategy JSON.

For the calendar/rebalance mechanism, the current generated event calendar
labels month-end and quarter-end trading-day windows without looking at returns:

```bash
quant-lab event-calendar inspect \
  --calendar data/event_calendars/calendar_rebalance_daily_proxy_2015_2025.csv
```

This is not a backtest. It answers a narrower question first: are the event rows
well-formed, sourced, and generated without return data?

## 4. Create The Strategy

Generate the basic SPY SMA long/cash strategy directly:

```bash
quant-lab new-strategy \
  --template sma-long-cash \
  --symbol SPY \
  --length 200 \
  --strategy-id spy_sma_200_long_cash \
  --name "SPY 200-day SMA long/cash" \
  --out artifacts/research/spy_200_sma_long_cash/spy_sma_200_long_cash.json
```

Read the generated JSON before running it. The strategy should have one
`sma_200` indicator, enter when close is above that SMA, and exit when close is
below it.

## 5. Run The Default Experiment Workflow

For normal one-strategy research, use `experiment run-default` first. It is the
front door.

If the next strategy idea is not chosen yet, start one step earlier:

```bash
quant-lab ideas suggest
```

This command reads prior `experiment_conclusion.json` files, experiment registry
decisions, tracked handoff docs, the conceptual strategy catalog in
`data/strategy_catalog/`, and the opportunity-thesis catalog in
`data/opportunity_catalog/`. It suggests one hypothesis, success criteria, and a
draft experiment config, but it does not create executable strategy JSON. When a
compatible `opportunity_thesis.v1` exists, the draft also names the market
niche, forced actor, institutional-friction claim, evidence-quality label,
edge-decay trigger, and falsification tests. That keeps idea selection separate
from implementation until a human approves the next test. The catalog can
contain many ideas that are not yet executable; use
`engine_can_currently_execute` to tell concept from current engine support.

```bash
quant-lab experiment run-default \
  --title "SPY 200-day SMA long/cash drawdown test" \
  --hypothesis "A daily SPY 200-day moving-average long/cash strategy may improve drawdown-adjusted performance versus SPY buy-and-hold after realistic costs." \
  --strategy artifacts/research/spy_200_sma_long_cash/spy_sma_200_long_cash.json \
  --data data/cache/SPY_2015-01-01_2025-12-31.csv \
  --symbol SPY \
  --cost-preset retail-liquid \
  --intended-benefit "lower drawdown with acceptable return retention" \
  --primary-metric max_drawdown \
  --minimum-acceptable-performance "Retain at least 80% of buy-and-hold CAGR and reduce max drawdown by at least 25% relative." \
  --tradeoff "May underperform SPY total return during strong bull markets." \
  --success-criterion '{"name":"return_retention","metric":"cagr","comparison":"strategy_vs_benchmark_ratio","operator":">=","threshold":0.8}' \
  --success-criterion '{"name":"drawdown_reduction","metric":"max_drawdown","comparison":"relative_reduction_vs_benchmark","operator":">=","threshold":0.25}' \
  --param sma_200.inputs.length=150,200,250 \
  --train-end 2020-12-31 \
  --test-start 2021-01-01 \
  --date-window 2015-01-02,2019-12-31 \
  --date-window 2020-01-01,2025-12-30 \
  --out artifacts/research/spy_200_sma_long_cash_default
```

This one command runs:

```text
baseline run
run trust report
parameter sweep
train/test validation
cost sensitivity
date sensitivity
benchmark sensitivity
evidence summary
experiment conclusion
conservative decision
```

Read this first:

```text
artifacts/research/spy_200_sma_long_cash_default/experiment_conclusion.md
```

The conclusion reports two independent outcomes:

- `Research-system status`: whether the repo measured the experiment honestly
  and reproducibly.
- `Strategy-hypothesis status`: whether the strategy met the prespecified
  investment criteria.

A valid negative result is possible and useful:

```text
Research-system status: valid
Strategy-hypothesis status: rejected
Interpretation: the repo worked; the strategy failed its investment objective.
```

Then inspect supporting files only as needed:

```text
default_workflow_summary.md
baseline/report.md
baseline/run_metadata.json
sweep_001/research.md
train_test_001/research.md
cost_sensitivity_001/cost_sensitivity_report.md
date_sensitivity_001/date_sensitivity_report.md
```

## Advanced Manual Workflow

Use the lower-level commands when you need to inspect or customize one step at
a time. They are the maintenance entrance, not the normal front door.

### Create A Guided Plan

```bash
quant-lab research-plan init \
  --title "QQQ SMA crossover research" \
  --hypothesis "Faster moving-average windows may reduce drawdown, but may also underperform buy-and-hold during strong trends." \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --symbol QQQ \
  --tag QQQ \
  --tag sma \
  --cost-preset retail-liquid \
  --out artifacts/research/sma_qqq_2015_2025
```

Ask the plan for the next recommended command:

```bash
quant-lab research-plan next \
  --plan artifacts/research/sma_qqq_2015_2025/research_plan.json
```

### Run A Baseline

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

Before widening the research branch, write a data trust report:

```bash
quant-lab summarize-run-trust \
  --metadata artifacts/research/sma_qqq_2015_2025/baseline/run_metadata.json
```

The trust report checks whether the current local CSV still matches the saved
fingerprint and summarizes source/provenance plus data-quality warnings. This
does not prove the strategy works; it only makes the input data easier to
explain before more runs depend on it.

### Run A Controlled Sweep

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

### Find Candidate Runs

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
  --index-path artifacts/research_index.jsonl \
  --out artifacts/research/sma_qqq_2015_2025/evidence_summary.md
```

Read the strongest and weakest excess-return lines together. A good research
decision should explain both, not only the best run. Also check the run type
breakdown so you can tell whether the support came from one broad sweep, a
train/test validation, or repeated walk-forward tests. The saved evidence
summary also includes a conservative evidence label and the reasons for that
label.

After evidence and robustness checks are visible, write the canonical conclusion
that humans, future Codex sessions, and local agents should read first:

```bash
quant-lab conclude-experiment \
  --experiment-id EXP-001 \
  --index-path artifacts/research_index.jsonl \
  --out artifacts/research/sma_qqq_2015_2025
```

This writes `experiment_conclusion.md`, `experiment_conclusion.json`, and
`agent_context.md`. The Markdown is the main human conclusion. The JSON is the
machine-readable research memory for future agent-assisted cycles.

Refresh the session manifest so future you, Codex, or a local agent can resume
from one orientation file:

```bash
quant-lab session refresh \
  --plan artifacts/research/sma_qqq_2015_2025/research_plan.json
```

When returning later, read `session_manifest.md` first to find the current
status, warnings, conclusion path, decision pointer, and next suggested command.
Then read `experiment_conclusion.md` for what the experiment actually taught.

Draft a decision before writing one:

```bash
quant-lab draft-decision \
  --experiment-id EXP-001 \
  --index-path artifacts/research_index.jsonl
```

The draft is a conservative template. It does not write to the experiment
registry. Treat it as a checklist, then edit the rationale and next action
before running `decide-experiment`.

## 11. Write A Skeptic Pass

For any promising result, answer:

- Did the strategy beat buy-and-hold on the same dates?
- Did you read the generated benchmark assumptions, especially first-close
  entry, no benchmark costs, and adjusted-price dividend treatment?
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
  --session-manifest artifacts/research/sma_qqq_2015_2025/session_manifest.json \
  --tag needs-walk-forward
```

Use `accept` only when the evidence is strong enough to promote the idea to a
stricter validation or paper-trading phase. Use `reject` when the evidence does
not justify more time. Use `continue` when the next action is still research.
Passing `--session-manifest` marks the session complete and records the decision
pointer in the manifest.

## Artifact Rule

If a result matters, keep the artifact folder. Chat history is not the source of
truth. The source of truth is:

```text
session_manifest.md
experiment_conclusion.md
run_metadata.json
research_warnings.json
metrics.json
trades.csv
equity_curve.csv
report.md
charts
research_index.jsonl
```
