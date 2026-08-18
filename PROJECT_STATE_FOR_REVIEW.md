# Project State For Review

Inspected repository state before this document refresh: `993a6c6 Test regular month-end calendar strategy`.

This file is meant to orient a reviewer quickly. It describes current behavior, not aspirations.

## 1. Executive Summary

Codex-Quant-Lab is a local Python research lab for daily-data, rule-based quant experiments. It is for a hands-on researcher or engineer who wants honest, reproducible backtests before adding more strategy complexity. The normal single-experiment workflow is: prepare data, create or choose a strategy JSON, run `experiment run-default`, then read `experiment_conclusion.md/json`. The normal campaign workflow is: run `campaign run --loop` with a bounded config, let the controller run existing experiment workflows, then read `final_report.md/json`. The repo now separates research-system validity from strategy-hypothesis success, so a strategy can fail while the repo succeeds. The most useful current path is still simple daily ETF research with realistic costs, benchmark comparison, validation, and saved conclusions, now including one fixed event-window calendar branch. The campaign layer can carry conclusions forward, avoid repeated rejected branches, and stop with a final report. Ollama integration exists behind strict proposal validation, retry, fallback, and explicit execution gates; Codex currently exists as a handoff provider, not an automatic API adapter. The biggest weakness is still information design: there are many reports, and users need docs to know which file is the front door. The biggest correctness risk is still adjusted-price and benchmark economics, especially dividends/splits and provider dependence.

## 2. Current End-to-End Workflow

Concrete example:

> Test whether a long/cash SPY 200-day moving-average strategy improves drawdown-adjusted performance versus SPY buy-and-hold after realistic costs.

### Required Single-Experiment Path

1. Prepare data.
   - Entry point: `quant-lab fetch`.
   - Input: symbol and date range.
   - Command:
     ```powershell
     .\.venv-win\Scripts\python.exe -m quant_lab.cli fetch `
       --symbol SPY `
       --start 2015-01-01 `
       --end 2025-12-31 `
       --out data\cache
     ```
   - Output: `data/cache/SPY_2015-01-01_2025-12-31.csv` and `.provenance.json`.
   - Read next: optionally inspect with `show-data-source`.

2. Create strategy JSON.
   - Entry point: `quant-lab new-strategy`.
   - Input: `sma-long-cash`, symbol, SMA length, ids.
   - Command:
     ```powershell
     .\.venv-win\Scripts\python.exe -m quant_lab.cli new-strategy `
       --template sma-long-cash `
       --symbol SPY `
       --length 200 `
       --strategy-id spy_sma_200_long_cash `
       --name "SPY 200-day SMA long/cash" `
       --out artifacts\research\spy_200d_long_cash\strategy.json
     ```
   - Output: strict v1 strategy JSON.
   - Read next: generated `strategy.json` if auditing assumptions.

3. Run the default workflow.
   - Entry point: `quant-lab experiment run-default`.
   - Input: hypothesis, strategy, data, benchmark/cost/validation choices.
   - Command:
     ```powershell
     .\.venv-win\Scripts\python.exe -m quant_lab.cli experiment run-default `
       --title "SPY 200-day SMA long/cash drawdown test" `
       --hypothesis "A daily SPY 200-day moving-average long/cash strategy may improve drawdown-adjusted performance versus SPY buy-and-hold after realistic costs." `
       --strategy artifacts\research\spy_200d_long_cash\strategy.json `
       --data data\cache\SPY_2015-01-01_2025-12-31.csv `
       --symbol SPY `
       --cost-preset retail-liquid `
       --param sma_200.inputs.length=150,200,250 `
       --train-end 2020-12-31 `
       --test-start 2021-01-01 `
       --date-window 2015-01-02,2019-12-31 `
       --date-window 2020-01-01,2025-12-30 `
       --out artifacts\research\spy_200d_long_cash_default
     ```
   - Output: baseline run, sweep/validation/robustness artifacts, `evidence_summary.md`, `experiment_conclusion.md`, `experiment_conclusion.json`, and a workflow summary.
   - Read next: `artifacts/research/spy_200d_long_cash_default/experiment_conclusion.md`.

