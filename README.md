# Codex-Quant-Lab

Codex-Quant-Lab is a small Python quant research lab for testing simple trading
ideas against daily OHLCV market data.

The current project is intentionally modest: it is not a production trading
system, and it is not trying to predict markets. It is a learning and research
tool that makes backtest assumptions visible.

## Default Workflow

Start with one research question and one strategy. The default path is:

```text
strategy -> baseline -> trust check -> sweep -> train/test -> robustness -> conclusion -> decision
```

If you want help choosing the next research idea before creating executable
strategy JSON, use the conceptual strategy catalog:

```bash
quant-lab ideas suggest
```

This reads `data/strategy_catalog/*.json` and prior
`artifacts/research/**/experiment_conclusion.json` files, registry decisions,
and tracked experiment handoffs, excludes matching `do_not_repeat` or rejected
decision guidance, and prints one proposed hypothesis, success criteria, and a
draft experiment config. It does not create executable strategy JSON; convert the
chosen idea only after human approval.

The catalog is intentionally broader than the executable strategy folder. It now
contains at least 30 canonical variants, but only variants marked executable
should be promoted into runnable strategy or portfolio files without adding
engine support first.

Use `experiment run-default` when you want the lab to run the normal
single-strategy workflow for you while still writing every underlying artifact:

```bash
quant-lab experiment run-default \
  --title "QQQ SMA crossover trust check" \
  --hypothesis "A daily SMA crossover may reduce drawdown versus buy-and-hold." \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --symbol QQQ \
  --cost-preset retail-liquid \
  --intended-benefit "lower drawdown with acceptable return retention" \
  --primary-metric max_drawdown \
  --minimum-acceptable-performance "Retain at least 80% of benchmark CAGR and reduce max drawdown by at least 25% relative." \
  --tradeoff "May underperform buy-and-hold total return during strong bull markets." \
  --success-criterion '{"name":"return_retention","metric":"cagr","comparison":"strategy_vs_benchmark_ratio","operator":">=","threshold":0.8}' \
  --success-criterion '{"name":"drawdown_reduction","metric":"max_drawdown","comparison":"relative_reduction_vs_benchmark","operator":">=","threshold":0.25}' \
  --param sma_20.inputs.length=10,20,30 \
  --param sma_50.inputs.length=50,100,150 \
  --train-end 2020-12-31 \
  --test-start 2021-01-01 \
  --date-window 2015-01-02,2019-12-31 \
  --date-window 2020-01-01,2025-12-30 \
  --out artifacts/research/qqq_sma_trust
```

The command creates or reuses an experiment, runs the baseline, writes the
run-trust report, runs the sweep and train/test validation, runs cost and date
sensitivity, runs benchmark sensitivity, writes `evidence_summary.md`, writes
`experiment_conclusion.md`, and records a conservative registry decision by
default. Detailed child command output is captured in
`default_workflow_summary.md` instead of printed to the terminal. Read this file
first:

```text
artifacts/research/qqq_sma_trust/experiment_conclusion.md
```

Every conclusion separates two questions:

- `Research-system status`: did the repo measure the experiment honestly and
  reproducibly?
- `Strategy-hypothesis status`: did the strategy meet the prespecified
  investment objective?

A strategy can be rejected while the research system is `valid`. That is a good
negative result, not a repo failure.

Use the guided workflow when you want the lab to create the workspace and
recommend one command at a time instead of executing the full default workflow:

```bash
quant-lab research-plan init \
  --title "QQQ SMA crossover trust check" \
  --hypothesis "A daily SMA crossover may reduce drawdown versus buy-and-hold." \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --symbol QQQ \
  --cost-preset retail-liquid \
  --out artifacts/research/qqq_sma_trust
```

After each major step, ask:

```bash
quant-lab research-plan next \
  --plan artifacts/research/qqq_sma_trust/research_plan.json
```

If you are returning to an experiment, orient from the session manifest first:

```text
artifacts/research/<experiment>/session_manifest.md
```

Then read the research conclusion:

```text
artifacts/research/<experiment>/experiment_conclusion.md
```

If the manifest is missing or stale, rebuild it from the plan:

```bash
quant-lab session refresh \
  --plan artifacts/research/<experiment>/research_plan.json
```

If you are using Codex or a local agent to continue a cycle, have it read these
first:

```text
artifacts/research/<experiment>/session_manifest.json
artifacts/research/<experiment>/experiment_conclusion.json
```

For command-oriented docs, start with the [runbook index](docs/runbooks/runbooks.md).
It points to setup, the default research workflow, local-agent dry runs, and
portfolio workflows.

For the full walkthrough, see [docs/runbooks/research-workflow.md](docs/runbooks/research-workflow.md).
For a copyable skeptical example, see
[docs/runbooks/trustworthy-example-workflow.md](docs/runbooks/trustworthy-example-workflow.md).

## Report Hierarchy

The lab writes many files, but they should not all compete for attention.

Read in this order:

1. Workflow orientation:
   `session_manifest.md`
