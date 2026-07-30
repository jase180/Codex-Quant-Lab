# Getting Running Locally

This guide is the shortest path from a fresh checkout to a local run that writes
real artifacts. It is intentionally practical: first prove the environment, then
run the default workflow on tracked sample data, then move to real market data.

## 1. Install The Project

From the repo root, create a virtual environment and install the package in
editable mode.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -e .
```

If `py` is not available on your machine, use the full path to an installed
Python executable instead.

WSL, Linux, or macOS:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

The installed console command is `quant-lab`. If the shell cannot find it, use
the module form instead:

```bash
python -m quant_lab.cli --help
```

## 2. Prove The Environment

Run the doctor command first:

Windows PowerShell:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli doctor
```

WSL, Linux, or macOS:

```bash
quant-lab doctor
```

The doctor command checks Python, core dependencies, required project files,
artifact write access, and the local data cache. An empty data cache is only a
warning because a fresh clone should still be able to run the offline smoke
workflow.

Run the offline smoke workflow:

Windows PowerShell:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli smoke-test --force
```

WSL, Linux, or macOS:

```bash
quant-lab smoke-test --force
```

The smoke test creates a sample research plan, runs one baseline against the
tracked sample CSV, refreshes a session manifest, and prints `read_first` plus
the next recommended command.

To also verify the deterministic local-agent dry-run path, add
`--agent-cycle`:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli smoke-test --force --agent-cycle
```

This writes the same smoke artifacts plus an `agent_cycle` folder. It does not
execute the proposed command.

Build the local-agent context bundle from that manifest:

Windows PowerShell:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli agent context `
  --manifest artifacts\smoke-test\session_manifest.json
```

WSL, Linux, or macOS:

```bash
quant-lab agent context \
  --manifest artifacts/smoke-test/session_manifest.json
```

Write the deterministic advisor recommendation:

Windows PowerShell:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli agent suggest `
  --manifest artifacts\smoke-test\session_manifest.json
```

WSL, Linux, or macOS:

```bash
quant-lab agent suggest \
  --manifest artifacts/smoke-test/session_manifest.json
```

Run the unit tests before trusting any research output:

Windows PowerShell:

```powershell
$env:MPLCONFIGDIR='artifacts/matplotlib-cache'
.\.venv-win\Scripts\python.exe -m unittest discover -s tests
```

WSL, Linux, or macOS:

```bash
MPLCONFIGDIR=artifacts/matplotlib-cache python -m unittest discover -s tests
```

`MPLCONFIGDIR` keeps matplotlib cache files inside the ignored `artifacts/`
directory instead of a user-level cache path. That makes test runs easier for
Codex and other local agents to repeat.

## 3. Run The Offline Smoke Workflow Manually

The manual path below is the expanded version of `quant-lab smoke-test`. It
needs no internet and uses the tracked `data/sample_ohlcv.csv` file, so it is
good for checking that commands, package imports, charts, reports, and session
manifests work.

Create a guided research plan:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli research-plan init `
  --title "Sample smoke workflow" `
  --hypothesis "The tracked sample data can prove the local workflow is installed and producing artifacts." `
  --strategy data\strategies\sma_crossover.json `
  --data data\sample_ohlcv.csv `
  --symbol QQQ `
  --cost-preset retail-liquid `
  --out artifacts\getting_started_smoke_plan `
  --experiments-path artifacts\getting_started_smoke_plan\experiments.jsonl `
  --index-path artifacts\getting_started_smoke_plan\research_index.jsonl
```

Then run the printed `next_command`. In module form, the baseline command is:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli run `
  --strategy data\strategies\sma_crossover.json `
  --data data\sample_ohlcv.csv `
  --out artifacts\getting_started_smoke_plan\baseline `
  --initial-cash 100000.0 `
  --quantity 1 `
  --sizing percent-equity `
  --allocation 1.0 `
  --benchmark buy-and-hold `
  --cost-preset retail-liquid `
  --experiments-path artifacts\getting_started_smoke_plan\experiments.jsonl `
  --experiment-id EXP-001 `
  --index-path artifacts\getting_started_smoke_plan\research_index.jsonl `
  --note "Baseline for research plan: The tracked sample data can prove the local workflow is installed and producing artifacts."
```

Refresh the session manifest:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli session refresh `
  --plan artifacts\getting_started_smoke_plan\research_plan.json
```

Inspect the current state:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli session status `
  --manifest artifacts\getting_started_smoke_plan\session_manifest.json
```

Expected result: the run completes, writes a baseline report, and the session
status recommends a data-trust report next. The sample CSV only has a few rows,
so this is not research evidence. It is a wiring check.

## 4. Read The Output

For the smoke workflow, start here:

```text
artifacts/getting_started_smoke_plan/session_manifest.md
artifacts/getting_started_smoke_plan/baseline/report.md
artifacts/getting_started_smoke_plan/baseline/run_metadata.json
```

The manifest is the best file for Codex or a local agent to read first because
it records the plan, current status, current recommendation, and missing
artifacts.

## 5. Move To Real Data

After the smoke path works, fetch real market data:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli fetch `
  --symbol QQQ `
  --start 2015-01-01 `
  --end 2025-12-31 `
  --out data\cache
```

Then create a real guided plan:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli research-plan init `
  --title "QQQ SMA crossover trust check" `
  --hypothesis "A daily SMA crossover may reduce drawdown versus buy-and-hold." `
  --strategy data\strategies\sma_crossover.json `
  --data data\cache\QQQ_2015-01-01_2025-12-31.csv `
  --symbol QQQ `
  --cost-preset retail-liquid `
  --out artifacts\research\qqq_sma_trust
```

From there, run:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli research-plan next `
  --plan artifacts\research\qqq_sma_trust\research_plan.json
```

and follow the recommended command one step at a time.

## Refactor Gate

No refactor is required before using this workflow. The known cleanup candidates
are still real, but they are not blockers:

- `src/quant_lab/cli.py` is large because it owns many subcommands.
- `src/quant_lab/session_manifest.py` could eventually split model, update, and
  formatting code.
- `src/quant_lab/cli_session.py` could move more non-CLI logic into a service
  module.

The next useful work is to make the default workflow easier to run and inspect,
then refactor only where the workflow starts fighting us.
