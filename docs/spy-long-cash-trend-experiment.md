# SPY Long/Cash Trend Experiment

Report role: supporting interpretation.

This note records the Milestone 15 end-to-end experiment run on July 26, 2026.
The generated artifacts live under `artifacts/research/spy_long_cash_trend/`
and are intentionally ignored by Git. This tracked note preserves the lesson
without committing bulky run outputs.

## Question

Hypothesis:

```text
A daily SPY EMA/RSI trend rule may reduce drawdown versus buy-and-hold without
giving up too much total return.
```

## Setup

- Symbol: `SPY`
- Data: `data/cache/SPY_2015-01-01_2025-12-31.csv`
- Rows fetched: `2765`
- Provider path: `quant-lab fetch` through `yfinance`
- Strategy: `artifacts/research/spy_long_cash_trend/spy_ema_trend_follow.json`
- Sizing: `percent-equity`
- Allocation: `1.0`
- Costs: `retail-liquid`
- Benchmark: `buy-and-hold`
- Experiment id: `EXP-001`

The fetched SPY data uses the repo's current data assumptions: adjusted daily
prices from `yfinance`, with provider semantics recorded in the provenance
sidecar.

## Workflow Run

The workflow used the Milestone 15 default path:

```text
research plan -> baseline -> data trust -> small sweep -> guardrails ->
evidence summary -> canonical conclusion -> decision
```

Key artifacts:

- `artifacts/research/spy_long_cash_trend/research_plan.md`
- `artifacts/research/spy_long_cash_trend/baseline/report.md`
- `artifacts/research/spy_long_cash_trend/baseline/run_trust_report.md`
- `artifacts/research/spy_long_cash_trend/sweep_001/research.md`
- `artifacts/research/spy_long_cash_trend/sweep_001/sweep_guardrails.md`
- `artifacts/research/spy_long_cash_trend/evidence_summary.md`
- `artifacts/research/spy_long_cash_trend/experiment_conclusion.md`
- `artifacts/research/spy_long_cash_trend/agent_context.md`

## Results

Baseline:

- Strategy total return: `57.22%`
- Buy-and-hold total return: `302.73%`
- Excess total return: `-245.51%`
- Data trust result: reproducible input file
- Worst trust warning: `none`

Small sweep:

- Sweep size: `9` runs
- Parameters:
  - `ema_50.inputs.length=25,50,100`
  - `rsi_14.inputs.length=10,14,21`
- Best run: `run_001`
- Best total return: `87.68%`
- Best excess total return: `-215.05%`
- Sweep guardrail warnings:
  - best run did not beat the benchmark,
  - parameter stability was `mixed`.

Conclusion:

- Confidence label: `rejected`
- Current conclusion: the linked evidence does not support the hypothesis.
- Next useful action: stop this branch or reformulate the hypothesis before
  running more tests.

Recorded decision:

- Outcome: `reject`
- Rationale: no linked run beat the benchmark on excess return; best excess was
  `-215.05%`.

## Interpretation

The trend rule reduced drawdown compared with buy-and-hold in some variants,
but it gave up too much total return. The hypothesis explicitly allowed some
return sacrifice, but a best excess return of `-215.05%` is not "without giving
up too much." More robustness checks would mostly confirm an already weak
branch.

Do not broaden this EMA/RSI branch unless the hypothesis changes. A revised
question could focus on drawdown control as the primary objective, but then the
benchmark and success criteria should change before more runs are added.

## Workflow Lessons

- The default workflow is usable end to end.
- `experiment_conclusion.md` is the right file to read first after the run.
- The conclusion correctly avoids recommending validation when every linked run
  underperforms.
- The report hierarchy helped: baseline report and sweep guardrails were useful
  supporting interpretation, while the canonical conclusion carried the final
  answer.
- The generated evidence summary was created before the registry decision, so
  it still showed the experiment status before completion. Regenerating or
  clearly timestamping summaries after decisions may be useful later.