2. Main conclusion:
   `experiment_conclusion.md`
3. Supporting interpretation:
   `evidence_summary.md`, robustness reports, data-trust reports, portfolio
   summaries
4. Raw audit files:
   `run_metadata.json`, `portfolio_metadata.json`, `metrics.json`,
   `trades.csv`, `equity_curve.csv`, charts, research index rows

Raw files stay available so results are auditable. The manifest exists so a
human, future Codex session, or local agent can find the current files and
warnings quickly. The conclusion exists so they do not need to reread every raw
artifact before deciding what happened.

## What Works Today

- Fetch daily market data with `yfinance`.
- Cache normalized OHLCV CSV files locally.
- Define rule-based strategies in strict JSON.
- Read a conceptual strategy catalog before generating executable strategy JSON.
- Suggest one next research idea with `quant-lab ideas suggest`, using prior
  conclusions and `do_not_repeat` constraints.
- Create valid starter strategy JSON from built-in templates.
- Create valid starter portfolio JSON from built-in templates.
- Execute SMA, EMA, RSI, rolling-high, and rolling-low based long-only strategies.
- Run one backtest from the CLI.
- Run parameter sweeps from the CLI.
- Read sweep research summaries with top-run and parameter-stability context.
- Run a train/test parameter sweep that selects on the train period and reruns
  only the selected variant on the later test period.
- Run explicit walk-forward windows for repeated train/test checks.
- Run simple static-weight multi-symbol portfolio backtests.
- Plan dry-run batches of portfolio candidate runs before executing them.
- Track research hypotheses in a local experiment registry.
- Save reports, metrics, equity curves, drawdown charts, trades, strategy copies,
  and sweep summaries.
- Save optional research notes beside run and sweep artifacts.
- Write data-quality summaries for run inputs.
- Compare strategy results with explicit benchmarks. Buy-and-hold is the
  default, and cash is available as a flat baseline.
- Write canonical experiment conclusions for humans and local agents.
- Define and refresh session manifest artifacts that orient future
  workflow-resume commands around the canonical conclusion.
- Create a human-gated local-agent cycle dry run that writes context,
  recommendation, and proposed-command artifacts without executing commands.
- Check local setup and dependency health with `quant-lab doctor`.
- Run an offline end-to-end wiring check with `quant-lab smoke-test`.
- Include deterministic local-agent dry-run verification in the smoke workflow
  with `quant-lab smoke-test --agent-cycle`.
- Follow a written research protocol in [AUTORESEARCH.md](AUTORESEARCH.md).

## Project Map

```text
data/
  sample_ohlcv.csv              Small sample dataset.
  portfolios/                   Example portfolio JSON files.
  strategies/                   Example strategy JSON files.
docs/
  README.md                     Documentation index by task and topic.
  runbooks/                     Setup, default workflow, and command runbooks.
  experiments/                  Tracked SPY experiment and audit handoffs.
  architecture/                 Strategy schema, audits, agent design, roadmap.
  milestones/                   Historical milestone plans and reviews.
  portfolio/                    Portfolio-specific workflow docs.
src/
  backtester_core/              Backtest engine, portfolio, execution, data validation.
  quant_lab/                    Strategy schema, executable rules, CLI, data fetch.
  metrics_reporting/            Metrics, markdown reports, artifact persistence.
tests/                          Unit and CLI tests.
artifacts/                      Ignored local run outputs.
data/cache/                     Ignored local market-data cache.
```

Detailed docs are organized by task in [docs/README.md](docs/README.md).
Module-level notes live in [src/backtester_core/README.md](src/backtester_core/README.md),
[src/quant_lab/README.md](src/quant_lab/README.md), and
[src/metrics_reporting/README.md](src/metrics_reporting/README.md).

## Setup

Python 3.10+ is required. In this checkout, prefer WSL for Python commands.
For the most practical setup path, including Windows PowerShell commands and an
offline smoke workflow, see [docs/runbooks/getting-running.md](docs/runbooks/getting-running.md).

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Run the test suite:

```bash
. .venv/bin/activate
python -m unittest discover -s tests
```

Check whether the local environment is ready for normal research workflows:

```bash
quant-lab doctor
```

Run an offline end-to-end smoke workflow:

```bash
quant-lab smoke-test
```

The tests avoid live market-data calls. Live fetching is done manually through
the CLI.

## Core Concepts

### Daily OHLCV Data

The backtester expects one row per daily bar:

```text
date,open,high,low,close,volume
```

Fetched data is written under `data/cache/`, which is ignored by Git.

### Signal Timing

The engine uses a conservative daily flow:

- A strategy reads bar `t` at that day's close.
- Orders generated from bar `t` are queued.
- Queued orders fill at bar `t+1` open.
- Portfolio value is recorded at each bar close.
- Final-bar signals do not fill because there is no next open.

This rule is important because it avoids pretending a strategy can trade at a
price that was not known when the signal was generated.

### Strategy JSON

Strategies live in `data/strategies/`. Example:

- [data/strategies/sma_crossover.json](data/strategies/sma_crossover.json)
- [data/strategies/rsi_reversion.json](data/strategies/rsi_reversion.json)
- [data/strategies/ema_trend_follow.json](data/strategies/ema_trend_follow.json)
- [data/strategies/breakout_trend.json](data/strategies/breakout_trend.json)

The v1 schema supports:

- `sma`
- `ema`
- `rsi`
- `rolling_high`
- `rolling_low`
- comparison operators like `gt`, `gte`, `lt`, `lte`, `eq`
- crossover operators like `crosses_above` and `crosses_below`

Schema details are in [docs/architecture/strategy-schema.md](docs/architecture/strategy-schema.md).

For one copyable skeptical research loop, see
[docs/runbooks/trustworthy-example-workflow.md](docs/runbooks/trustworthy-example-workflow.md).

## CLI Usage

### Create A Strategy From A Template

List the built-in starter templates:

```bash
quant-lab list-strategy-templates
```

Create a valid v1 strategy JSON file:

```bash
quant-lab new-strategy \
  --template sma-crossover \
  --symbol QQQ \
  --strategy-id qqq_sma_crossover \
  --name "QQQ SMA Crossover" \
  --out data/strategies/qqq_sma_crossover.json
```

Create a simple long/cash trend rule, such as SPY close above/below its
200-day SMA:

```bash
quant-lab new-strategy \
  --template sma-long-cash \
  --symbol SPY \
  --length 200 \
  --strategy-id spy_sma_200_long_cash \
  --name "SPY 200-day SMA Long/Cash" \
  --out data/strategies/spy_sma_200_long_cash.json
```

Available templates are:

```text
sma-crossover
sma-long-cash
ema-trend-follow
rsi-reversion
breakout-trend
```

The command validates the generated JSON before writing it and refuses to
overwrite an existing file unless `--force` is provided.

### Fetch Data

```bash
quant-lab fetch \
  --symbol QQQ \
  --start 2015-01-01 \
  --end 2025-12-31 \
  --out data/cache
```

Output:

```text
data/cache/QQQ_2015-01-01_2025-12-31.csv
data/cache/QQQ_2015-01-01_2025-12-31.provenance.json
```

The fetch command currently uses adjusted daily prices from `yfinance` with
`auto_adjust=True` and `actions=False`. Provider data can have outages, missing
sessions, and corporate-action assumptions, so treat cached data as research
input that may need verification. The provenance JSON records the provider,
requested range, fetched timestamp, row count, actual data range, CSV
fingerprint, and price-adjustment policy.

Inspect a cached CSV and its provenance sidecar:

```bash
quant-lab show-data-source \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv
```

This prints row count, actual date range, file fingerprint, provider, requested
range, fetched timestamp, price-adjustment policy, and warnings such as missing
provenance. Single-run and portfolio trust reports also include the recorded
price-adjustment policy when a provenance sidecar is available, so the
adjusted-price assumption travels with the run evidence.

List cached CSV files without fetching new data:

```bash
quant-lab list-data-cache --data-dir data/cache
```

The inventory shows each cached CSV's symbol, row count, date range, fingerprint
prefix, provenance status, and duplicate-looking symbol/date ranges.

Audit adjusted-price behavior for a known corporate-action window:

```bash
quant-lab audit-adjusted-prices \
  --symbol SPY \
  --start 2024-03-01 \
  --end 2024-04-15 \
  --expected-dividend 2024-03-15=1.595 \
  --out artifacts/data-audits/spy_2024_q1_dividend
```

This downloads two `yfinance` views for the same symbol/date window: adjusted
OHLCV and raw OHLCV with `Adj Close`, dividends, and splits. It writes
`adjusted_price_audit.md`, `adjusted_price_audit.json`, and
`adjusted_price_comparison.csv`. This is still provider-internal verification,
not automated second-source validation, but it makes dividend/split rows
visible, compares manually supplied expected dividend amounts to provider action
rows, and checks that the adjusted close used by `auto_adjust=True` matches the
provider's `Adj Close` field within tolerance.

### Summarize Run Data Trust

After a run exists, write a Markdown trust report from its metadata:

```bash
quant-lab summarize-run-trust \
  --metadata artifacts/research/qqq_sma_trust/baseline/run_metadata.json
```

The report verifies whether the current local CSV still matches the saved
fingerprint, includes source/provenance details, and summarizes data-quality
findings.

For portfolio runs, write the equivalent per-symbol data trust report:

```bash
quant-lab summarize-portfolio-data-trust \
  --metadata artifacts/research/qqq_spy_tlt/baseline/portfolio_metadata.json
```

The portfolio report verifies every symbol input and benchmark data when saved
benchmark metadata is available.

### Run The Default Experiment Workflow

Use this when you already have one strategy file and one data file, and you
want the normal research path to run end to end:

