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

Main gaps:

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

Status: first priority.

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

- Every run writes `data_quality.json`.
- Every sweep sub-run writes `data_quality.json`.
- Tests cover clean data, zero volume, missing values, non-positive prices, and
  duplicate dates.
- Docs explain that warnings are research prompts, not automatic proof of bad
  data.

## Deliverable 2: Cost Presets

Status: second priority.

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

- Run and sweep accept `--cost-preset`.
- Metadata records preset and resolved values.
- Tests cover preset defaults and explicit override behavior.

## Deliverable 3: Sample And Trade Count Warnings

Status: third priority.

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

- Runs with zero trades show a warning.
- Runs with very few trades show a warning.
- Short samples show a warning.
- Tests cover warning generation.

## Deliverable 4: Train/Test Date Split

Status: fourth priority.

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

- Keep selection metric explicit with `--select-by`.
- Avoid automatic over-optimization beyond selecting one row.
- Record split dates in metadata and research summary.

Acceptance criteria:

- Sweep can produce train and test outputs.
- Selected train parameters are saved.
- Test run metadata records that it came from a train/test workflow.
- Docs explain that this is a guardrail, not proof.

## Deliverable 5: Benchmark Variants

Status: fifth priority.

Goal: compare strategies against more than one simple baseline.

Possible benchmarks:

- buy-and-hold,
- cash,
- equal-weight simple moving average exposure, if later useful.

Recommendation:

- Start with `cash` benchmark only if it clarifies reports.
- Keep buy-and-hold as the default and primary benchmark.

Acceptance criteria:

- Benchmark choice is recorded in metadata.
- Reports and summaries name the benchmark clearly.
- Existing buy-and-hold behavior remains default.

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

- Runs and sweeps produce data-quality artifacts.
- Cost presets are available and recorded.
- Weak samples and tiny trade counts are called out.
- A basic train/test sweep workflow exists.
- Benchmark assumptions are explicit in outputs.
- Docs explain how to use these guardrails without overclaiming.

At that point, the lab should support a more skeptical workflow:

```text
run experiment -> inspect data quality -> apply realistic costs -> check sample warnings -> compare train/test evidence -> decide next experiment
```

## Near-Term Recommendation

Build `data_quality.json` first.

Reason: better data warnings improve every future experiment and are less risky
than changing strategy execution or sweep behavior.
