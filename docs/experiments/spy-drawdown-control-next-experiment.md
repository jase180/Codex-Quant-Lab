# SPY Drawdown-Control Next Experiment

Report role: research design handoff.

This note defines the first post-v1 research cycle after the rejected SPY
200-day SMA long/cash experiment. It turns the prior conclusion into a narrower
test with explicit success criteria before another backtest is run.

## Prior Result

The previous SPY 200-day SMA long/cash branch was rejected for the original
benchmark-outperformance hypothesis.

Important prior evidence:

- Strategy total return: `148.39%`
- SPY buy-and-hold total return: `302.73%`
- Excess total return versus buy-and-hold: `-154.34%`
- Strategy max drawdown: `-20.37%`
- SPY buy-and-hold max drawdown: `-33.72%`
- Train/test selected-run excess return: `-57.73%`
- Cost sensitivity: failed versus buy-and-hold
- Date sensitivity: failed versus buy-and-hold
- Benchmark sensitivity: mixed, because the strategy beat cash but not
  buy-and-hold

Conclusion: do not keep tuning SMA lengths as if the goal is benchmark
outperformance.

## Revised Hypothesis

A daily SPY long/cash trend rule may be useful as a drawdown-control overlay
only if it materially reduces max drawdown while keeping return drag versus
buy-and-hold within a predefined acceptable limit after realistic costs.

This is different from the rejected hypothesis. The new question is not "does
it beat SPY buy-and-hold?" The new question is "is the risk reduction worth the
return sacrifice?"

## Success Criteria

The next experiment should be considered interesting only if all of these are
true on the test period and robustness checks:

- Max drawdown improves by at least `25%` relative to buy-and-hold.
- Total return keeps at least `65%` of buy-and-hold total return.
- Sharpe ratio is not worse than buy-and-hold by more than `0.10`.
- Retail-liquid costs do not change the interpretation.
- Date windows do not show the result depends on one obvious regime.

The 200-day SMA baseline improved max drawdown by about `40%` relative to
buy-and-hold, but kept only about `49%` of buy-and-hold total return. That
failed the return-retention threshold, so this next cycle needs either a less
defensive rule or a clear reason to accept lower retention.

## What Not To Repeat

- Do not optimize a larger SMA sweep just to find a prettier backtest row.
- Do not accept "beats cash" as enough for a SPY long/cash overlay.
- Do not call the result promising unless the return-retention threshold is met.
- Do not run a new strategy until adjusted-price assumptions remain acceptable
  for this data set.

## Candidate Next Test

Use the existing SPY long/cash SMA strategy machinery, but test a less defensive
trend threshold neighborhood:

- `100` trading-day SMA
- `150` trading-day SMA
- `200` trading-day SMA as the prior anchor

Reasoning:

- A shorter SMA may re-enter sooner after selloffs.
- Faster re-entry may retain more upside.
- The prior `200` value remains in the sweep so the new test can prove whether
  the revised objective actually changes the preferred parameter.

This is still a simple hypothesis. It changes one meaningful research idea:
the objective has shifted from benchmark outperformance to a bounded
drawdown/return tradeoff.

## Planned Command Shape

Use the default workflow so the next result still produces the full evidence
chain:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli experiment run-default `
  --title "SPY SMA drawdown-control overlay test" `
  --hypothesis "A daily SPY long/cash SMA trend rule may be useful as a drawdown-control overlay only if it materially reduces max drawdown while retaining at least 65 percent of buy-and-hold total return after realistic costs." `
  --strategy artifacts\research\spy_200_sma_long_cash\spy_sma_200_long_cash.json `
  --data data\cache\SPY_2015-01-01_2025-12-31.csv `
  --symbol SPY `
  --cost-preset retail-liquid `
  --param sma_200.inputs.length=100,150,200 `
  --train-end 2020-12-31 `
  --test-start 2021-01-01 `
  --date-window 2015-01-02,2019-12-31 `
  --date-window 2020-01-01,2025-12-30 `
  --date-window 2018-01-01,2022-12-31 `
  --tag canonical-spy `
  --tag drawdown-control `
  --out artifacts\research\spy_sma_drawdown_control_overlay
```

## Interpretation Rule

If the result still fails the return-retention threshold, stop this SMA
long/cash family for now. The next move should not be another SMA length tweak;
it should be a different risk-control mechanism or a correctness/data audit.

## Run Result

The planned default workflow was run after this design was written.

Generated artifacts:

- `artifacts/research/spy_sma_drawdown_control_overlay/experiment_conclusion.md`
- `artifacts/research/spy_sma_drawdown_control_overlay/default_workflow_summary.md`
- `artifacts/research/spy_sma_drawdown_control_overlay/sweep_001/summary.csv`
- `artifacts/research/spy_sma_drawdown_control_overlay/train_test_001/test_summary/summary.csv`

Workflow outcome:

- Experiment id: `EXP-004`
- Default decision: `reject`
- Read-first file:
  `artifacts/research/spy_sma_drawdown_control_overlay/experiment_conclusion.md`

Best full-period sweep row:

- SMA length: `100`
- Strategy total return: `153.78%`
- Buy-and-hold total return: `302.73%`
- Return retained: about `50.3%`
- Strategy max drawdown: `-17.56%`
- Buy-and-hold max drawdown: `-33.72%`
- Drawdown improvement: about `47.9%`
- Strategy Sharpe: `0.8343`
- Buy-and-hold Sharpe: `0.8032`

Selected train/test result:

- Selected SMA length: `100`
- Test total return: `55.64%`
- Test buy-and-hold total return: `99.56%`
- Test return retained: about `55.9%`
- Test max drawdown: `-17.56%`
- Test buy-and-hold max drawdown: `-24.50%`
- Test drawdown improvement: about `28.3%`
- Test Sharpe: `0.8837`
- Test buy-and-hold Sharpe: `0.8975`

Result against pre-committed success criteria:

- Max drawdown improved by at least `25%`: passed.
- Total return retained at least `65%` of buy-and-hold: failed.
- Sharpe no worse than buy-and-hold by more than `0.10`: passed.
- Retail-liquid costs did not change the interpretation: failed in the broader
  default workflow because cost sensitivity still did not beat the benchmark.
- Date windows did not show one-regime dependence: failed in the broader
  default workflow because all requested date windows had negative excess return.

Conclusion:

The revised drawdown-control hypothesis is still not strong enough. A shorter
SMA improved drawdown and Sharpe shape, but the return-retention threshold was
not met in either the full-period sweep or the selected test period.

Do not keep tuning SMA lengths in this long/cash family for now. The next
research move should be either:

- a different risk-control mechanism that can re-enter faster without whipsawing
  so much, or
- a correctness audit around adjusted-price and benchmark treatment before
  drawing stronger conclusions from SPY daily data.