### Optional Validation Steps

- `quant-lab summarize-run-trust`: one-run trust report from `run_metadata.json`.
- `quant-lab sweep`: parameter sweeps, train/test, and walk-forward checks.
- `quant-lab robustness cost-sensitivity`: rerun across cost presets.
- `quant-lab robustness date-sensitivity`: rerun across date windows.
- `quant-lab robustness benchmark-sensitivity`: compare benchmark assumptions.
- `quant-lab audit-adjusted-prices`: provider-internal adjusted-price audit.

### Advanced Research-Management Steps

- `research-plan init/next`: guided manual workflow.
- `session refresh/status/replay-plan`: session orientation and command replay.
- `agent context/suggest/cycle/validate-recommendation`: local-agent advisor artifacts.
- `ideas suggest`: conceptual strategy-catalog suggestion from prior conclusions.
- `campaign run --loop`: bounded multi-cycle orchestration.
- Portfolio commands: `portfolio-run`, `portfolio-plan`, `portfolio-variants`, `portfolio-candidates`, `portfolio-batch`.

### Campaign Path

Deterministic campaign:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_drawdown_control_campaign.json `
  --out artifacts\campaigns\spy_research_001 `
  --loop `
  --duration 30m `
  --max-cycles 3 `
  --max-total-runs 33 `
  --force
```

Ollama dry run:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_drawdown_control_campaign.json `
  --provider ollama `
  --out artifacts\campaigns\spy_ollama_dry_run_001 `
  --model llama3.1:8b `
  --force
```

Codex handoff:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_drawdown_control_campaign.json `
  --provider codex `
  --out artifacts\campaigns\spy_codex_handoff_001 `
  --force
```

Campaign front door after completion: `artifacts/campaigns/<campaign>/final_report.md`.

## 3. Current Architecture Map

### Market Data

- Important files: `src/quant_lab/data_fetch.py`, `src/quant_lab/data_source.py`, `src/backtester_core/data.py`, `src/quant_lab/data_quality.py`.
- Owns: yfinance download, OHLCV normalization, provenance, cached-data inspection, data-quality warnings.
- Flow: `fetch` writes adjusted OHLCV CSV plus provenance; runs load the CSV, validate it, fingerprint it, and carry provenance into metadata/reports.
- Dependents: runs, sweeps, robustness, portfolio runs, trust reports, adjusted-price audit.

### Strategy Definition

- Important files: `src/quant_lab/strategy_schema.py`, `src/quant_lab/strategy_templates.py`, `src/quant_lab/rule_based_strategy.py`, `src/quant_lab/event_calendar.py`, `data/strategies/*.json`, `data/event_calendars/*.csv`.
- Owns: strict strategy schema, starter templates, indicator/rule parsing, signal generation, and fixed event-window inputs.
- Flow: JSON strategy -> `StrategySpec` -> rule-based strategy -> bar-by-bar signals. Event-window strategies additionally read a predeclared event calendar and output `1.0` only for bars inside allowed windows.
- Dependents: `run`, `experiment run-default`, campaign conversion, sweeps, robustness.

### Backtest Execution And Portfolio Logic

- Important files: `src/backtester_core/engine.py`, `src/backtester_core/execution.py`, `src/backtester_core/portfolio.py`, `src/quant_lab/run_artifacts.py`, `src/quant_lab/portfolio_backtest.py`.
- Owns: next-open fills, commissions/slippage, cash/position accounting, equity curves, portfolio rebalancing.
- Flow: strategy signal on bar `t` becomes order for bar `t+1` open; portfolio marks equity to close.
- Dependents: all strategy runs, portfolio runs, validation, and reports.

### Metrics And Reporting

- Important files: `src/metrics_reporting/metrics.py`, `src/metrics_reporting/artifacts.py`, `src/quant_lab/benchmarks.py`, `src/quant_lab/experiment_conclusion.py`, `src/quant_lab/campaign_report.py`.
- Owns: return/drawdown metrics, charts, benchmark comparisons, run reports, experiment conclusions, campaign final reports.
- Flow: execution output -> raw artifacts -> run metadata/index -> summaries/conclusions -> session/agent/campaign context.
- Dependents: humans, Codex, local agents, campaign controller.

