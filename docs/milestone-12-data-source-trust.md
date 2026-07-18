# Milestone 12: Data Source Trust

## Status

Planned.

## Goal

Make it easier to answer one basic research question before trusting a run:

```text
Can I explain exactly what data this result used, where that data came from,
whether the local file still matches, and whether the input has obvious quality
problems?
```

The lab already records CSV fingerprints, fetch provenance, and per-run data
quality. Milestone 12 should turn those raw artifacts into a clearer workflow.
The goal is not to add another data vendor or a heavy database. The goal is to
make local research harder to fool yourself with.

## Current Starting Point

Working capabilities:

- `quant-lab fetch` writes normalized OHLCV CSV files.
- Fetches write `*.provenance.json` beside the CSV.
- Single-strategy run metadata stores the input data fingerprint.
- Portfolio metadata stores per-symbol data fingerprints.
- Run reports include data-quality sections.
- `quant-lab verify-run-data` can compare a run metadata fingerprint with the
  current local CSV.
- Portfolio runs record per-symbol data quality, aligned rows, dropped rows, and
  benchmark data inputs.

Main gaps:

- Data provenance is saved, but not easy to inspect from the CLI.
- A user has to know which files to open to review source, timestamp, row count,
  actual date range, and fingerprint.
- Portfolio runs have multiple data inputs, but no single data-trust report that
  checks all symbols at once.
- Research workflow docs mention trust checks, but they are not yet a first-class
  repeated step like running or summarizing.

## Non-Goals

- No paid data-vendor integration.
- No intraday data.
- No automatic provider reconciliation.
- No database or remote cache service.
- No live data refresh during backtests.
- No claim that yfinance data is authoritative.
- No statistical data-cleaning system.

This milestone stays local, explicit, and inspectable.

## Deliverables

### 1. Data Provenance Inspection

Status: delivered.

Add a command that prints a concise summary for a cached data CSV and its
optional provenance file.

Possible command:

```bash
quant-lab show-data-source \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv
```

Acceptance criteria:

- Prints CSV path, row count, first date, last date, and fingerprint prefix.
- Prints provenance provider, requested start/end, actual start/end,
  fetched-at timestamp, and provenance schema version when available.
- Warns clearly when the provenance file is missing.
- Fails clearly when the CSV file is missing or malformed.
- Tests cover present provenance, missing provenance, and missing CSV.

### 2. Single-Run Trust Report

Status: delivered.

Add a command that turns existing run metadata into a short Markdown trust
report.

Possible command:

```bash
quant-lab summarize-run-trust \
  --metadata artifacts/research/qqq_sma/baseline/run_metadata.json
```

Acceptance criteria:

- Reads `run_metadata.json` and related artifact paths.
- Verifies whether the current local CSV still matches the saved fingerprint.
- Includes data quality severity and findings.
- Includes source/provenance details when a sidecar provenance file exists.
- Writes `run_trust_report.md` beside the metadata file by default.
- Prints a concise terminal result with the report path and worst warning.

### 3. Portfolio Data Trust Report

Status: delivered.

Add the same trust workflow for portfolio metadata, where one result can depend
on several symbol CSVs plus benchmark data.

Possible command:

```bash
quant-lab summarize-portfolio-data-trust \
  --metadata artifacts/research/qqq_spy_tlt/baseline/portfolio_metadata.json
```

Acceptance criteria:

- Reads `portfolio_metadata.json`.
- Checks every symbol data file against the saved fingerprint.
- Checks benchmark data when benchmark metadata is present.
- Reports per-symbol quality severity, aligned rows, dropped rows, and
  fingerprint status.
- Writes `portfolio_data_trust_report.md` beside the metadata file by default.
- Warns if any symbol is missing, changed, thin, or has severe data quality.

### 4. Research Workflow Integration

Status: planned.

Make data trust a visible next step in the guided workflow docs and plan
recommendations.

Acceptance criteria:

- Update README and workflow docs with copyable trust-check commands.
- `research-plan next` should recommend a run trust report after a baseline run
  exists and before over-interpreting a sweep.
- `portfolio-plan next` should recommend a portfolio data trust report after a
  baseline portfolio run exists.
- The recommendation should be conservative: trust checks explain inputs; they
  do not certify that a strategy works.

### 5. Data Cache Inventory

Status: planned.

Add a small local inventory command for cached market-data files.

Possible command:

```bash
quant-lab list-data-cache --data-dir data/cache
```

Acceptance criteria:

- Lists cached CSV files with symbol, row count, date range, fingerprint prefix,
  and provenance presence.
- Flags duplicate-looking files for the same symbol/date range.
- Flags files missing provenance sidecars.
- Does not fetch or mutate data.
- Tests use temporary local CSV fixtures only.

## Build Order

1. Data provenance inspection.
2. Single-run trust report.
3. Portfolio data trust report.
4. Guided workflow recommendations.
5. Data cache inventory.
6. README and workflow docs updates as each command becomes real.

## Design Notes

- Keep trust reports derived from saved artifacts. Do not rerun backtests.
- Prefer small JSON/Markdown outputs over hidden state.
- Reuse existing fingerprint and data-quality code instead of making a second
  validation system.
- Treat missing provenance as a warning, not a fatal error, because older local
  CSV files may predate provenance sidecars.
- Treat changed or missing CSV fingerprints as high-severity, because the saved
  result can no longer be reproduced from the local input file.
- For portfolio reports, show every symbol separately. A portfolio result is only
  as explainable as its weakest input.

## Exit Criteria

Milestone 12 is done when a user can inspect cached data, generate trust reports
for strategy and portfolio runs, and see data-trust checks appear naturally in
the guided research workflow. The lab still will not prove market data is
perfect, but it should make stale, missing, changed, or weak data hard to ignore.