```bash
quant-lab experiment run-default \
  --title "SPY 200-day SMA long/cash drawdown test" \
  --hypothesis "A daily SPY 200-day moving-average long/cash strategy may improve drawdown-adjusted performance versus SPY buy-and-hold after realistic costs." \
  --strategy artifacts/research/spy_200_sma_long_cash/spy_sma_200_long_cash.json \
  --data data/cache/SPY_2015-01-01_2025-12-31.csv \
  --symbol SPY \
  --cost-preset retail-liquid \
  --param sma_200.inputs.length=150,200,250 \
  --train-end 2020-12-31 \
  --test-start 2021-01-01 \
  --date-window 2015-01-02,2019-12-31 \
  --date-window 2020-01-01,2025-12-30 \
  --out artifacts/research/spy_200_sma_long_cash_default
```

This writes the same underlying files as the manual workflow and adds
`default_workflow_summary.md` as a map. The main read-first file remains
`experiment_conclusion.md`.

### Start A Guided Research Plan

Use `research-plan init` when you have a hypothesis and want the lab to create a
consistent local workspace before you start running backtests:

```bash
quant-lab research-plan init \
  --title "QQQ SMA crossover trust check" \
  --hypothesis "A daily SMA crossover may reduce drawdown versus buy-and-hold." \
  --strategy data/strategies/qqq_sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --symbol QQQ \
  --tag QQQ \
  --tag sma \
  --cost-preset retail-liquid \
  --out artifacts/research/qqq_sma_trust
```

This writes:

```text
artifacts/research/qqq_sma_trust/research_plan.json
artifacts/research/qqq_sma_trust/research_plan.md
```

It also creates or references an experiment id and prints the next copyable
baseline `quant-lab run` command. It does not run the baseline automatically.

After you run the recommended command, ask for the next step:

```bash
quant-lab research-plan next \
  --plan artifacts/research/qqq_sma_trust/research_plan.json
```

The guided plan checks the linked experiment's run index rows and recommends
baseline, run-trust review, sweep, train/test validation, saved evidence
summary, robustness checks, canonical conclusion, draft decision, or done.

### Run One Backtest

```bash
quant-lab run \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --sizing percent-equity \
  --allocation 1.0 \
  --cost-preset retail-liquid \
  --experiment-id EXP-001 \
  --note "Hypothesis: the crossover may reduce drawdown versus buy-and-hold." \
  --out artifacts/qqq_sma_crossover
```

Outputs:

```text
artifacts/qqq_sma_crossover/
  metrics.json
  equity_curve.csv
  equity_curve.png
  drawdown.png
  data_quality.json
  report.md
  trades.csv
  research_note.md
  run_metadata.json

artifacts/research_index.jsonl
```

Write a guardrail report for an existing sweep summary:

```bash
quant-lab summarize-sweep-guardrails \
  --summary artifacts/research/qqq_sma_crossover_2015_2025/summary.csv
```

This writes `sweep_guardrails.md` and warns about broad grids, tiny trade
counts, fragile parameter winners, and benchmark underperformance.

Write a focused parameter-neighborhood robustness report for the same sweep:

```bash
quant-lab robustness parameter-neighborhood \
  --summary artifacts/research/qqq_sma_crossover_2015_2025/summary.csv \
  --out artifacts/research/qqq_sma_crossover_2015_2025/robustness/parameters
```

This writes `parameter_neighborhood_summary.csv` and
`parameter_neighborhood_report.md`. It treats the best sweep row as the center,
checks one-parameter numeric neighbors, and asks whether those nearby values
also beat the benchmark. Non-numeric parameters are listed but skipped because
distance is not meaningful.

`report.md` includes a benchmark section built from the same CSV date range and
initial cash. Buy-and-hold is the default benchmark. Use `--benchmark cash` when
you want a flat cash baseline instead. The PNG charts plot the strategy beside
the selected benchmark so the path of returns and drawdowns is easier to inspect
than raw CSV rows. Single-run reports and `run_metadata.json` also record the
benchmark assumptions. The default buy-and-hold benchmark is fully invested at
the first input close, marks at each later close, does not pay transaction
costs, and treats dividends as embedded only when the input price series is
adjusted.

The cost flags are optional. `--commission-fixed` charges a flat amount per
fill, `--commission-rate` charges a fraction of trade value, and
`--slippage-bps` moves buy fills above the next open and sell fills below the
next open. For example, `--slippage-bps 5` means 0.05% one-way slippage.
Use `--cost-preset` for named assumptions such as `none`, `retail-liquid`,
`retail-conservative`, and `high-friction`. Explicit cost flags override preset
values.

Run cost sensitivity when a result looks promising and you want to know whether
it survives stricter assumptions:

```bash
quant-lab robustness cost-sensitivity \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --benchmark buy-and-hold \
  --cost-preset none \
  --cost-preset retail-liquid \
  --cost-preset retail-conservative \
  --out artifacts/research/qqq_sma/robustness/costs
```

This writes normal child run folders plus `cost_sensitivity_summary.csv` and
`cost_sensitivity_report.md`. Child runs are indexed as
`cost_sensitivity_run`.