### Robustness And Validation

- Important files: `src/quant_lab/robustness.py`, `src/quant_lab/parameter_neighborhood.py`, `src/quant_lab/sweep_guardrails.py`.
- Owns: cost/date/benchmark sensitivity and parameter-neighborhood review.
- Flow: reuse normal backtest execution with controlled changes, then write summary CSV/Markdown.
- Dependents: default experiment workflow and experiment conclusions.

### Experiment Registry And Guided Workflow

- Important files: `src/quant_lab/research_registry.py`, `src/quant_lab/research_index.py`, `src/quant_lab/research_plan.py`, `src/quant_lab/session_manifest.py`.
- Owns: experiment records, linked runs, research index, session orientation, next-step guidance.
- Flow: run metadata is appended to `research_index.jsonl`, experiment records link metadata paths, session manifests package the current state.
- Dependents: summaries, conclusions, agent context, campaign knowledge.

### Campaign Orchestration

- Important files: `src/quant_lab/campaign.py`, `src/quant_lab/campaign_proposal.py`, `src/quant_lab/campaign_provider.py`, `src/quant_lab/campaign_provider_prompt.py`, `src/quant_lab/campaign_conversion.py`, `src/quant_lab/campaign_execution.py`, `src/quant_lab/campaign_knowledge.py`, `src/quant_lab/campaign_report.py`, `src/quant_lab/cli_campaign.py`.
- Owns: bounded campaign config/state, strict proposal schema, provider attempts, validation, conversion to `experiment run-default`, execution, cumulative memory, final reports.
- Flow: config/state -> provider proposal -> validator -> existing experiment workflow -> canonical conclusion -> campaign state/final report.
- Dependents: campaign CLI, future model-driven research loops.

## 4. Findings And Knowledge Flow

After a normal run, raw evidence is saved as `metrics.json`, `equity_curve.csv`, `trades.csv`, `run_metadata.json`, `strategy.json`, data quality JSON, warnings JSON, charts, and a row in `research_index.jsonl`.

Human-readable analysis is saved as `report.md`, optional trust reports, sweep `research.md`, robustness reports, `evidence_summary.md`, and `experiment_conclusion.md`.

Experiment-level conclusions are saved in `experiment_conclusion.md` and `experiment_conclusion.json`. These are the main source of truth for what was learned inside one experiment.

Campaign-level conclusions are saved in `campaign_state.md/json` during execution and `final_report.md/json` when stopped. The campaign state carries forward completed experiment titles, research-system status, strategy-hypothesis status, current findings, do-not-repeat items, unresolved questions, and budgets.

Future runs do not automatically query a global semantic knowledge base. Future campaign cycles can read their own accumulated campaign state; agent/context workflows can package conclusions; humans and Codex still need to interpret cross-experiment knowledge.

Worked example:

> QQQ SMA crossover reduced drawdown but materially underperformed buy-and-hold.

- Saved data: run-level metrics, equity curve, trades, metadata, strategy snapshot, data quality, warnings.
- Saved analysis: `report.md`, optional trust report, sweep/robustness reports.
- Saved decision: experiment registry decision plus `experiment_conclusion.md/json`.
- Reusable knowledge: `do_not_repeat`, `current_conclusion`, `next_useful_tests`, and campaign `do_not_repeat` if the run occurred inside a campaign.
- Effect on next experiment: inside the same campaign, rejected branches are carried into `campaign_state.json` and can block unchanged repeats. Across unrelated experiments, reuse still requires a human, Codex, or local agent to read the prior conclusion.

## 5. Artifact Inventory

### Raw Evidence

- Market data CSV and provenance: created by `fetch`; authoritative local input; read when checking source data.
- `strategy.json`: saved beside each run; authoritative exact strategy input for that run; intentionally duplicates the source strategy file.
- `run_metadata.json`: created by run persistence; authoritative run identity, paths, costs, sizing, benchmark, git commit, data fingerprint.
- `metrics.json`, `equity_curve.csv`, `trades.csv`: created by run artifact persistence; authoritative raw run results.
- `data_quality.json`, `research_warnings.json`: created per run; authoritative caveats.
- Portfolio equivalents: `portfolio_metadata.json`, `portfolio_metrics.json`, `portfolio_equity_curve.csv`, `portfolio_positions.csv`, `portfolio_trades.csv`.

