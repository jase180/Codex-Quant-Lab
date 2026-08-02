# SPY Volatility-Target Drawdown-Control Experiment

Report role: research result handoff.

This note records the first real test of the strategy-layer volatility-target
risk control added after the SPY long/cash SMA drawdown-control branch was
rejected. The generated run artifacts are intentionally ignored by Git; this
tracked note carries the conclusion forward.

## Question

Does adding a close-based volatility target to a daily SPY long/cash SMA trend
rule improve the drawdown/return tradeoff enough to make the branch worth
continuing?

The hypothesis was:

> A daily SPY long/cash SMA trend rule with volatility-targeted percent-equity
> entries may materially reduce max drawdown while retaining at least 65 percent
> of buy-and-hold total return after realistic costs.

## Setup

- Strategy: `data/strategies/sma_long_cash_vol_target.json`
- Data: `data/cache/SPY_2015-01-01_2025-12-31.csv`
- Costs: `retail-liquid`
- Sizing: `percent-equity`, allocation `1.0`
- Benchmark: `buy-and-hold`
- Volatility target: 20-day close-to-close realized volatility, 12% annual
  target, allocation clamped from 25% to 100%
- SMA sweep: `100`, `150`, `200`
- Train/test split: train through `2020-12-31`, test from `2021-01-01`
- Date windows:
  - `2015-01-02` to `2019-12-31`
  - `2020-01-01` to `2025-12-30`
  - `2018-01-01` to `2022-12-31`

## Command

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli experiment run-default `
  --title "SPY SMA volatility-target drawdown-control test" `
  --hypothesis "A daily SPY long/cash SMA trend rule with volatility-targeted percent-equity entries may materially reduce max drawdown while retaining at least 65 percent of buy-and-hold total return after realistic costs." `
  --strategy data\strategies\sma_long_cash_vol_target.json `
  --data data\cache\SPY_2015-01-01_2025-12-31.csv `
  --symbol SPY `
  --cost-preset retail-liquid `
  --param sma_100.inputs.length=100,150,200 `
  --train-end 2020-12-31 `
  --test-start 2021-01-01 `
  --date-window 2015-01-02,2019-12-31 `
  --date-window 2020-01-01,2025-12-30 `
  --date-window 2018-01-01,2022-12-31 `
  --tag canonical-spy `
  --tag drawdown-control `
  --tag volatility-target `
  --out artifacts\research\spy_sma_vol_target_drawdown_control
```

## Generated Artifacts

Read first:

- `artifacts/research/spy_sma_vol_target_drawdown_control/experiment_conclusion.md`

Supporting artifacts:

- `artifacts/research/spy_sma_vol_target_drawdown_control/default_workflow_summary.md`
- `artifacts/research/spy_sma_vol_target_drawdown_control/baseline/run_metadata.json`
- `artifacts/research/spy_sma_vol_target_drawdown_control/baseline/strategy.json`
- `artifacts/research/spy_sma_vol_target_drawdown_control/sweep_001/summary.csv`
- `artifacts/research/spy_sma_vol_target_drawdown_control/train_test_001/test_summary/summary.csv`
- `artifacts/research/spy_sma_vol_target_drawdown_control/cost_sensitivity_001/cost_sensitivity_report.md`
- `artifacts/research/spy_sma_vol_target_drawdown_control/date_sensitivity_001/date_sensitivity_report.md`

## Result

The default workflow created experiment `EXP-005` and recorded the decision as
`reject`.

Baseline full-period result:

- Strategy total return: `96.05%`
- Buy-and-hold total return: `302.73%`
- Return retained: about `23.8%`
- Excess total return: `-206.68%`
- Strategy max drawdown: `-13.00%`
- Buy-and-hold max drawdown: `-33.72%`
- Drawdown improvement: about `61.4%`
- Strategy Sharpe: `0.8386`
- Buy-and-hold Sharpe: `0.8032`
- Trades: `105`

Best full-period sweep row:

- SMA length: `100`
- Total return: `96.05%`
- Max drawdown: `-13.00%`
- Sharpe: `0.8386`
- Excess total return: `-206.68%`

Selected train/test result:

- Selected SMA length: `100`
- Test total return: `34.76%`
- Test buy-and-hold total return: `99.56%`
- Test return retained: about `33.8%`
- Test excess total return: `-64.80%`
- Test max drawdown: `-11.43%`
- Test buy-and-hold max drawdown: `-24.50%`
- Test drawdown improvement: about `53.3%`
- Test Sharpe: `0.8747`
- Test buy-and-hold Sharpe: `0.8975`

Cost sensitivity:

- `retail-liquid`: return `96.05%`, excess `-206.68%`
- `retail-conservative`: return `81.85%`, excess `-220.87%`
- `high-friction`: return `50.57%`, excess `-252.15%`

Date sensitivity:

- `2015-01-02` to `2019-12-31`: return `24.11%`, excess `-48.78%`
- `2020-01-01` to `2025-12-30`: return `62.51%`, excess `-68.26%`
- `2018-01-01` to `2022-12-31`: return `26.67%`, excess `-28.31%`

## Interpretation

Volatility targeting did what it was mechanically supposed to do: it reduced
drawdown. But it reduced exposure so much that the return-retention criterion
failed badly. Compared with the prior SPY SMA drawdown-control run, the
vol-target version improved drawdown more but retained much less of
buy-and-hold's return.

This suggests the current risk control is too blunt for the revised hypothesis.
It behaves more like a capital-preservation overlay than a drawdown-control
overlay that still participates enough in SPY's upside.

## Do Not Repeat

- Do not keep tuning SMA length inside this exact long/cash plus 12% vol-target
  branch.
- Do not treat the higher Sharpe as enough when return retention is far below
  the pre-committed 65% threshold.
- Do not broaden into a large vol-target parameter sweep until the next
  hypothesis explains why exposure should remain high enough to retain upside.

## Next Useful Research Move

The next experiment should change the risk-control idea, not just the SMA
length. A better candidate is a less binary exposure model: stay partially
invested below the trend filter instead of exiting fully to cash, or use
volatility targeting as a cap on an always-invested trend allocation.

Before expanding risk controls further, keep the adjusted-price correctness
audit as the highest technical risk, because all SPY conclusions depend on
consistent adjusted prices, fills, and benchmark treatment.
