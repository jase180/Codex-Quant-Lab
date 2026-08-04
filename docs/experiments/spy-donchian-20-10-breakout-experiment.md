# SPY Donchian 20/10 Breakout Experiment

## Role

Tracked experiment handoff for ignored local artifacts in:

```text
artifacts/research/spy_donchian_20_10_breakout/
```

Read the canonical local conclusion first when artifacts are available:

```text
artifacts/research/spy_donchian_20_10_breakout/experiment_conclusion.md
```

## Why This Was Run

Codex acted as the research chooser, without Ollama, and used
`quant-lab ideas suggest` plus prior experiment conclusions. The top currently
executable non-repeated catalog idea was:

```text
breakout_trend / donchian_20_10_long_cash
```

This changed one meaningful research idea after the prior SPY trend-following
and RSI pullback branches were rejected.

## Strategy

Executable strategy:

```text
data/strategies/spy_donchian_20_10_long_cash.json
```

Rule:

- Indicator: 20-day rolling high of close.
- Indicator: 10-day rolling low of close.
- Entry: buy when close is greater than the 20-day rolling high.
- Exit: move to cash when close is less than the 10-day rolling low.
- Execution: existing v1 rule path, where bar `t` signals fill at bar `t+1`
  open.

## Prespecified Hypothesis

A daily Donchian 20/10 breakout rule may improve risk-adjusted return versus SPY
buy-and-hold by entering only after confirmed upside persistence.

## Prespecified Success Criteria

- `risk_adjusted_return`: Sharpe strategy-vs-benchmark delta must be greater
  than `0.0`.
- `return_retention`: strategy CAGR divided by benchmark CAGR must be at least
  `0.7`.

Important trade-offs accepted before running:

- The rule may suffer false breakouts in choppy markets.
- The rule may enter late after large moves.

## Command

The command was invoked through a Python argv wrapper because PowerShell strips
quotes inside JSON success-criterion arguments.

Equivalent command:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli experiment run-default `
  --title "SPY Donchian 20/10 breakout test" `
  --hypothesis "A daily Donchian 20/10 breakout rule may improve risk-adjusted return versus SPY buy-and-hold by entering only after confirmed upside persistence." `
  --strategy data\strategies\spy_donchian_20_10_long_cash.json `
  --data data\cache\SPY_2015-01-01_2025-12-31.csv `
  --symbol SPY `
  --cost-preset retail-liquid `
  --intended-benefit "Potential upside participation with explicit exits when price loses recent support." `
  --primary-metric sharpe `
  --minimum-acceptable-performance "Improve Sharpe versus buy-and-hold and retain at least 70% of benchmark CAGR after realistic costs." `
  --tradeoff "May suffer false breakouts in choppy markets." `
  --tradeoff "May enter late after large moves." `
  --success-criterion '{"name":"risk_adjusted_return","metric":"sharpe","comparison":"strategy_vs_benchmark_delta","operator":">","threshold":0.0}' `
  --success-criterion '{"name":"return_retention","metric":"cagr","comparison":"strategy_vs_benchmark_ratio","operator":">=","threshold":0.7}' `
  --param high_20.inputs.length=20 `
  --param low_10.inputs.length=10 `
  --train-end 2020-12-31 `
  --test-start 2021-01-01 `
  --date-window 2015-01-02,2019-12-31 `
  --date-window 2020-01-01,2025-12-30 `
  --out artifacts\research\spy_donchian_20_10_breakout
```

The singleton parameter values intentionally avoid a broad sweep while still
using the default workflow's sweep and train/test machinery.

## Result

- Experiment id: `EXP-009`.
- Research-system status: `valid`.
- Strategy-hypothesis status: `rejected`.
- Decision: `reject`.
- Baseline total return: `119.99%`.
- Buy-and-hold benchmark total return: `302.73%`.
- Baseline excess total return: `-182.73%`.
- Baseline CAGR: `7.45%`.
- Baseline max drawdown: `-9.31%`.
- Baseline Sharpe: `0.8550`.
- Prespecified Sharpe delta criterion: `fail`, observed `-0.0340`.
- Prespecified return-retention criterion: `fail`, observed `0.5334`.
- Train/test selected test total return: `46.30%`.
- Test selected run excess total return: `-53.27%`.

## What This Means

The repo succeeded at measuring the idea honestly and reproducibly. The tested
strategy failed its prespecified investment objective.

This was closer than the RSI pullback branch. The Donchian rule materially
reduced drawdown and produced positive absolute return, but it did not improve
Sharpe versus buy-and-hold and retained only about 53% of benchmark CAGR. Treat
that as useful evidence, not permission to immediately sweep many breakout
windows.

## Do Not Repeat

- Do not widen this breakout branch into many channel lengths until the failure
  mode is explained in writing.
- Do not call the strategy successful just because drawdown was lower.
- Do not ignore the predefined return-retention threshold.

## Next

Use `quant-lab ideas suggest` again before selecting the next experiment. A
reasonable next direction is to let the catalog choose among remaining
executable families, but avoid another breakout variant unless the hypothesis
changes materially.