### Derived Analysis

- `report.md`: one-run human report; read for a single run.
- `run_trust_report.md`: one-run trust/caveat report; read when auditing data/benchmark assumptions.
- `summary.csv` and `research.md`: sweep outputs; read for parameter experiments.
- Robustness reports: cost/date/benchmark/parameter-neighborhood summaries; read for sensitivity.
- `default_workflow_summary.md`: one-command workflow receipt; read when checking what `experiment run-default` produced.

### Experiment-Level Knowledge

- `evidence_summary.md`: supporting summary, not the final front door.
- `experiment_conclusion.md`: main human-readable experiment conclusion.
- `experiment_conclusion.json`: machine-readable conclusion for agents/campaigns.
- Registry decisions in `experiments.jsonl`: structured experiment decisions.

### Campaign-Level Knowledge

- `campaign_config.json`: authoritative campaign input.
- `campaign_state.json/md`: current campaign status and memory.
- `cycles/cycle_*/proposal.json`: final selected proposal for a cycle.
- `cycles/cycle_*/proposal_validation.md/json`: proposal gate.
- `cycles/cycle_*/provider_attempt_*/provider_context.json` and `provider_prompt.md`: model/Codex context.
- `cycles/cycle_*/campaign_execution.json/md`: execution receipt when a cycle executes.
- `final_report.md/json`: campaign front door after stop.

Main entry points:

- One run: `report.md` for human reading, `run_metadata.json` for audit.
- One sweep: `research.md` plus `summary.csv`.
- One experiment: `experiment_conclusion.md`.
- One campaign: `final_report.md`.

## 6. CLI Surface

Core:

- `fetch`, `show-data-source`, `list-data-cache`
- `new-strategy`, `list-strategy-templates`
- `run`, `experiment run-default`
- `campaign run`, `campaign init`, `campaign status`

Validation:

- `doctor`, `smoke-test`, `verify-run`
- `summarize-run-trust`, `audit-adjusted-prices`
- `sweep`
- `robustness cost-sensitivity`, `date-sensitivity`, `benchmark-sensitivity`, `parameter-neighborhood`

Organization:

- `list-runs`, `show-run`, `compare-runs`
- `new-experiment`, `list-experiments`, `show-experiment`, `update-experiment`, `link-run`, `decide-experiment`, `draft-decision`
- `summarize-experiment`, `conclude-experiment`
- `session status`, `session replay-plan`, `session refresh`

Advanced:

- Portfolio commands: `new-portfolio`, `portfolio-run`, `portfolio-plan`, `portfolio-variants`, `portfolio-candidates`, `portfolio-batch`, `show-portfolio-run`, `compare-portfolio-runs`, `summarize-portfolio-data-trust`, `summarize-portfolio-experiment`
- Agent commands: `agent context`, `agent suggest`, `agent cycle`, `agent validate-recommendation`
- Idea command: `ideas suggest`

Redundant candidates:

- `show-run`, `report.md`, and `run_metadata.json` overlap by design.
- `session_manifest.md`, `campaign_state.md`, and `final_report.md` can all act as orientation files at different scopes.
- Manual `research-plan` flow overlaps with `experiment run-default`, but remains useful for step-by-step work.

Legacy candidates:

- None are clearly legacy. The project should demote some commands in docs before removing anything.

Most commands still require explicit paths. `experiment run-default` and `campaign run --loop` are the main orchestration commands that reduce manual path passing.

## 7. What Changed Recently

