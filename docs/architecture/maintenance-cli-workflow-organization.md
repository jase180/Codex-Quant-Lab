# Maintenance: CLI And Workflow Organization

Status: complete.

## Purpose

Prepare the codebase for the next product milestone without changing user-facing
behavior.

The lab had become useful enough that several modules were carrying too many
responsibilities. Before adding portfolio or multi-asset research, the CLI and
run workflow plumbing needed clearer boundaries.

## What Changed

- CLI command handlers were split out of `quant_lab.cli` into command-focused
  modules.
- CLI parser registration was grouped by command family.
- Run inspection commands moved into their own CLI handler module.
- Data commands moved into their own CLI handler module.
- Experiment commands moved into their own CLI handler module.
- Run commands moved into their own CLI handler module.
- Sweep setup was centralized so regular, train/test, and walk-forward sweeps
  share strategy loading, parameter variant building, data loading, output
  directory setup, and research-note handling.
- Train-sweep selection was centralized so train/test and walk-forward workflows
  use the same train variant execution and best-run selection path.
- Selected test-run execution was centralized across train/test and
  walk-forward workflows.
- Sweep grid execution was centralized so regular sweeps and train sweeps use
  the same variant-running loop.
- Run record persistence was centralized so single runs and sweep runs share
  metadata saving, experiment linking, and research-index appending.
- Backtest execution and artifact saving were centralized behind a shared
  helper used by both single runs and sweep variants.

## Why It Matters

This work reduces the number of places future changes need to touch.

For example, a future metadata field now belongs in the shared run persistence
path instead of separate single-run and sweep-run branches. A future sweep
workflow can reuse the same setup and variant execution helpers instead of
copying artifact-writing logic.

The important constraint was behavior preservation: command names, flags,
artifact paths, metadata shape, run index rows, and test expectations were kept
stable.

## Verification

Each slice was committed after focused tests and the full test suite passed.

The final state was verified with:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

At completion, the suite covered 135 tests.

## Resulting Code Shape

- `quant_lab.cli` now mostly defines parser wiring.
- `quant_lab.cli_runs`, `quant_lab.cli_data`, `quant_lab.cli_experiments`, and
  `quant_lab.cli_run_inspection` own command handlers.
- `quant_lab.sweep_workflows` still owns sweep orchestration, but shared setup,
  train selection, selected test execution, and grid execution are extracted.
- `quant_lab.run_artifacts` owns shared execution, artifact writing, metadata
  persistence, experiment linking, and index appending.

## Follow-Up

The codebase is ready to pivot back to product work.

Recommended next product direction: a guided research-question workflow that
helps a user move from hypothesis to baseline run, sweep, validation check,
evidence summary, and decision.
