# SPY 200-Day SMA Long/Cash Experiment

Report role: supporting interpretation.

This note preserves the canonical SPY 200-day moving-average long/cash
experiment run on August 1, 2026. The detailed generated artifacts live under
`artifacts/research/spy_200_sma_long_cash/` and are intentionally ignored by
Git. The tracked note keeps the conclusion visible without committing bulky run
outputs.

## Question

Hypothesis:

```text
A daily SPY 200-day moving-average long/cash strategy may improve
drawdown-adjusted performance versus SPY buy-and-hold after realistic costs.
```

## Setup

- Symbol: `SPY`
- Data: `data/cache/SPY_2015-01-01_2025-12-31.csv`
- Rows fetched: `2765`
- Data range: `2015-01-02` to `2025-12-30`
- Provider path: `quant-lab fetch` through `yfinance`
- Price policy: `auto_adjust=True`, `actions=False`
- Strategy template: `sma-long-cash`
- Strategy length: `200`
- Sizing: `percent-equity`
- Allocation: `1.0`
- Costs: `retail-liquid`
- Benchmark: `buy-and-hold`
- Experiment id: `EXP-001`

The SPY cache was refreshed before the run so the provenance sidecar explicitly
records the adjusted-price policy. A provider-internal adjusted-price audit was
also run for the March 2024 SPY dividend window:

- Command: `quant-lab audit-adjusted-prices --symbol SPY --start 2024-03-01 --end 2024-04-15 --expected-dividend-date 2024-03-15 --out artifacts/research/spy_200_sma_long_cash/data_audit`
- Result: `pass`
- Rows compared: `30`
- Max adjusted close difference: `0.0`
- Expected dividend row found: `2024-03-15`

This audit compares yfinance's adjusted close behavior against yfinance's raw
`Adj Close` and action rows. It is useful evidence, but it is not a second-source
vendor reconciliation.

## Workflow Run

The workflow used the current default path:

```text
fetch data -> audit adjusted prices -> create strategy -> research plan ->
baseline -> data trust -> sweep -> train/test -> robustness -> evidence summary
-> canonical conclusion -> decision
```

Key artifacts:

- `artifacts/research/spy_200_sma_long_cash/research_plan.md`
- `artifacts/research/spy_200_sma_long_cash/data_audit/adjusted_price_audit.md`
- `artifacts/research/spy_200_sma_long_cash/baseline/report.md`
- `artifacts/research/spy_200_sma_long_cash/baseline/run_trust_report.md`
- `artifacts/research/spy_200_sma_long_cash/sweep_001/research.md`
- `artifacts/research/spy_200_sma_long_cash/sweep_001/sweep_guardrails.md`
- `artifacts/research/spy_200_sma_long_cash/train_test_001/research.md`
- `artifacts/research/spy_200_sma_long_cash/cost_sensitivity_001/cost_sensitivity_report.md`
- `artifacts/research/spy_200_sma_long_cash/date_sensitivity_001/date_sensitivity_report.md`
- `artifacts/research/spy_200_sma_long_cash/evidence_summary.md`
- `artifacts/research/spy_200_sma_long_cash/experiment_conclusion.md`
- `artifacts/research/spy_200_sma_long_cash/agent_context.md`

## Results

Baseline with `retail-liquid` costs:

- Strategy total return: `148.39%`
- Buy-and-hold total return: `302.73%`
- Excess total return: `-154.34%`
- Strategy CAGR: `8.65%`
- Buy-and-hold CAGR: `13.54%`
- Strategy Sharpe: `0.7807`
- Buy-and-hold Sharpe: `0.8032`
- Strategy max drawdown: `-20.37%`
- Buy-and-hold max drawdown: `-33.72%`
- Trades: `59`
- Data trust result: reproducible input file
- Worst trust warning: `none`

Small parameter sweep:

- Sweep size: `3` runs
- Lengths: `150`, `200`, `250`
- Best run: `run_002`
- Best length: `200`
- Best total return: `148.39%`
- Best excess total return: `-154.34%`
- Sweep guardrail warning: best run did not beat its benchmark on total return.

Train/test validation:

- Train end: `2020-12-31`
- Test start: `2021-01-01`
- Selection metric: `sharpe_ratio`
- Selected train run: `run_002`
- Selected length: `200`
- Test total return: `41.83%`
- Test excess total return: `-57.73%`
- Test max drawdown: `-20.37%`
- Test benchmark max drawdown: `-24.50%`

Cost sensitivity:

- No requested cost preset beat buy-and-hold.
- No-cost excess total return: `-139.24%`
- Retail-liquid excess total return: `-154.34%`
- Retail-conservative excess total return: `-168.57%`
- High-friction excess total return: `-200.78%`

Date sensitivity:

- No requested date window beat buy-and-hold.
- `2015-01-02` to `2019-12-31`: excess `-37.07%`
- `2020-01-01` to `2025-12-30`: excess `-45.74%`
- `2018-01-01` to `2022-12-31`: excess `-33.96%`

## Conclusion

The experiment was rejected.

The 200-day SMA long/cash strategy reduced drawdown versus buy-and-hold in the
full baseline, but the return sacrifice was too large for the stated
hypothesis. The baseline gave up `154.34%` total return versus buy-and-hold
after realistic costs, and every linked sweep, train/test, cost-sensitivity, and
date-sensitivity run had negative excess return.

Recorded decision:

- Outcome: `reject`
- Rationale: no linked run beat SPY buy-and-hold on excess return; best excess
  was still `-33.96%`, while realistic-cost baseline excess was `-154.34%`.
- Next action: stop this 200-day SPY long/cash branch unless the hypothesis is
  reformulated around drawdown control with explicit return-sacrifice limits.

## Interpretation

This strategy is not useless, but it does not answer the original question
favorably. It behaves like a drawdown-reduction overlay that pays for risk
reduction with substantial foregone upside. That can be a legitimate objective,
but it needs a different hypothesis and success criterion, such as maximum
acceptable return drag per unit of drawdown reduction.

Do not keep widening this branch with more SMA lengths just because drawdown
looks better. Future work should either stop here or explicitly test a revised
drawdown-control question.

## Workflow Lessons

- The default workflow is usable end to end, but still command-heavy.
- `experiment_conclusion.md` is the correct file to read first after the run.
- The tracked docs need this summary because generated artifacts are ignored.
- The adjusted-price audit was useful supporting evidence, but it still needs a
  true second-source option before claiming provider-independent correctness.
- The current conclusion system carried the decision forward into the
  experiment registry after `decide-experiment`.