- Candidate-menu discovery was added. Campaigns now generate bounded `campaign_candidate_menu.v1` choices from opportunity theses, experiment templates, parameter neighborhoods, and prior conclusions before asking a provider to choose.
- Campaign provider behavior was narrowed. Model providers choose candidate IDs, request human review, or stop; Python owns execution, validation, state, budgets, and stopping.
- Deterministic campaign loops now execute existing `experiment run-default` workflows, read `experiment_conclusion.json`, update campaign memory, and stop with `final_report.md/json`.
- Liquid ETF universe runs proved the loop can diversify across symbols and stop with `SEARCH_SPACE_EXHAUSTED`; the bottleneck is now thesis/template breadth more than orchestration.
- Event-calendar research was added for the calendar/rebalance mechanism, including generated month-end/quarter-end windows, no-trade event studies, and one fixed SPY regular month-end strategy test.
- `calendar-month-end` is now an executable strategy template and campaign-visible experiment template, but it remains a single fixed event-window branch rather than a timing-optimization feature.
- Retry/fallback behavior and explicit model execution gating were added. Invalid or failed model attempts are saved, retried once, then stop or fall back for inspection.
- Codex handoff provider was added. It writes Codex-readable context/prompt artifacts and stops with `request_human_review`; it does not pretend to call this chat session.

Net effect: campaign orchestration is now coherent and useful, while the discovery layer remains deliberately bounded. Model-provider execution still needs more evidence before being trusted for unattended research.

## 8. Current Strengths

1. Execution timing is explicit and tested. Core backtests use next-open fills and tests cover no same-bar fill, final-bar signals, commissions/slippage, and sizing behavior.
2. Reproducibility is strong. Runs save exact `strategy.json`, metadata, data fingerprints, costs, sizing, benchmark assumptions, and output paths.
3. The project now distinguishes system validity from investment success. `experiment_conclusion.json` has research-system and strategy-hypothesis statuses, so failed strategies are not confused with repo failures.
4. Campaign state carries knowledge forward inside a campaign. It records completed experiments, findings, do-not-repeat items, unresolved questions, remaining budgets, and branch-level opportunity/template exclusions.
5. Model/agent boundaries are conservative. Ollama proposals are strict JSON, retried once, validated, and dry-run by default. Codex is a handoff, not an uncontrolled executor.

## 9. Current Weaknesses

1. Information-design problem: too many Markdown reports compete for attention. `experiment_conclusion.md` and campaign `final_report.md` are the intended front doors, but this is learned from docs.
2. Correctness problem: adjusted-price economics are still provider-dependent. The audit checks yfinance internal consistency, but not an independent provider or full corporate-action accounting.
3. Missing research capability: no global cross-experiment semantic memory. Conclusions are reusable artifacts, but a new unrelated experiment does not automatically query them.
4. Architecture/usability problem: there are many CLI commands. The core path is simpler now, but advanced use still requires manual paths and ids.
5. Missing model capability: Ollama can choose from strict candidate menus, but small models still need bounded raw material and should not be trusted to invent experiments freely. Codex is a handoff provider only.

## 10. One Concrete Experiment Walkthrough

Shortest current path for the SPY 200-day long/cash question:

1. Data preparation:
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli fetch --symbol SPY --start 2015-01-01 --end 2025-12-31 --out data\cache
   ```
   Creates adjusted daily OHLCV CSV and provenance.

2. Strategy creation:
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli new-strategy --template sma-long-cash --symbol SPY --length 200 --strategy-id spy_sma_200_long_cash --name "SPY 200-day SMA long/cash" --out artifacts\research\spy_200d_long_cash\strategy.json
   ```
   Creates strict executable strategy JSON.

