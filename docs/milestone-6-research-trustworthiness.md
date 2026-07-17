# Milestone 6: Research Trustworthiness

## Purpose

Make Codex-Quant-Lab stricter about whether a research result deserves trust.

The lab already saves runs, summaries, experiment links, and decisions. That is
useful, but it also raises the standard: if a decision is recorded, the project
should make it easy to see what data, assumptions, and warnings the decision
rested on.

This milestone should reduce quiet failure modes:

- the CSV changed after a run,
- the data source is unclear,
- a result looks good but has weak evidence,
- a decision ignores contradictory validation evidence,
- a future user cannot reproduce what happened.

## Current Starting Point

Already available:

- run metadata with strategy, data range, sizing, costs, benchmark, command, and
  artifact paths,
- data-quality JSON artifacts,
- research warnings for weak samples and tiny trade counts,
- run index rows,
- experiment records,
- automatic run-to-experiment linking,
- evidence summaries,
- conservative decision drafts,
- structured experiment decisions.

Main gaps:

- Run metadata records data range and row count, but not a fingerprint of the
  actual input file.
- Fetch/cache outputs do not record enough source/provenance detail.
- Data-quality findings are inspectable, but not clearly severity-ranked.
- There is no command to check whether an old run still matches the current
  local CSV.
- The docs describe workflows, but do not yet include a compact end-to-end
  trustworthy research example.

## User Stories

1. As a researcher, I can tell whether the CSV used by a run has changed.
2. As a researcher, I can see where a dataset came from and when it was fetched.
3. As a researcher, I can quickly identify severe data-quality issues.
4. As a researcher, I can verify an old run before trusting its conclusion.
5. As a learner, I can follow one honest example from hypothesis to decision.

## Non-Goals

Do not build these in this milestone:

- live trading,
- broker integration,
- intraday market data,
- a database server,
- full data-vendor abstraction,
- survivorship-bias-free equity universes,
- portfolio optimization.

Those are real topics, but they would expand the project before the current
single-symbol daily workflow is trustworthy enough.

## Deliverable 1: Dataset Fingerprints

Status: delivered.

Goal: make every run metadata file identify the exact input CSV content.

Proposed metadata fields:

```json
{
  "data": {
    "path": "data/cache/QQQ_2015-01-01_2025-12-31.csv",
    "row_count": 2768,
    "start": "2015-01-02",
    "end": "2025-12-31",
    "file_sha256": "...",
    "file_size_bytes": 123456,
    "modified_at_utc": "2026-07-15T12:00:00Z"
  }
}
```

Implementation notes:

- Hash the raw CSV file bytes, not the loaded pandas frame. Delivered.
- Keep the existing metadata schema version unless the change remains backward
  compatible for readers. Delivered.
- Store file size and modified time as helpful context, but treat SHA-256 as
  the reliable identity. Delivered.
- Add tests around deterministic hashing and changed-file behavior. Delivered.

Acceptance criteria:

- `run_metadata.json` includes the source file hash for `run`, `sweep`,
  train/test, and walk-forward runs. Delivered through shared metadata writing.
- Tests prove the same file produces the same fingerprint and changed content
  changes the fingerprint. Delivered.
- README documents why the fingerprint exists. Delivered.

## Deliverable 2: Dataset Provenance For Fetches

Status: planned.

Goal: make cached market data explain where it came from.

Proposed output beside fetched CSV:

```text
data/cache/QQQ_2015-01-01_2025-12-31.csv
data/cache/QQQ_2015-01-01_2025-12-31.provenance.json
```

Suggested provenance fields:

- symbol,
- requested start/end,
- provider,
- interval,
- fetched_at_utc,
- output CSV path,
- row count,
- data start/end,
- file hash.

Acceptance criteria:

- `quant-lab fetch` writes provenance JSON beside the CSV.
- Provenance JSON includes provider and timestamp.
- Tests cover provenance serialization without requiring network access.

## Deliverable 3: Data-Quality Severity Levels

Status: planned.

Goal: make data-quality output easier to act on.

First version:

- classify findings as `info`, `warning`, or `critical`,
- include a top-level worst severity,
- show worst severity in reports and run metadata,
- keep raw finding details for auditability.

Acceptance criteria:

- Missing required OHLCV values are at least `warning`.
- Non-positive prices are `critical`.
- Duplicate dates are at least `warning`.
- Reports include a concise severity line.

## Deliverable 4: Reproducibility Check Command

Status: planned.

Goal: verify whether a saved run still matches the current local input data.

Proposed CLI:

```bash
quant-lab verify-run \
  --metadata artifacts/research/qqq_sma/run_metadata.json
```

Expected output:

```text
Run verification
metadata: artifacts/research/qqq_sma/run_metadata.json
data_path: data/cache/QQQ_2015-01-01_2025-12-31.csv
file_sha256: match
row_count: match
date_range: match
result: reproducible input file
```

Acceptance criteria:

- The command reports match/mismatch for file hash, row count, and date range.
- Missing data files produce a clear failure message.
- Tests cover matching, changed, and missing data file cases.

## Deliverable 5: Trustworthy Example Workflow

Status: planned.

Goal: document one complete skeptical research loop.

The example should include:

- experiment creation,
- baseline run,
- sweep,
- train/test or walk-forward check,
- evidence summary,
- decision draft,
- final structured decision.

Acceptance criteria:

- A learner can copy the command sequence using sample data.
- The example explains why the conclusion is limited.
- The example does not imply profitability or trading readiness.

## Suggested Build Order

1. dataset fingerprints,
2. fetch provenance,
3. data-quality severity levels,
4. `verify-run`,
5. trustworthy example workflow.

Reasoning:

- Fingerprints are the smallest high-value trust improvement.
- Fetch provenance builds on fingerprints and clarifies source assumptions.
- Severity levels make existing data-quality output more useful.
- `verify-run` becomes much more valuable once fingerprints exist.
- The example workflow should come after the commands are stable enough to
  document honestly.