Run date sensitivity when you want to see whether a result depends too much on
one hand-picked sample period:

```bash
quant-lab robustness date-sensitivity \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --benchmark buy-and-hold \
  --cost-preset retail-liquid \
  --window 2015-01-01,2018-12-31 \
  --window 2019-01-01,2021-12-31 \
  --window 2022-01-01,2025-12-31 \
  --out artifacts/research/qqq_sma/robustness/dates
```

This writes normal child run folders plus `date_sensitivity_summary.csv` and
`date_sensitivity_report.md`. Child runs are indexed as
`date_sensitivity_run`; each child metadata file records its requested window.

Run benchmark sensitivity when you want to check whether the result only looks
good against an easy hurdle:

```bash
quant-lab robustness benchmark-sensitivity \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --cost-preset retail-liquid \
  --benchmark cash \
  --benchmark buy-and-hold \
  --out artifacts/research/qqq_sma/robustness/benchmarks
```

This writes normal child run folders plus
`benchmark_sensitivity_summary.csv` and `benchmark_sensitivity_report.md`.
Child runs are indexed as `benchmark_sensitivity_run`; the report treats
beating cash as weaker evidence than beating buy-and-hold.

`run_metadata.json` records the command, strategy identity, data range, sizing,
cost assumptions, benchmark choice, optional experiment id, Git commit, and
artifact paths. It also records a SHA-256 fingerprint, file size, and modified
timestamp for the input CSV so you can tell later whether the local data file
changed. Treat it as the source of truth for how a run folder was produced.

`data_quality.json` summarizes suspicious input-data conditions such as missing
OHLCV values, duplicate dates, zero volume, non-positive prices, and large gaps.
It includes structured findings with `info`, `warning`, or `critical` severity
plus a top-level `worst_severity`. The same worst severity is copied into
`run_metadata.json` under `data.quality_severity`. These warnings are prompts
for review, not automatic proof that the data is bad.

`research_warnings.json` flags weak evidence such as short samples, tiny trade
counts, no trades, no completed exits, and drawdown that is large relative to
return.

`research_note.md` is written when you pass `--note` or `--note-file`. Use it
for the research question, hypothesis, or conclusion that should live beside
the artifacts instead of only in chat.

Each run also appends one flat JSON line to `artifacts/research_index.jsonl` by
default. Use `--index-path` to write the registry somewhere else. Pass
`--experiment-id EXP-001` to store the experiment id in run metadata and index
rows, and to automatically append the generated `run_metadata.json` path to the
experiment's `linked_runs`. Use `--experiments-path` too when the experiment
registry is not the default `artifacts/experiments.jsonl`.

### Run A Static-Weight Portfolio

List the built-in starter portfolio templates:

```bash
quant-lab list-portfolio-templates
```

Create a valid `portfolio_plan.v1` JSON file:

```bash
quant-lab new-portfolio \
  --template qqq-spy-60-40 \
  --out data/portfolios/qqq_spy_static_60_40.json
```

The command validates the generated JSON before writing it and refuses to
overwrite an existing file unless `--force` is provided.

Generate weight variants from a base portfolio spec:

```bash
quant-lab portfolio-variants \
  --portfolio data/portfolios/qqq_spy_static_60_40.json \
  --weights QQQ=0.50,SPY=0.50 \
  --weights QQQ=0.70,SPY=0.30 \
  --rebalance none \
  --rebalance quarterly \
  --out data/portfolios/variants/qqq_spy
```

The generated files are normal `portfolio_plan.v1` JSON specs, so each one can
be reviewed, committed, or passed to `portfolio-run`. If `--rebalance` is
omitted, the command keeps the base portfolio spec's rebalance frequency.

Generate a capped grid of static-weight candidates from explicit symbols:

```bash
quant-lab portfolio-candidates \
  --symbols QQQ,SPY,TLT \
  --step 0.25 \
  --data-dir data/cache \
  --max-candidates 25 \
  --out data/portfolios/candidates/qqq_spy_tlt
```

This writes candidate JSON files only. It does not run backtests automatically.

Plan a dry-run batch from a directory of portfolio candidate specs:

```bash
quant-lab portfolio-batch plan \
  --portfolios data/portfolios/candidates/qqq_spy_tlt \
  --out artifacts/research/qqq_spy_tlt/batch_001 \
  --initial-cash 100000 \
  --cost-preset retail-liquid
```

This writes `portfolio_batch_manifest.json` with one planned `portfolio-run`
command per candidate. It validates every portfolio spec first and still does
not run any backtests.

Execute a saved batch manifest sequentially:

```bash
quant-lab portfolio-batch run \
  --manifest artifacts/research/qqq_spy_tlt/batch_001/portfolio_batch_manifest.json \
  --experiment-id EXP-001
```

This writes `portfolio_batch_result.json`, runs each planned portfolio through
the same artifact path as `portfolio-run`, and stops on the first failure unless
`--continue-on-error` is provided.

Summarize a planned or executed batch:

```bash
quant-lab portfolio-batch summarize \
  --manifest artifacts/research/qqq_spy_tlt/batch_001/portfolio_batch_manifest.json
```

This writes `portfolio_batch_summary.md` with planned, completed, failed, and
skipped counts plus guardrail warnings for broad batches, failed runs, skipped
runs, missing result files, and thin evidence.

```bash
quant-lab portfolio-run \
  --portfolio data/portfolios/qqq_spy_static_60_40.json \
  --initial-cash 100000 \
  --cost-preset retail-liquid \
  --out artifacts/research/qqq_spy_static_60_40/baseline
```

The portfolio command loads every symbol CSV from the portfolio spec, aligns
dates by intersection, rebalances static target weights, compares against the
configured buy-and-hold benchmark, writes portfolio artifacts, and appends a
`portfolio_run` row to the research index. See
[docs/portfolio/portfolio-workflow.md](docs/portfolio/portfolio-workflow.md).

Inspect a saved portfolio run:

```bash
quant-lab show-portfolio-run \
  --metadata artifacts/research/qqq_spy_static_60_40/baseline/portfolio_metadata.json
```

Compare saved portfolio runs:

```bash
quant-lab compare-portfolio-runs \
  --metadata artifacts/research/portfolio_a/portfolio_metadata.json \
  --metadata artifacts/research/portfolio_b/portfolio_metadata.json
```

Start a guided portfolio research plan when you have an allocation hypothesis
and want the lab to create the local plan files plus the first copyable command:

```bash
quant-lab portfolio-plan init \
  --title "QQQ SPY allocation check" \
  --hypothesis "A 60/40 QQQ/SPY allocation may improve return versus SPY buy-and-hold." \
  --portfolio data/portfolios/qqq_spy_static_60_40.json \
  --tag QQQ \
  --tag SPY \
  --cost-preset retail-liquid \
  --out artifacts/research/qqq_spy_static_60_40
```

After each portfolio run, ask for the next step:

```bash
quant-lab portfolio-plan next \
  --plan artifacts/research/qqq_spy_static_60_40/portfolio_research_plan.json
```

The guided portfolio plan can now recommend portfolio batch steps too: planning
a batch when candidate specs exist, running a saved manifest, and summarizing a
batch result before comparing winners.

Summarize linked portfolio runs for one experiment:

```bash
quant-lab summarize-portfolio-experiment \
  --experiment-id EXP-001 \
  --out artifacts/research/qqq_spy_static_60_40/portfolio_summary.md
```

The portfolio summary includes a conservative evidence label and skeptical
notes for benchmark underperformance, large drawdowns, data-trust report
presence, marginal excess return, allocation variant count, and whether linked
portfolio runs represent multiple cost presets or benchmarks.

### List Previous Runs

```bash
quant-lab list-runs \
  --symbol QQQ \
  --strategy-id sma_crossover \
  --experiment-id EXP-001 \
  --run-type sweep_run \
  --sort sharpe_ratio \
  --limit 10
```

This reads `artifacts/research_index.jsonl` by default and prints a compact
table of past runs. Use `--index-path` to inspect a different registry, and
`--csv` when you want comma-separated output.

Inspect one saved run:

```bash
quant-lab show-run --metadata artifacts/qqq_sma_crossover/run_metadata.json
```

This prints the run identity, data range, metrics, benchmark comparison when
available, cost assumptions, artifact paths, and original command.

Verify that a saved run still matches its local input CSV:

```bash
quant-lab verify-run --metadata artifacts/qqq_sma_crossover/run_metadata.json
```

This recomputes the current CSV fingerprint and compares it with the hash, file
size, row count, and date range stored in `run_metadata.json`. A mismatch means
the run's original input data no longer matches the local file.

Compare saved runs:

```bash
quant-lab compare-runs \
  --metadata artifacts/run_a/run_metadata.json \
  --metadata artifacts/run_b/run_metadata.json
```

This prints a compact table with returns, benchmark context, drawdown, Sharpe,
trade count, cost assumptions, and output directories.

### Track Research Experiments

Create an experiment record before running a new idea:

```bash
quant-lab new-experiment \
  --title "QQQ SMA crossover sweep" \
  --hypothesis "A shorter fast SMA may improve risk-adjusted returns versus the default crossover." \
  --tag QQQ \
  --tag sma \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv
```

This appends one strict JSON line to `artifacts/experiments.jsonl` by default.
Use `--experiments-path` to store the registry somewhere else. Experiment IDs
are local sequential IDs such as `EXP-001`.

List experiments:

```bash
quant-lab list-experiments --status planned --limit 10
```

Inspect one experiment:

```bash
quant-lab show-experiment --experiment-id EXP-001
```

Summarize an experiment with linked run evidence from the research index:

```bash
quant-lab summarize-experiment \
  --experiment-id EXP-001 \
  --index-path artifacts/research_index.jsonl \
  --out artifacts/research/qqq_sma_trust/evidence_summary.md
```

