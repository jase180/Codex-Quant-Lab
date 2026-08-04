# SPY Rolling-Low Reversion Experiment

## Role

Tracked experiment handoff for ignored local artifacts in:

```text
artifacts/research/spy_rolling_low_reversion/
```

Read the canonical local conclusion first when artifacts are available:

```text
artifacts/research/spy_rolling_low_reversion/experiment_conclusion.md
```

## Why This Was Run

Codex acted as the research chooser, without Ollama, after the Donchian
breakout and SPY/TLT allocation branches were rejected. The idea suggestion
pipeline pointed to:

```text
statistical_reversion / rolling_low_reversion
```

This was intended to test a different family from trend following and static
allocation while changing only one meaningful research idea.

## Capability Caveat

The current strategy schema can express a fresh rolling-low break, but it cannot
yet express "near the rolling low" or an arithmetic distance from a low. This
experiment therefore tested a stricter executable version:

- Entry: close breaks below the prior 20-day rolling low.
- Exit: close crosses above a 10-day SMA.

Do not treat this result as a full test of all statistical reversion ideas.

## Strategy

Executable strategy:

```text
data/strategies/spy_rolling_low_reversion.json
```

Rule:

- Indicator: 20-day rolling low of close.
- Indicator: 10-day SMA of close.
- Entry: buy when close is less than the prior 20-day rolling low.
- Exit: move to cash when close crosses above the 10-day SMA.
- Execution: existing v1 rule path, where bar `t` signals fill at bar `t+1`
  open.

## Prespecified Hypothesis

A daily rolling-low reversion rule may improve risk-adjusted return versus SPY
buy-and-hold by buying new short-term lows and exiting after recovery.

## Prespecified Success Criteria

- `risk_adjusted_return`: Sharpe strategy-vs-benchmark delta must be greater
  than `0.0`.

Important trade-offs accepted before running:

- Persistent trends can crush reversion entries.
- Costs can erase small edges.

## Command

The command was invoked through a Python argv wrapper because PowerShell strips
quotes inside JSON success-criterion arguments.

Equivalent command:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli experiment run-default `
  --title "SPY rolling-low reversion test" `
  --hypothesis "A daily rolling-low reversion rule may improve risk-adjusted return versus SPY buy-and-hold by buying new short-term lows and exiting after recovery." `
  --strategy data\strategies\spy_rolling_low_reversion.json `
  --data data\cache\SPY_2015-01-01_2025-12-31.csv `
  --symbol SPY `
  --cost-preset retail-liquid `
  --intended-benefit "Potential short-horizon risk-adjusted return improvement with lower average exposure." `
  --primary-metric sharpe `
  --minimum-acceptable-performance "Improve Sharpe versus buy-and-hold after realistic costs." `
  --tradeoff "Persistent trends can crush reversion entries." `
  --tradeoff "Costs can erase small edges." `
  --success-criterion '{"name":"risk_adjusted_return","metric":"sharpe","comparison":"strategy_vs_benchmark_delta","operator":">","threshold":0.0}' `
  --param low_20.inputs.length=20 `
  --param sma_10.inputs.length=10 `
  --train-end 2020-12-31 `
  --test-start 2021-01-01 `
  --date-window 2015-01-02,2019-12-31 `
  --date-window 2020-01-01,2025-12-30 `
  --out artifacts\research\spy_rolling_low_reversion
```

The singleton parameter values intentionally avoid a broad sweep while still
using the default workflow's sweep and train/test machinery.

## Result

- Experiment id: `EXP-011`.
- Research-system status: `valid`.
- Strategy-hypothesis status: `rejected`.
- Decision: `reject`.
- Baseline total return: `29.88%`.
- Buy-and-hold benchmark total return: `302.73%`.
- Baseline excess total return: `-272.84%`.
- Baseline CAGR: `2.41%`.
- Baseline max drawdown: `-31.66%`.
- Baseline Sharpe: `0.2631`.
- Prespecified Sharpe delta criterion: `fail`, observed `-0.3701`.
- Train/test selected test total return: `26.25%`.
- Test selected run excess total return: `-73.31%`.
- Cost sensitivity: failed; the branch worsened as friction increased.
- Date sensitivity: failed; both tested windows lagged buy-and-hold.
- Benchmark sensitivity: mixed only because the strategy beat cash, not because
  it beat SPY buy-and-hold.

## What This Means

The repo succeeded at measuring the idea honestly and reproducibly. The tested
strategy failed its prespecified investment objective.

The result is a useful negative finding. A new-low mean-reversion rule on SPY
had low growth, high drawdown for the amount of return earned, and poor
out-of-sample excess return versus buy-and-hold. This should not become an
invitation to add many reversion knobs immediately.

## Do Not Repeat

- Do not rerun the same rolling-low branch unless the hypothesis changes.
- Do not treat beating cash as evidence that the strategy is good enough for a
  SPY allocation problem.
- Do not broaden into Bollinger, z-score, or distance-from-low variants until
  the capability gap and revised hypothesis are written down first.

## Next

`quant-lab ideas suggest` was run after this handoff was written. It returned:

```text
No strategy idea suggestion: No executable strategy catalog idea remains after applying do_not_repeat constraints.
```

That is useful behavior: prior conclusions are being carried forward strongly
enough to block repeated executable ideas. The next branch should therefore be a
correctness/benchmark audit or catalog expansion before another strategy run,
rather than forcing another statistical-reversion variant.
