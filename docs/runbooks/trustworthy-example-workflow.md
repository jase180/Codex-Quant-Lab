# Trustworthy Example Workflow

This example shows one skeptical research path from hypothesis to decision.

The goal is not to prove a strategy is profitable. The goal is to create a
repeatable evidence trail that makes it harder to fool yourself.

The commands use QQQ and the built-in SMA crossover template. Adjust symbols,
dates, and output folders for your own research.

## 1. Create A Strategy

Start from a generated strategy so the JSON is valid before research begins:

```bash
quant-lab new-strategy \
  --template sma-crossover \
  --symbol QQQ \
  --strategy-id qqq_sma_crossover \
  --name "QQQ SMA Crossover" \
  --out data/strategies/qqq_sma_crossover.json
```

If the file already exists and you intentionally want to replace it, add
`--force`.

## 2. Fetch Data With Provenance

Fetch adjusted daily data:

```bash
quant-lab fetch \
  --symbol QQQ \
  --start 2015-01-01 \
  --end 2025-12-31 \
  --out data/cache
```

Expected files:

```text
data/cache/QQQ_2015-01-01_2025-12-31.csv
data/cache/QQQ_2015-01-01_2025-12-31.provenance.json
```

Open the provenance file before trusting the data. It records provider,
requested range, actual data range, row count, fetched timestamp, and file
fingerprint.

## 3. Create The Experiment

Write the hypothesis before looking at results:

```bash
quant-lab new-experiment \
  --title "QQQ SMA crossover trust check" \
  --hypothesis "A daily SMA crossover may reduce drawdown versus buy-and-hold, but may underperform during strong trends." \
  --tag QQQ \
  --tag sma \
  --strategy data/strategies/qqq_sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv
```

The command prints an id such as `EXP-001`. Use that id in later commands.

## 4. Run A Baseline

Run the starter strategy with explicit cost assumptions:

```bash
quant-lab run \
  --strategy data/strategies/qqq_sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --sizing percent-equity \
  --allocation 1.0 \
  --benchmark buy-and-hold \
  --cost-preset retail-liquid \
  --experiment-id EXP-001 \
  --note "Baseline before searching parameters." \
  --out artifacts/research/qqq_sma_trust/baseline
```

The run writes `run_metadata.json`, `data_quality.json`, charts, metrics, and a
markdown report. The metadata includes the CSV fingerprint and
`data.quality_severity`.

## 5. Verify The Baseline Input

Check that the current local CSV still matches the run metadata:

```bash
quant-lab verify-run \
  --metadata artifacts/research/qqq_sma_trust/baseline/run_metadata.json
```

If any field reports `mismatch`, treat the run as historical evidence tied to a
different local data file. Do not compare it casually with new runs until you
understand what changed.

## 6. Run A Small Parameter Sweep

Search a small grid. Keep the data, sizing, benchmark, and costs the same as
the baseline:

```bash
quant-lab sweep \
  --strategy data/strategies/qqq_sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --sizing percent-equity \
  --allocation 1.0 \
  --benchmark buy-and-hold \
  --cost-preset retail-liquid \
  --experiment-id EXP-001 \
  --note "Small parameter grid after baseline." \
  --out artifacts/research/qqq_sma_trust/sweep_001
```

Read `artifacts/research/qqq_sma_trust/sweep_001/research.md` before choosing a
winner. The parameter-stability label is a heuristic, not proof.

## 7. Run A Train/Test Check

If the sweep has a promising candidate, run a split test:

```bash
quant-lab sweep \
  --strategy data/strategies/qqq_sma_crossover.json \
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
  --out artifacts/research/qqq_sma_trust/train_test_001
```

Do not move the split date after seeing the result. If you want another split,
record that as another experiment or another clearly named validation run.

## 8. Summarize Evidence

Summarize all linked run evidence:

```bash
quant-lab summarize-experiment \
  --experiment-id EXP-001 \
  --index-path artifacts/research_index.jsonl
```

Look for both support and contradiction:

- strongest excess-return evidence,
- weakest excess-return evidence,
- validation run evidence,
- data-quality severity,
- trade count,
- benchmark comparison.

## 9. Draft A Decision

Ask the tool for a conservative draft:

```bash
quant-lab draft-decision \
  --experiment-id EXP-001 \
  --index-path artifacts/research_index.jsonl
```

The draft does not write anything. Edit the rationale before using it.

## 10. Record The Decision

Example conservative outcome:

```bash
quant-lab decide-experiment \
  --experiment-id EXP-001 \
  --outcome continue \
  --rationale "The sweep showed possible improvement, but validation evidence is not strong enough to accept the idea yet." \
  --supporting-run artifacts/research/qqq_sma_trust/sweep_001/run_004/run_metadata.json \
  --contradicting-run artifacts/research/qqq_sma_trust/train_test_001/test_selected/run_metadata.json \
  --next-action "Run walk-forward windows and test the same hypothesis on SPY." \
  --tag needs-walk-forward
```

Use:

- `accept` only when evidence survives stricter validation,
- `reject` when the evidence does not justify more research time,
- `continue` when the next action is still research.

## What This Example Proves

This workflow proves only that the research was recorded and checked in a
disciplined way. It does not prove a trading edge.

The conclusion should stay limited:

```text
The result is a local daily-data research observation for one symbol, one data
provider, one cost model, and one date range. It needs more validation before it
can be treated as anything stronger.
```