The summary reconciles two links: metadata paths stored on the experiment
record and rows in the research index with the same experiment id. It highlights
the strongest and weakest excess-return evidence, groups evidence by run type,
prints a conservative evidence label, and shows recent linked runs. This is
meant to happen before `draft-decision`, so the decision starts from a saved
research note instead of a half-remembered terminal table.

Write the canonical conclusion artifacts for the experiment:

```bash
quant-lab conclude-experiment \
  --experiment-id EXP-001 \
  --index-path artifacts/research_index.jsonl \
  --out artifacts/research/qqq_sma_trust
```

This writes `experiment_conclusion.md`, `experiment_conclusion.json`, and
`agent_context.md`. Read the Markdown first. Future Codex sessions or local
agents should read the JSON before scanning raw run folders. The conclusion also
includes a structured next-cycle research prompt so the next agent has
inspiration and guardrails: what looked promising, what failed, what not to
repeat, and what the next experiment should prove.

If `session_manifest.json` already exists in the same output directory,
`conclude-experiment` updates it with the conclusion paths, clears conclusion
missing warnings, and records `draft-decision` as the next suggested command.

Inspect a saved session manifest when you are returning to a research workflow:

```bash
quant-lab session status \
  --manifest artifacts/research/qqq_sma_trust/session_manifest.json
```

This prints the current session status, experiment id, conclusion path, plan
path, first next step, and first warning. It is intentionally compact so a human,
future Codex session, or local agent can orient before opening detailed reports.

Create or update that manifest from a saved research plan:

```bash
quant-lab session refresh \
  --plan artifacts/research/qqq_sma_trust/research_plan.json
```

`refresh` reads the plan, experiment registry, research index, and common files
in the output directory. It writes `session_manifest.json` and
`session_manifest.md`, then records the current recommended next command.

Print saved pending commands without running them:

```bash
quant-lab session replay-plan \
  --manifest artifacts/research/qqq_sma_trust/session_manifest.json
```

By default, replay output skips commands marked `executed`. Add
`--include-executed` when you want an audit-style view of every command stored
in the manifest.

Draft a conservative decision without writing to the registry:

```bash
quant-lab draft-decision \
  --experiment-id EXP-001 \
  --index-path artifacts/research_index.jsonl
```

The draft prints a suggested `accept`, `reject`, or `continue` outcome, a short
rationale, supporting and contradictory run references, a next action, and a
ready-to-edit `decide-experiment` command. It is intentionally conservative and
does not modify `artifacts/experiments.jsonl`.

Attach an existing run metadata file to the experiment record:

```bash
quant-lab link-run \
  --experiment-id EXP-001 \
  --metadata artifacts/qqq_sma_crossover/run_metadata.json
```

New `run` and `sweep` commands do this linking automatically when you pass
`--experiment-id`. Keep `link-run` for older artifacts or one-off manual
cleanup.

After reviewing linked run or sweep results, update the experiment decision:

```bash
quant-lab decide-experiment \
  --experiment-id EXP-001 \
  --outcome reject \
  --rationale "Best run still underperformed buy-and-hold after costs." \
  --supporting-run artifacts/research/qqq_sma_crossover_2015_2025/run_004/run_metadata.json \
  --contradicting-run artifacts/research/qqq_sma_train_test_2015_2025/test_selected/run_metadata.json \
  --next-action "Try the same research question on SPY before adding complexity." \
  --session-manifest artifacts/research/qqq_sma_trust/session_manifest.json \
  --tag rejected
```

Runs and sweeps require the experiment to already exist when `--experiment-id`
is provided. This catches typos before a long backtest or sweep starts.

`decide-experiment` stores a structured `decision_record` in the experiment
registry while also keeping the older plain `decision` text. Outcomes are
`accept`, `reject`, and `continue`. `accept` and `reject` mark the experiment
`completed`; `continue` keeps it `running`.

When `--session-manifest` is provided, the command also marks that session
manifest `complete`, records the decision pointer, and clears outstanding next
steps.

Use `update-experiment` for simple status, notes, tag, or legacy decision text
edits when you do not need the structured decision fields.

### Run A Parameter Sweep

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --sizing percent-equity \
  --allocation 1.0 \
  --experiment-id EXP-001 \
  --out artifacts/research/qqq_sma_crossover_2015_2025
```

Outputs:

```text
artifacts/research/qqq_sma_crossover_2015_2025/
  summary.csv
  research.md
  run_001/
    metrics.json
    equity_curve.csv
    equity_curve.png
    drawdown.png
    data_quality.json
    report.md
    trades.csv
    run_metadata.json
    strategy.json

