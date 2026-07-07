# Milestone 3: Research Usability

## Purpose

Make completed research runs easier to inspect, compare, and explain from the
CLI.

Milestones 1 and 2 made the lab reproducible: runs write artifacts, metadata,
charts, and a searchable JSONL index. Milestone 3 should make those saved
artifacts pleasant to use without manually opening many files.

## Current Starting Point

Already available:

- `quant-lab run`
- `quant-lab sweep`
- `quant-lab list-runs`
- per-run `run_metadata.json`
- per-run `metrics.json`
- per-run `report.md`
- per-run `trades.csv`
- per-run charts
- append-only `artifacts/research_index.jsonl`

Main gap:

- The user can find runs, but cannot quickly inspect or compare selected runs
  from the CLI.

## User Stories

1. As a researcher, I can list recent or high-performing runs and choose one to
   inspect.
2. As a researcher, I can print one run's important metadata, metrics, costs,
   benchmark comparison, and artifact paths.
3. As a researcher, I can compare two or more runs in a compact table.
4. As a learner, I can understand what the command is showing without needing
   to know the full JSON structure.

## Non-Goals

Do not build these in this milestone:

- an interactive dashboard,
- a database,
- a web app,
- multi-asset portfolio research,
- new strategy rules,
- statistical significance tooling.

The milestone should stay focused on making existing artifacts useful.

## Deliverable 1: `quant-lab show-run`

Status: first priority.

Goal: inspect one run from either a metadata path or an index row.

Proposed commands:

```bash
quant-lab show-run --metadata artifacts/qqq_run/run_metadata.json
```

```bash
quant-lab show-run --index-path artifacts/research_index.jsonl --output-dir artifacts/qqq_run
```

First version can require `--metadata`. Index lookup can come next if needed.

Output should include:

- strategy id and name,
- symbol and timeframe,
- data start/end,
- initial cash,
- sizing mode,
- commission and slippage,
- total return,
- benchmark total return,
- excess total return,
- max drawdown,
- Sharpe ratio,
- trade count,
- artifact paths.

Implementation notes:

- Read `run_metadata.json`.
- Read `metrics.json` through the artifact path stored in metadata.
- Read index row only if the command supports index lookup.
- Keep formatting plain text and table-like.
- Do not mutate artifacts.

Acceptance criteria:

- A valid metadata path prints a useful summary.
- Missing metadata path gives an explicit error.
- Missing metrics artifact gives an explicit error.
- Tests cover normal output and missing-file behavior.

## Deliverable 2: `quant-lab compare-runs`

Status: second priority.

Goal: compare two or more runs side by side.

Proposed command:

```bash
quant-lab compare-runs \
  --metadata artifacts/run_a/run_metadata.json \
  --metadata artifacts/run_b/run_metadata.json
```

Output columns:

```text
run
symbol
strategy
total_return
benchmark_total_return
excess_total_return
max_drawdown
sharpe_ratio
trade_count
commission_rate
slippage_bps
output_dir
```

Implementation notes:

- Build this on top of the same reader/formatter helpers used by `show-run`.
- Keep the first version metadata-path based.
- Index-based selection can come later.

Acceptance criteria:

- Two or more metadata paths produce one comparison table.
- Missing files fail clearly.
- Tests cover ordering and key metric formatting.

## Deliverable 3: `list-runs` Improvements

Status: third priority.

Goal: make the run registry more useful without turning it into a dashboard.

Likely additions:

- `--strategy-id`
- `--run-type`
- `--since`
- `--csv`
- `--columns`

Suggested order:

1. Add `--strategy-id`.
2. Add `--csv` export.
3. Add `--columns` only if the default table becomes noisy.

Acceptance criteria:

- Filtering remains predictable.
- Existing `list-runs` output remains stable unless flags request a different
  format.
- Tests cover every new filter or output format.

## Deliverable 4: Workflow Documentation

Status: fourth priority.

Goal: document one complete research loop.

Suggested doc:

```text
docs/research-workflow.md
```

It should show:

1. fetch data,
2. run baseline,
3. run sweep,
4. list runs,
5. show one run,
6. compare runs,
7. write a skeptic-pass conclusion.

Acceptance criteria:

- A future user can follow the doc from an empty artifact folder to a completed
  research summary.

## Suggested Build Order

1. `show-run --metadata`
2. `compare-runs --metadata`
3. `list-runs --strategy-id`
4. `list-runs --csv`
5. `docs/research-workflow.md`

## Design Principles

- Prefer local files and simple formats.
- Keep commands deterministic.
- Make errors explicit.
- Do not hide assumptions.
- Keep outputs readable in a terminal.
- Add tests for every CLI behavior.
- Update README/module docs when commands change.

## Exit Criteria For Milestone 3

Milestone 3 is complete when:

- `list-runs` finds candidate runs.
- `show-run` explains one selected run.
- `compare-runs` compares selected runs.
- docs show the complete research workflow.
- all commands are covered by focused tests.

At that point, the lab should support a full local workflow:

```text
run experiment -> save artifacts -> find run -> inspect run -> compare runs -> decide next experiment
```