3. Baseline plus validation workflow:
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli experiment run-default `
     --title "SPY 200-day SMA long/cash drawdown test" `
     --hypothesis "A daily SPY 200-day moving-average long/cash strategy may improve drawdown-adjusted performance versus SPY buy-and-hold after realistic costs." `
     --strategy artifacts\research\spy_200d_long_cash\strategy.json `
     --data data\cache\SPY_2015-01-01_2025-12-31.csv `
     --symbol SPY `
     --cost-preset retail-liquid `
     --param sma_200.inputs.length=150,200,250 `
     --train-end 2020-12-31 `
     --test-start 2021-01-01 `
     --date-window 2015-01-02,2019-12-31 `
     --date-window 2020-01-01,2025-12-30 `
     --out artifacts\research\spy_200d_long_cash_default
   ```
   Creates baseline run, sweep, cost/date/benchmark checks, train/test validation, evidence summary, and conclusion.

4. Main report:
   ```text
   artifacts/research/spy_200d_long_cash_default/experiment_conclusion.md
   ```
   This is the first file to read.

5. Cost sensitivity:
   Included in `experiment run-default` when the default workflow is run with the current validation arguments. Manual command remains available through `robustness cost-sensitivity`.

6. Date sensitivity:
   Included through `--date-window` arguments. Manual command remains available through `robustness date-sensitivity`.

7. Train/test validation:
   Included through `--train-end` and `--test-start`.

8. Experiment summary/final conclusion:
   `experiment_conclusion.md/json` is the canonical conclusion. `default_workflow_summary.md` is the execution receipt.

Campaign variant:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_drawdown_control_campaign.json `
  --out artifacts\campaigns\spy_research_001 `
  --loop `
  --duration 30m `
  --max-cycles 3 `
  --max-total-runs 33 `
  --force
```

This runs the current deterministic campaign sequence and writes `final_report.md/json`.

## 11. Test And Correctness Status

Last full-suite command used during this docs refresh:

```powershell
$env:MPLCONFIGDIR='artifacts/matplotlib-cache'
.\.venv-win\Scripts\python.exe -m unittest discover -s tests
```

Observed result during this docs refresh: `503` tests passed, `0` failed, `0` skipped, `21.317s`.

Coverage assessment:

- Next-open execution: directly tested.
- No same-bar look-ahead: directly tested.
- Final-bar signals: directly tested.
- Cash exits: tested through long/cash strategy and portfolio accounting paths.
- Percent-equity sizing: directly tested.
- Commissions/slippage: directly tested.
- Adjusted price handling: partially audited against provider-internal yfinance adjusted OHLC behavior.
- Dividends: not modeled as cash flows; provider-adjusted prices are relied on.
- Splits: not directly modeled; assumed included in adjusted OHLC.
- Benchmark alignment: tested and audited for relevant SPY entry-timing concern.
- Indicator warm-up: directly tested.
- Train/test separation and walk-forward windows: directly tested for overlap/selection mechanics.
- Data fingerprint verification: directly tested.
- Experiment linking: directly tested.
- Campaign linking/knowledge: directly tested for conclusion carry-forward, do-not-repeat, final reports, provider attempts, retries, fallback, loop mode, candidate menus, and bounded branch filters.

Passing tests do not prove economic truth. They prove deterministic plumbing and many accounting assumptions.

## 12. Reviewer Questions

1. Is the project currently useful for disciplined daily-data quant research?
   - Yes, for small daily, long-only, rule-based research with strong auditability.
2. Is it over-engineered relative to its strategy capabilities?
   - Somewhat, but less than before. Campaign and conclusion machinery now connects to real workflows.
3. Are findings merely stored, or turned into reusable knowledge?
   - Inside a campaign, they are reusable through campaign state. Across unrelated experiments, they are stored/summarized but not globally automatic.
4. Do the pieces work together coherently?
   - Mostly yes. The single-experiment and deterministic campaign paths are coherent. Model paths are bounded but not yet proven productive.
5. Where does the workflow create unnecessary human-facing noise?
   - Run/trust/sweep/robustness/evidence/session/agent/campaign Markdown files overlap. The docs must keep naming the front doors.
6. What should be simplified next?
   - Make docs even more front-door oriented and consider demoting older manual workflow docs behind `experiment run-default` and `campaign run --loop`.
7. What should not be removed?
   - Raw artifacts, `run_metadata.json`, strategy snapshots, `experiment_conclusion.md/json`, campaign state/final reports, data fingerprints, and correctness tests.
8. What is the single highest-priority correctness audit?
   - Independent adjusted-price/corporate-action validation against another provider or known-event dataset.
9. What is the single best next real experiment?
   - Inspect a campaign candidate menu that includes the calendar-flow branch, then run only if campaign memory is not already blocking the exact weakened branch.
10. Is the project ready for feature development, or should development pause for consolidation?
   - Pause major feature expansion. Run a few real campaigns/experiments, inspect friction, and only then add strategy breadth.
