# SPY RSI Pullback Mean-Reversion Experiment

## Role

Tracked experiment handoff for the ignored local artifacts in
`artifacts/research/spy_rsi_pullback_mean_reversion_v2/`.

Read the canonical local conclusion first when artifacts are available:

```text
artifacts/research/spy_rsi_pullback_mean_reversion_v2/experiment_conclusion.md
```

## Why This Was Run

`quant-lab ideas suggest` selected the conceptual `mean_reversion` family after
reading prior conclusions and the strategy catalog. The chosen catalog variant
was `rsi_pullback_long_cash`.

The prior trend-following branch had already produced negative conclusions, so
this test changed one meaningful research idea instead of widening the same
trend-following branch.

## Strategy

Executable strategy:

```text
data/strategies/spy_rsi_pullback_long_cash.json
```

Rule:

- Indicator: 14-day RSI on close.
- Entry: buy when RSI is below 30.
- Exit: move to cash when RSI is at least 55.
- Execution: existing v1 rule path, where bar `t` signals fill at bar `t+1`
  open.

## Prespecified Hypothesis

A daily RSI pullback strategy may improve risk-adjusted return versus SPY
buy-and-hold by concentrating exposure after short-term oversold conditions.

## Prespecified Success Criteria

- `risk_adjusted_return`: Sharpe strategy-vs-benchmark delta must be greater
  than `0.0`.
- `return_retention`: strategy CAGR divided by benchmark CAGR must be at least
  `0.7`.

Important trade-offs accepted before running:

- The rule may catch falling markets where oversold readings keep getting worse.
- The rule may suffer high turnover and cost drag.

## Command

The command was invoked through a Python argv wrapper because PowerShell stripped
quotes inside JSON success-criterion arguments.

Equivalent command:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli experiment run-default `
  --title "SPY RSI pullback mean-reversion test" `
  --hypothesis "A daily RSI pullback strategy may improve risk-adjusted return versus SPY buy-and-hold by concentrating exposure after short-term oversold conditions." `
  --strategy data\strategies\spy_rsi_pullback_long_cash.json `
  --data data\cache\SPY_2015-01-01_2025-12-31.csv `
  --symbol SPY `
  --cost-preset retail-liquid `
  --intended-benefit "Improve risk-adjusted return or lower exposure by buying weakness and exiting after recovery instead of staying fully invested." `
  --primary-metric sharpe `
  --minimum-acceptable-performance "Improve Sharpe versus buy-and-hold while retaining at least 70% of benchmark CAGR after realistic costs." `
  --tradeoff "May catch falling markets where oversold readings keep getting worse." `
  --tradeoff "May suffer high turnover and cost drag." `
  --success-criterion '{"name":"risk_adjusted_return","metric":"sharpe","comparison":"strategy_vs_benchmark_delta","operator":">","threshold":0.0}' `
  --success-criterion '{"name":"return_retention","metric":"cagr","comparison":"strategy_vs_benchmark_ratio","operator":">=","threshold":0.7}' `
  --param rsi_14.inputs.length=14 `
  --train-end 2020-12-31 `
  --test-start 2021-01-01 `
  --date-window 2015-01-02,2019-12-31 `
  --date-window 2020-01-01,2025-12-30 `
  --out artifacts\research\spy_rsi_pullback_mean_reversion_v2
```

The singleton `--param rsi_14.inputs.length=14` intentionally avoids a broad
parameter sweep while satisfying the default workflow's required sweep step.

## Result

- Experiment id: `EXP-008`.
- Research-system status: `valid`.
- Strategy-hypothesis status: `rejected`.
- Decision: `reject`.
- Baseline total return: `27.39%`.
- Buy-and-hold benchmark total return: `302.73%`.
- Baseline excess total return: `-275.34%`.
- Baseline Sharpe: `0.2470`.
- Prespecified Sharpe delta criterion: `fail`, observed `-0.6274`.
- Prespecified return-retention criterion: `fail`, observed `0.1399`.
- Train/test selected test total return: `10.81%`.
- Test selected run excess total return: `-88.75%`.

`EXP-007` was an earlier local run of the same idea before
`benchmark_sharpe_ratio` was added to research-index rows. Treat `EXP-008` as
the cleaner handoff because it evaluates both prespecified criteria.

## What This Means

The repo succeeded at measuring the idea honestly and reproducibly. The tested
RSI pullback rule failed its investment objective.

Do not widen this RSI pullback branch into more thresholds or lengths until the
failure mode is explained in writing. The immediate lesson is not "try more RSI
numbers"; it is that this simple oversold/recovery rule gave up too much SPY
buy-and-hold growth and did not improve Sharpe after realistic costs.

## Next

Before another strategy experiment, run `quant-lab ideas suggest` again and
confirm that prior `do_not_repeat` constraints now steer away from both the
trend-following branch and this exact RSI pullback branch unless the hypothesis
changes materially.