artifacts/research_index.jsonl
```

`summary.csv` is sorted by total return, best first.

Each sweep run writes its own `run_metadata.json`. When the sweep uses
`--experiment-id`, every generated metadata path is appended to that
experiment's `linked_runs`, so `show-experiment` and `summarize-experiment`
can find the evidence without a separate manual linking step.

`research.md` includes a top-runs table and a parameter-stability section. The
stability check is a deterministic heuristic: it looks for one-parameter
neighbors around the best run and flags whether the winner looks supported,
mixed, isolated, or too sparse to judge. Treat it as a prompt for follow-up
testing, not statistical proof.

Sweep summaries include selected benchmark columns:

```text
benchmark_name
benchmark_total_return
benchmark_max_drawdown
excess_total_return
commission_fixed
commission_rate
slippage_bps
```

### Run A Train/Test Sweep

Use train/test mode when you want to choose parameters on an earlier period and
then check the selected variant on a later period:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --sizing percent-equity \
  --allocation 1.0 \
  --cost-preset retail-liquid \
  --experiment-id EXP-001 \
  --train-end 2020-12-31 \
  --test-start 2021-01-01 \
  --select-by sharpe_ratio \
  --out artifacts/research/qqq_sma_train_test_2015_2025
```

Outputs:

```text
artifacts/research/qqq_sma_train_test_2015_2025/
  research.md
  train_sweep/
    summary.csv
    run_001/
      run_metadata.json
      strategy.json
      report.md
  test_summary/
    summary.csv
  test_selected/
    run_metadata.json
    strategy.json
    report.md
```

The train and test periods must not overlap. `--select-by` currently supports
`total_return` and `sharpe_ratio`. The test run metadata records the split
dates, selection metric, selected train run id, and benchmark choice.

This workflow reduces in-sample overconfidence, but it does not prove an edge.
Treat the test result as one skeptical check before trying another symbol, date
range, or nearby parameter grid.

### Run Walk-Forward Windows

Use walk-forward mode when you want repeated train/test checks across multiple
explicit windows:

```bash
quant-lab sweep \
  --strategy data/strategies/sma_crossover.json \
  --data data/cache/QQQ_2015-01-01_2025-12-31.csv \
  --param sma_20.inputs.length=5,10,20 \
  --param sma_50.inputs.length=50,100,200 \
  --sizing percent-equity \
  --allocation 1.0 \
  --cost-preset retail-liquid \
  --walk-forward-window 2015-01-01,2018-12-31,2019-01-01,2020-12-31 \
  --walk-forward-window 2017-01-01,2020-12-31,2021-01-01,2022-12-31 \
  --select-by sharpe_ratio \
  --out artifacts/research/qqq_sma_walk_forward_2015_2022
```

Each window runs the full grid on its train dates, selects one train winner,
and reruns only that selected variant on the window's test dates.

Outputs:

```text
artifacts/research/qqq_sma_walk_forward_2015_2022/
  walk_forward_summary.csv
  research.md
  window_001/
    train_sweep/
      summary.csv
    test_summary/
      summary.csv
    test_selected/
      run_metadata.json
```

Window dates are recorded in test metadata. Do not adjust window dates after
seeing results; create a new experiment folder instead.

### Sizing Modes

The CLI supports two sizing modes:

```bash
--sizing fixed-shares --quantity 100
```

Fixed-share sizing buys the same number of shares on every entry signal.

```bash
--sizing percent-equity --allocation 1.0
```

Percent-equity sizing invests a fraction of available cash at the next open.
`--allocation 1.0` means 100% of available cash, while `--allocation 0.5`
means 50%. This mode allows fractional shares internally because it is meant for
research, not broker-order simulation.

For percent-equity buys, the engine sizes the order so the requested allocation
can cover fill price plus commission. This avoids accidentally spending more
cash than the allocation allows.

## First Research Lesson

The first real QQQ SMA sweep showed why benchmarks and sizing matter.

With fixed 100-share sizing, the best tested SMA crossover was smoother than
buy-and-hold but underperformed it substantially during the 2015-2025 QQQ
sample:

```text
Best SMA variant: about 48% total return with lower drawdown.
QQQ buy-and-hold: about 553% total return with larger drawdown.
```

That does not make the SMA idea useless. It shows why every strategy result
needs benchmark context before interpretation.

## Research Workflow

Use [AUTORESEARCH.md](AUTORESEARCH.md) before interpreting results.

Short version:

1. State the research question.
2. Fetch or choose the data.
3. Run a baseline.
4. Write a data trust report for the baseline.
5. Run one controlled variation or sweep.
6. Compare against a benchmark.
7. Inspect trades and drawdowns.
8. Decide the next experiment.

Avoid treating a good-looking backtest as proof. Use it as evidence to decide
what to test next.

## Current Limitations

- No short selling.
- No live trading, broker integration, or automatic order routing.
- Charts are intentionally simple PNG artifacts, not an interactive dashboard.
- `yfinance` data is convenient but should not be treated as institutional-grade
  data without verification.

## Near-Term Roadmap

1. Keep Milestone 17 on the safe path while non-dry-run execution is deferred:
   docs, validation hardening, dry-run comparison, and cleanup.
2. Decide later, with explicit human review, whether guarded non-dry-run
   `agent cycle` execution belongs in this lab.
3. Reassess Strategy Language V2 versus Portfolio Realism after the advisor loop
   can recommend bounded next experiments from saved artifacts.
