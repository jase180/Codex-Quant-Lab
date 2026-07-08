# Milestone 4: Better Validation And Realism

## Purpose

Reduce false confidence from unrealistic assumptions and weak input data.

The lab can now run, store, find, inspect, and compare experiments. Milestone 4
should make those experiments more trustworthy by adding guardrails around data
quality, cost assumptions, sample quality, and out-of-sample thinking.

## Current Starting Point

Already available:

- strict OHLCV shape validation,
- deterministic next-bar-open fills,
- simple commission and slippage model,
- buy-and-hold benchmark,
- run metadata,
- research index,
- list/inspect/compare CLI commands.

Original gaps:

- Data quality issues are not summarized for research runs.
- Cost assumptions are manually typed each time.
- Short samples and tiny trade counts are visible but not strongly flagged.
- All current sweeps are in-sample over one date range.
- Buy-and-hold is the only benchmark.

## User Stories

1. As a researcher, I can see data-quality warnings before trusting a run.
2. As a researcher, I can use named cost presets instead of remembering numeric
   commission and slippage assumptions.
3. As a researcher, I can quickly see when a result is based on too few trades
   or too short a sample.
4. As a researcher, I can separate exploratory parameter selection from a later
   test period.
5. As a learner, I can understand why a result should or should not be trusted.

## Non-Goals

Do not build these in this milestone:

- live trading,
- broker integration,
- intraday execution simulation,
- institutional-grade market data handling,
- advanced statistics,
- multi-asset portfolio logic,
- machine learning optimization.

This milestone should make the current daily single-symbol lab more honest, not
turn it into a production trading system.

## Deliverable 1: Data Quality Report

Status: delivered.

Goal: summarize basic input-data risks for every run and sweep.

Proposed artifact:

```text
data_quality.json
```

Proposed fields:

```json
{
  "row_count": 2765,
  "start": "2015-01-02",
  "end": "2025-12-30",
  "duplicate_dates": 0,
  "missing_ohlcv_values": 0,
  "zero_volume_rows": 0,
  "non_positive_price_rows": 0,
  "large_gap_warnings": [],
  "calendar_gap_warnings": [],
  "warnings": []
}
```

Implementation notes:

- Keep this separate from strict OHLCV validation.
- Strict validation should still reject unusable data.
- Data quality reporting should warn about suspicious-but-possibly-valid data.
- Save the artifact into every run directory.
- Add the path to `run_metadata.json`.
- Add key warnings to `report.md` if present.

Acceptance criteria:

- Every run writes `data_quality.json`. Delivered.
- Every sweep sub-run writes `data_quality.json`. Delivered.
- Tests cover clean data, zero volume, missing values, non-positive prices, and
  duplicate dates. Delivered.
- Docs explain that warnings are research prompts, not automatic proof of bad
  data. Delivered.

## Deliverable 2: Cost Presets

Status: delivered.

Goal: make cost assumptions reusable and less error-prone.

Proposed CLI:

```bash
quant-lab run \
  --cost-preset retail-liquid
```

Possible presets:

```text
none
retail-liquid
retail-conservative
high-friction
```

Proposed behavior:

- `none`: no commission, no slippage.
- `retail-liquid`: low commission/slippage for liquid ETFs.
- `retail-conservative`: higher slippage to stress test assumptions.
- `high-friction`: deliberately punitive assumption for sensitivity checks.

Implementation notes:

- Keep existing explicit flags.
- If a preset and explicit flags are both provided, explicit flags should
  override the preset.
- Record both the preset name and final numeric costs in `run_metadata.json`.
- Include cost preset in the research index.

Acceptance criteria:

- Run and sweep accept `--cost-preset`. Delivered.
- Metadata records preset and resolved values. Delivered.
- Tests cover preset defaults and explicit override behavior. Delivered.

## Deliverable 3: Sample And Trade Count Warnings

Status: delivered.

Goal: make weak evidence obvious in reports and inspection commands.

Warnings to add:

- short sample,
- too few trades,
- no completed exits,
- high drawdown relative to return,
- strategy did not trade.

Proposed location:

- `metrics.json` caveats or a new `research_warnings` field,
- `report.md`,
- `show-run` output.

Implementation notes:

- Start with simple thresholds.
- Keep thresholds documented and deterministic.
- Do not block runs; warn instead.

Acceptance criteria:

- Runs with zero trades show a warning. Delivered.
- Runs with very few trades show a warning. Delivered.
- Short samples show a warning. Delivered.
- Tests cover warning generation. Delivered.

## Deliverable 4: Train/Test Date Split

Status: delivered.

Goal: support basic out-of-sample thinking without adding optimization logic.

Proposed CLI:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --train-end 2020-12-31 \
  --test-start 2021-01-01 \
  --out artifacts/research/sma_split_001
```

First version:

- run the sweep on the train period,
- identify best train result by total return or Sharpe,
- rerun that selected variant on the test period,
- write separate train and test artifacts.

Implementation notes:

- Keep selection metric explicit with `--select-by`. Delivered.
- Avoid automatic over-optimization beyond selecting one row. Delivered.
- Record split dates in metadata and research summary. Delivered.
- Require non-overlapping split dates. Delivered.

Delivered output shape:

```text
artifacts/research/sma_split_001/
  research.md
  train_sweep/
    summary.csv
    run_001/
      run_metadata.json
  test_summary/
    summary.csv
  test_selected/
    run_metadata.json
```

Acceptance criteria:

- Sweep can produce train and test outputs. Delivered.
- Selected train parameters are saved. Delivered.
- Test run metadata records that it came from a train/test workflow. Delivered.
- Docs explain that this is a guardrail, not proof. Delivered.

## Deliverable 5: Benchmark Variants

Status: delivered.

Goal: compare strategies against more than one simple baseline.

Possible benchmarks:

- buy-and-hold,
- cash,
- equal-weight simple moving average exposure, if later useful.

Recommendation:

- Start with `cash` benchmark only if it clarifies reports. Delivered.
- Keep buy-and-hold as the default and primary benchmark. Delivered.

Acceptance criteria:

- Benchmark choice is recorded in metadata. Delivered.
- Reports and summaries name the benchmark clearly. Delivered.
- Existing buy-and-hold behavior remains default. Delivered.

## Suggested Build Order

1. `data_quality.json`
2. cost presets
3. sample and trade count warnings
4. train/test split
5. benchmark variants

Reasoning:

- Data quality and warnings improve every run immediately.
- Cost presets reduce user error.
- Train/test split is more invasive and should come after the reporting
  foundation is stronger.
- Benchmark variants are useful, but less urgent than knowing whether the data
  and sample are trustworthy.

## Design Principles

- Warn clearly before adding complexity.
- Keep every assumption visible in metadata.
- Prefer deterministic local artifacts over hidden state.
- Avoid pretending warnings are statistical proof.
- Preserve current default behavior unless a user opts into new assumptions.
- Add focused tests for every warning and every new artifact.

## Exit Criteria For Milestone 4

Milestone 4 is complete when:

- Runs and sweeps produce data-quality artifacts. Delivered.
- Cost presets are available and recorded. Delivered.
- Weak samples and tiny trade counts are called out. Delivered.
- A basic train/test sweep workflow exists. Delivered.
- Benchmark assumptions are explicit in outputs. Delivered.
- Docs explain how to use these guardrails without overclaiming. Delivered.

At that point, the lab should support a more skeptical workflow:

```text
run experiment -> inspect data quality -> apply realistic costs -> check sample warnings -> compare train/test evidence -> decide next experiment
```

## Delivered Milestone Summary

Milestone 4 added data-quality artifacts, named cost presets, research warning
artifacts, train/test sweep mode, and explicit benchmark selection. The lab now
has a more skeptical default workflow without adding live trading, intraday
execution, or multi-asset portfolio complexity.
