# Project State For Review

Inspected code/research state: `bca10d7e9b38dd809573dc4c16f0dcea046a531b`

Note: this review document is committed in a later docs-cleanup commit, so the
final commit hash is reported in the commit history rather than embedded here.

## 1. Executive Summary

Codex-Quant-Lab is now a local Python daily-data quant research lab, not a trading system. It can fetch adjusted daily OHLCV data, validate simple JSON strategies, run long-only backtests with next-open fills, save auditable artifacts, run sweeps and robustness checks, and organize results into experiment-level summaries and conclusions. The intended user is a hands-on researcher or engineer who wants disciplined small experiments without building a full research platform. The normal workflow is hypothesis -> default experiment workflow -> baseline run -> trust/robustness/validation -> canonical experiment conclusion -> decision. The most mature path is single-symbol rule-based strategy research; portfolio support exists but is more advanced and noisier. The project has useful guardrails around data fingerprints, benchmark comparison, transaction costs, warnings, saved strategy payloads, and explicit human review. Recent work added local-agent advisor scaffolding and the first strategy-layer risk control, but agent execution remains dry-run and human-gated. The biggest remaining weakness is information design: the system writes many overlapping human-facing reports, and a reviewer must know that `experiment_conclusion.md` is the intended experiment-level source of truth. A second weakness is that findings are saved and summarized, but they are not automatically converted into a reusable knowledge base that constrains future experiments unless a human, Codex, or local agent reads the conclusion/manifest. Correctness is supported by tests, but adjusted-price/corporate-action assumptions still depend heavily on `yfinance` behavior and should be audited directly.

## 2. Current End-to-End Workflow

Concrete target hypothesis:

> Test whether a long/cash SPY 200-day moving-average strategy improves drawdown-adjusted performance versus SPY buy-and-hold after realistic costs.

The project can express this as a v1 JSON rule strategy that enters when SPY close is above a 200-day moving average and exits to cash when close is below it. The current `new-strategy` command can generate this with the `sma-long-cash` template and `--length 200`. Existing examples include `data/strategies/sma_crossover.json`, `data/strategies/ema_trend_follow.json`, and `data/strategies/sma_long_cash_vol_target.json`.

### Required Steps

1. Data preparation.
   - Entry point: `quant-lab fetch`.
   - Command:
     ```powershell
     .\.venv-win\Scripts\python.exe -m quant_lab.cli fetch `
       --symbol SPY `
       --start 2015-01-01 `
       --end 2025-12-31 `
       --out data\cache
     ```
   - Input: ticker/date range.
   - Output: `data/cache/SPY_2015-01-01_2025-12-31.csv` plus `data/cache/SPY_2015-01-01_2025-12-31.provenance.json`.
   - Read next: optional `quant-lab show-data-source --data data\cache\SPY_2015-01-01_2025-12-31.csv`.

2. Strategy definition.
   - Entry point: `quant-lab new-strategy`.
   - Command:
     ```powershell
     .\.venv-win\Scripts\python.exe -m quant_lab.cli new-strategy `
       --template sma-long-cash `
       --symbol SPY `
       --length 200 `
       --strategy-id spy_sma_200_long_cash `
       --name "SPY 200-day SMA long/cash" `
       --out artifacts\research\spy_200d_long_cash\spy_sma_200_long_cash.json
     ```
   - Input: template name, symbol, SMA length, strategy id/name, and output path.
   - Output: a strict strategy JSON consumed by `src/quant_lab/strategy_schema.py` and `src/quant_lab/rule_based_strategy.py`.
   - Read next: the generated strategy JSON and `docs/architecture/strategy-schema.md`.

3. Default experiment workflow.
   - Entry point: `quant-lab experiment run-default`.
   - Command:
     ```powershell
     .\.venv-win\Scripts\python.exe -m quant_lab.cli experiment run-default `
       --title "SPY 200-day SMA long/cash drawdown test" `
       --hypothesis "A daily SPY 200-day moving-average long/cash strategy may improve drawdown-adjusted performance versus SPY buy-and-hold after realistic costs." `
       --strategy artifacts\research\spy_200d_long_cash\spy_sma_200_long_cash.json `
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
   - Input: hypothesis, strategy JSON, OHLCV CSV, cost preset, benchmark default, one controlled parameter neighborhood, train/test split, and date windows.
   - Output: baseline run, trust report, sweep, train/test validation, cost/date/benchmark sensitivity, `evidence_summary.md`, `experiment_conclusion.md/json`, `default_workflow_summary.md`, and a conservative decision.
   - Read next: `artifacts/research/spy_200d_long_cash_default/experiment_conclusion.md`.

4. Supporting inspection.
   - Entry points: `show-run`, `compare-runs`, `summarize-run-trust`, `session refresh`, and direct artifact reads.
   - Input: generated metadata paths and session/conclusion artifacts.
   - Output: no new core evidence unless a report command is explicitly run.
   - Read next: supporting files only when the conclusion raises a question, especially `baseline/report.md`, `baseline/run_metadata.json`, `sweep_001/research.md`, and robustness reports.

The old manual chain still exists, but it is now the advanced path. The first walkthrough should not require users to manually operate `research-plan init`, `run`, `summarize-run-trust`, `summarize-experiment`, and `conclude-experiment` unless they need step-by-step control.

### Optional Validation Steps

- Parameter sweep: `quant-lab sweep --param sma_200.inputs.length=150,175,200,225,250`.
- Train/test validation: same `sweep` command with `--train-end`, `--test-start`, and `--select-by`.
- Walk-forward validation: same `sweep` command with repeated `--walk-forward-window train_start,train_end,test_start,test_end`.
- Cost sensitivity: `quant-lab robustness cost-sensitivity`.
- Date sensitivity: `quant-lab robustness date-sensitivity`.
- Benchmark sensitivity: `quant-lab robustness benchmark-sensitivity`.
- Parameter-neighborhood report: `quant-lab robustness parameter-neighborhood --summary ...`.

### Advanced Research-Management Steps

- Experiment registry: `new-experiment`, `list-experiments`, `show-experiment`, `update-experiment`, `link-run`, `decide-experiment`.
- Session manifest: `session status`, `session replay-plan`, `session refresh`.
- Local-agent advisor: `agent context`, `agent suggest`, `agent cycle --dry-run`, `agent validate-recommendation`.
- Portfolio workflow: `portfolio-run`, `portfolio-plan`, `portfolio-variants`, `portfolio-candidates`, `portfolio-batch`.

## 3. Current Architecture Map

### Market Data

- Source files: `src/quant_lab/data_fetch.py`, `src/quant_lab/data_source.py`, `src/backtester_core/data.py`, `src/quant_lab/data_quality.py`.
- Owns: yfinance download, OHLCV normalization, CSV/provenance writing, cached-data inspection, OHLCV validation, data-quality warnings.
- Information flow: `fetch_market_data()` calls `yf.download(..., auto_adjust=True, actions=False)`, `normalize_ohlcv_frame()` writes date/open/high/low/close/volume CSVs, and `write_market_data_provenance()` records provider/date/fingerprint metadata. Backtests then read CSVs and run `validate_ohlcv_data()` plus `build_data_quality_report()`.
- Dependents: `run`, `sweep`, robustness commands, portfolio runs, trust reports, `doctor`, and metadata fingerprint verification.

### Strategy Definition

- Source files: `src/quant_lab/strategy_schema.py`, `src/quant_lab/strategy_templates.py`, `data/strategies/*.json`, `docs/architecture/strategy-schema.md`.
- Owns: strict v1 JSON parsing, allowed indicators/operators/value references, starter templates.
- Information flow: JSON is parsed into `StrategySpec`, validated for unknown fields and indicator references, then passed to `build_rule_based_strategy()`.
- Dependents: single-run backtests, sweeps, robustness checks, research plans, smoke tests.

### Signal Generation

- Source file: `src/quant_lab/rule_based_strategy.py`.
- Owns: incremental close-based SMA/EMA/RSI/rolling-high/rolling-low state and entry/exit condition evaluation.
- Information flow: each close updates indicator state, conditions produce buy/sell orders, and the engine fills those orders on the next bar open.
- Dependents: `src/quant_lab/run_artifacts.py`, sweeps, robustness, smoke tests.

### Backtest Execution

- Source files: `src/backtester_core/engine.py`, `src/backtester_core/execution.py`, `src/backtester_core/portfolio.py`, `src/quant_lab/run_artifacts.py`, `src/quant_lab/run_config.py`.
- Owns: next-open order execution, transaction cost model, cash/position accounting, equity history, run configuration.
- Information flow: `run_single_backtest()` builds the strategy, benchmark, data quality report, and engine; `BacktestEngine.run()` queues signals from bar `t` and fills on bar `t+1` open; `Portfolio` records fills and marks to close.
- Dependents: CLI `run`, `sweep`, robustness, smoke test, artifact writers.

### Portfolio Logic

- Source files: `src/quant_lab/portfolio_spec.py`, `portfolio_data.py`, `portfolio_backtest.py`, `portfolio_execution.py`, `portfolio_artifacts.py`, `portfolio_metadata.py`, `portfolio_benchmarks.py`.
- Owns: static-weight portfolio specs, aligned multi-symbol data, periodic rebalancing, portfolio-level trades/positions/equity, benchmarks, metadata.
- Information flow: portfolio spec plus symbol CSVs are loaded, aligned by date, rebalanced according to frequency, and written as portfolio-specific artifacts.
- Dependents: `portfolio-run`, `portfolio-plan`, `portfolio-variants`, `portfolio-candidates`, `portfolio-batch`, portfolio inspection/trust/summary commands.

### Metrics

- Source files: `src/backtester_core/reporting.py`, `src/metrics_reporting/metrics.py`, `src/metrics_reporting/artifacts.py`, `src/metrics_reporting/charts.py`, `src/quant_lab/benchmarks.py`.
- Owns: total return, CAGR, Sharpe, max drawdown, equity/drawdown chart output, buy-and-hold/cash benchmark curves.
- Information flow: engine output -> metrics summary -> run report, JSON metrics, charts, benchmark comparison.
- Dependents: all run/sweep/robustness/portfolio artifacts and summaries.

### Reporting

- Source files: `src/quant_lab/run_artifacts.py`, `experiment_summary.py`, `experiment_conclusion.py`, `portfolio_report.py`, `portfolio_experiment_summary.py`, `run_trust.py`, `portfolio_trust.py`, `sweep_guardrails.py`, `parameter_neighborhood.py`.
- Owns: human-readable run reports, evidence summaries, conclusions, trust reports, portfolio reports, robustness/guardrail reports.
- Information flow: raw run metadata/index rows are converted to Markdown reports; `experiment_conclusion.py` synthesizes linked rows into a current conclusion, do-not-repeat list, and next useful tests.
- Dependents: users, Codex/local-agent context, session manifests.

### Robustness Testing

- Source files: `src/quant_lab/robustness.py`, `src/quant_lab/parameter_neighborhood.py`, `src/quant_lab/sweep_guardrails.py`.
- Owns: cost sensitivity, date sensitivity, benchmark substitution, parameter-neighborhood review, sweep guardrails.
- Information flow: robustness commands rerun normal backtests with controlled perturbations and append rows to the same research index; reports summarize sensitivity outcomes.
- Dependents: guided workflow and experiment conclusion labeling.

### Experiment Registry

- Source files: `src/quant_lab/research_registry.py`, `src/quant_lab/research_index.py`.
- Owns: experiment JSONL records, linked metadata paths, decisions, flat run index rows.
- Information flow: runs append flat rows to `research_index.jsonl`; experiment records in `experiments.jsonl` link metadata paths and store status/decision fields.
- Dependents: `list-runs`, `show-run`, compare commands, summaries, conclusions, guided workflow, session manifests.

### Guided Workflow

- Source files: `src/quant_lab/research_plan.py`, `src/quant_lab/research_plan_workflow.py`, `src/quant_lab/cli_research_plan.py`, `src/quant_lab/portfolio_research_plan.py`, `src/quant_lab/cli_session.py`.
- Owns: plan files, next-step recommendation, session refresh/status/replay.
- Information flow: plan + index + experiment registry + known artifacts -> next recommended command; session manifest packages current status and key artifacts.
- Dependents: human CLI workflow and agent context.

### Artifact Persistence

- Source files: `src/quant_lab/run_artifacts.py`, `src/quant_lab/run_metadata.py`, `src/metrics_reporting/artifacts.py`, `src/quant_lab/session_manifest.py`, `src/quant_lab/agent_*`.
- Owns: stable JSON/CSV/Markdown/PNG outputs.
- Information flow: every run writes its own directory; experiment-level commands write summary/conclusion files; agent commands write context/recommendation/cycle artifacts.
- Dependents: all inspection, verification, summary, session, and local-agent commands.

## 4. Findings and Knowledge Flow

### What Happens After A Run

- Raw evidence saved: `metrics.json`, `equity_curve.csv`, `trades.csv`, `data_quality.json`, `research_warnings.json`, charts, `run_metadata.json`, and a flat row in `research_index.jsonl`.
- Human-readable analysis saved: `report.md`, optional `research_note.md`, optional `run_trust_report.md`, sweep `research.md`, robustness reports, evidence summaries.
- Experiment-level conclusion saved: `experiment_conclusion.md`, `experiment_conclusion.json`, and `agent_context.md` from `conclude-experiment`.
- Current conclusion storage: the authoritative experiment-level conclusion is `artifacts/research/<experiment>/experiment_conclusion.md`, with structured companion `experiment_conclusion.json`.
- Future automatic use: a future run does not automatically read prior conclusions before executing; future Codex/local-agent workflows can read them through `session_manifest.json`, `agent_context.md`, and `agent context`.
- Guided workflow previous-result use: `research-plan next` uses previous runs indirectly through `research_index.jsonl`, experiment decision state, and artifact existence checks such as `run_trust_report.md`, `evidence_summary.md`, robustness reports, and `experiment_conclusion.json`.
- Linked versus synthesized: the system does synthesize linked results into evidence labels, supporting/contradicting evidence, do-not-repeat items, and next useful tests; it does not maintain a broader semantic memory across separate experiments.
- Manual interpretation still required: deciding whether a weak/mixed/rejected conclusion is economically meaningful, whether the hypothesis should change, whether corporate-action data assumptions are acceptable, and whether a next experiment is logically new rather than a rerun.

### Worked Example

Run result:

> QQQ SMA crossover reduced drawdown but materially underperformed buy-and-hold.

Storage path:

- Saved data: each run directory stores `metrics.json`, `equity_curve.csv`, `trades.csv`, `run_metadata.json`, `data_quality.json`, `research_warnings.json`, and chart PNGs. The research index stores a flat row with run type, total return, max drawdown, trade count, benchmark total return, excess total return, output directory, and metadata path.
- Saved analysis: `report.md` shows the strategy metrics, benchmark comparison, data quality, and warnings. `summarize-run-trust` can add `run_trust_report.md`. A sweep adds `summary.csv` and `research.md`.
- Saved decision: `decide-experiment` stores a structured decision inside `experiments.jsonl`; `conclude-experiment` stores a deterministic conclusion in `experiment_conclusion.md/json`.
- Reusable research knowledge: `experiment_conclusion.json` contains `current_conclusion`, `do_not_repeat`, `next_useful_tests`, `source_artifacts`, and agent instructions. It is reusable when a future human/Codex/agent reads it; it is not a global memory that automatically blocks future commands.

Effect on next experiment:

- Within the same experiment, `research-plan next` can stop after a recorded decision or move toward conclusion/decision based on artifacts.
- Across a new experiment, nothing automatically says "do not repeat QQQ SMA crossover"; the user or agent must read the prior conclusion and apply it.

## 5. Artifact Inventory

### Raw Evidence

- `data/cache/<SYMBOL>_<start>_<end>.csv`
  - Created by: `quant-lab fetch`.
  - Authoritative: yes for local input data.
  - Duplicates: no, but multiple cached CSVs can overlap.
  - Read when: checking exactly what data was tested.
- `*.provenance.json`
  - Created by: `write_market_data_provenance()`.
  - Authoritative: yes for fetch/provider/fingerprint metadata.
  - Duplicates: overlaps with `run_metadata.data`.
  - Read when: auditing adjusted-price source and data identity.
- `run_metadata.json`
  - Created by: `run_single_backtest()` / `persist_run_record()`.
  - Authoritative: yes for one strategy run.
  - Duplicates: paths and metrics overlap with reports/index rows.
  - Read when: auditing one run or feeding inspection/summary commands.
- `strategy.json`
  - Created by: `save_strategy_payload()` for normal runs and sweep variants.
  - Authoritative: yes for the exact strategy payload passed to that run.
  - Duplicates: source strategy files, but intentionally snapshots the run input.
  - Read when: reproducing or auditing the exact rules that generated a run.
- `metrics.json`
  - Created by: `metrics_reporting.save_run_artifacts()`.
  - Authoritative: yes for computed run metrics.
  - Duplicates: values appear in `report.md`, `run_metadata.json`, and index rows.
  - Read when: machine-comparing one run.
- `equity_curve.csv`
  - Created by: `metrics_reporting.save_run_artifacts()`.
  - Authoritative: yes for run equity series.
  - Duplicates: chart visualizations.
  - Read when: recalculating metrics or plotting.
- `trades.csv`
  - Created by: `save_trades()`.
  - Authoritative: yes for fills.
  - Duplicates: trade count appears elsewhere.
  - Read when: checking execution behavior.
- `data_quality.json`
  - Created by: `save_data_quality_report()`.
  - Authoritative: yes for per-run data checks.
  - Duplicates: summary appears in `report.md`.
  - Read when: evaluating data cleanliness.
- `research_warnings.json`
  - Created by: `save_research_warnings()`.
  - Authoritative: yes for warning flags.
  - Duplicates: warning text appears in `report.md`.
  - Read when: checking weak-sample/trade-count caveats.
- Portfolio raw artifacts: `portfolio_metadata.json`, `portfolio_metrics.json`, `portfolio_equity_curve.csv`, `portfolio_positions.csv`, `portfolio_trades.csv`, `portfolio_allocation_drift.csv`.
  - Created by: `portfolio-run`.
  - Authoritative: yes for one portfolio run.
  - Duplicates: metrics and paths appear in portfolio reports/index rows.
  - Read when: auditing portfolio execution and allocation behavior.

### Derived Analysis

- `report.md`
  - Created by: `run`.
  - Authoritative: main human entry point for one run, but not the machine source.
  - Duplicates: metrics, benchmark, data quality, warnings.
  - Read when: first inspecting one run.
- `equity_curve.png`, `drawdown.png`
  - Created by: `save_charts()`.
  - Authoritative: no, visual derivative.
  - Duplicates: `equity_curve.csv`.
  - Read when: visually scanning behavior.
- `run_trust_report.md`
  - Created by: `summarize-run-trust`.
  - Authoritative: supporting trust analysis.
  - Duplicates: data provenance/fingerprint/data-quality checks.
  - Read when: before widening a branch.
- Sweep `summary.csv`
  - Created by: `sweep`.
  - Authoritative: yes for sweep table.
  - Duplicates: child run metadata.
  - Read when: selecting/diagnosing parameter variants.
- Sweep `research.md`
  - Created by: `sweep`.
  - Authoritative: main human entry point for one sweep.
  - Duplicates: `summary.csv`.
  - Read when: first inspecting a sweep.
- Robustness reports: `cost_sensitivity_report.md`, `date_sensitivity_report.md`, `benchmark_sensitivity_report.md`, `parameter_neighborhood_report.md`.
  - Created by: `robustness ...`.
  - Authoritative: supporting interpretation for robustness.
  - Duplicates: child run metadata and summary CSVs.
  - Read when: deciding if evidence survives perturbation.
- Guardrail reports: `sweep_guardrails.md`, `portfolio_batch_summary.md`.
  - Created by: `summarize-sweep-guardrails` and `portfolio-batch summarize`.
  - Authoritative: supporting warning layer.
  - Duplicates: summary CSVs/manifests.
  - Read when: checking whether a sweep/batch is too broad or weak.

### Experiment-Level Knowledge

- `research_plan.json` / `research_plan.md`
  - Created by: `research-plan init`.
  - Authoritative: yes for intended hypothesis/configuration.
  - Duplicates: experiment registry fields and session manifest.
  - Read when: starting/resuming workflow.
- `experiments.jsonl`
  - Created/updated by: experiment commands and run linking.
  - Authoritative: yes for experiment registry and decisions.
  - Duplicates: plan/title/status and linked metadata paths.
  - Read when: auditing decisions/links.
- `research_index.jsonl`
  - Created by: run/sweep/robustness/portfolio execution.
  - Authoritative: yes as flat run index, no as detailed run source.
  - Duplicates: selected fields from run metadata.
  - Read when: finding/comparing runs.
- `evidence_summary.md`
  - Created by: `summarize-experiment`.
  - Authoritative: supporting interpretation, not final truth.
  - Duplicates: conclusion and index rows.
  - Read when: understanding linked evidence before conclusion.
- `experiment_conclusion.md` / `experiment_conclusion.json`
  - Created by: `conclude-experiment`.
  - Authoritative: main full-experiment source of truth.
  - Duplicates: selected evidence summary content.
  - Read when: deciding what was learned and what not to repeat.
- `agent_context.md`
  - Created by: `conclude-experiment`.
  - Authoritative: no; adapter for agents.
  - Duplicates: conclusion fields.
  - Read when: prompting Codex/local agent.
- `session_manifest.json` / `session_manifest.md`
  - Created by: `session refresh`, smoke test, conclusion/decision updates.
  - Authoritative: workflow orientation, not conclusion.
  - Duplicates: plan, conclusion path, key artifact paths, next command.
  - Read when: resuming a workflow.
- `agent_context_bundle.json/md`, `agent_recommendation.json/md`, `agent_cycle.json/md`
  - Created by: `agent context`, `agent suggest`, `agent cycle --dry-run`.
  - Authoritative: no for research; yes for advisor audit trail.
  - Duplicates: manifest/conclusion/recommendation content.
  - Read when: inspecting local-agent advice.

Main entry points:

- One run: `report.md` for human reading, `run_metadata.json` for authoritative machine audit.
- One sweep: `research.md` for human reading, `summary.csv` for authoritative sweep table.
- One full experiment: `experiment_conclusion.md` for human reading, `experiment_conclusion.json` for agent/tool reading. `session_manifest.md` is the resume entry point, not the conclusion.

## 6. CLI Surface

### Core

- `fetch`: core data preparation; user passes symbol/date/out.
- `run`: core single strategy run; user passes strategy/data/out/experiment/index paths.
- `sweep`: core exploratory parameter grid; user passes strategy/data/out/params and optional validation windows.
- `experiment run-default`: core one-command workflow for baseline, trust, sweep, train/test, robustness, evidence summary, conclusion, and decision.
- `research-plan init`, `research-plan next`: core guided workflow; `next` prints commands but user still copies/runs them.
- `show-run`: core run inspection; requires metadata path.
- `compare-runs`: core comparison; requires multiple metadata paths.
- `summarize-experiment`: core evidence summary; requires experiment/index paths and experiment id.
- `conclude-experiment`: core canonical conclusion; requires experiment/index paths and output dir.
- `decide-experiment`: core decision recording; requires experiment id and decision fields.

### Validation

- `doctor`: environment/dependency/project-file checks.
- `smoke-test`: offline wiring check; `--agent-cycle` verifies deterministic local-agent dry-run.
- `show-data-source`: data/provenance inspection; requires data path.
- `list-data-cache`: cache inventory.
- `audit-adjusted-prices`: focused adjusted-price/corporate-action audit against expected events.
- `verify-run`: fingerprint verification; requires run metadata.
- `summarize-run-trust`: data trust report; requires run metadata.
- `summarize-sweep-guardrails`: sweep warning report; requires sweep summary.
- `robustness cost-sensitivity`: controlled cost reruns.
- `robustness date-sensitivity`: controlled date-window reruns.
- `robustness benchmark-sensitivity`: benchmark substitution reruns.
- `robustness parameter-neighborhood`: parameter stability report from sweep summary.

### Organization

- `list-runs`: index browsing.
- `new-experiment`, `list-experiments`, `show-experiment`, `update-experiment`, `link-run`: registry management.
- `session status`, `session replay-plan`, `session refresh`: workflow orientation/replay without execution.
- `list-strategy-templates`, `new-strategy`: strategy starter files.

### Advanced

- `portfolio-run`, `show-portfolio-run`, `compare-portfolio-runs`, `summarize-portfolio-data-trust`.
- `list-portfolio-templates`, `new-portfolio`, `portfolio-variants`, `portfolio-candidates`.
- `portfolio-plan init`, `portfolio-plan next`.
- `portfolio-batch plan`, `portfolio-batch run`, `portfolio-batch summarize`.
- `summarize-portfolio-experiment`.
- `agent context`, `agent suggest`, `agent cycle`, `agent validate-recommendation`.

### Redundant Candidates

- `summarize-experiment` and `conclude-experiment` overlap as human-facing synthesis; conclusion is clearer as final source of truth.
- `session status` and `session_manifest.md` duplicate orientation.
- `agent_context.md` and `agent_context_bundle.md` overlap conceptually but serve different stages.
- `show-run`, `report.md`, and `run_metadata.json` all answer "what happened in this run" at different levels.

### Legacy Candidates

- None are clearly legacy in code, but several early inspection commands may become secondary if the default workflow is simplified around plan/session/conclusion.

The default single-strategy workflow can run as one command through `experiment run-default`. Advanced, incremental, portfolio, and inspection workflows still mostly require manual path passing. Guided commands print next commands, and session/agent commands package paths, but they do not execute a fully autonomous state machine.

## 7. What Changed Recently

- Strategy-layer risk controls were added. `risk_controls` now supports a strict `volatility_target` control in v1 strategy JSON, and `data/strategies/sma_long_cash_vol_target.json` records the first SPY example. User problem solved: test risk controls in the backtester/strategy layer before asking an agent to invent them. Complexity impact: adds a real strategy feature, but the schema stays narrow and deterministic.
- Normal single runs now save `strategy.json` beside the rest of the run artifacts and record it in `run_metadata.json`. User problem solved: one run is now self-contained enough to audit the exact strategy payload later. Complexity impact: net simplification for reproducibility.
- A real SPY volatility-target drawdown-control experiment was run and documented in `docs/experiments/spy-vol-target-drawdown-control-experiment.md`. User problem solved: the new risk-control feature was tested end to end instead of only proven by unit tests. Complexity impact: reduces research ambiguity by rejecting this exact 12% vol-target branch.
- Research guardrails were documented in `docs/architecture/research-guardrails.md`. User problem solved: prevent the project from responding to each failed backtest by adding a new strategy knob. Complexity impact: reduces future scope creep and freezes agent expansion until more human-reviewed conclusions exist.
- Local-agent advisor path was added: `agent context`, `agent suggest`, `agent cycle --dry-run`, and `agent validate-recommendation` now create strict context/recommendation/cycle artifacts. User problem solved: let a local model recommend the next experiment step without taking over execution. Complexity impact: useful but definitely another layer; dry-run boundary prevents it from becoming dangerous.
- OpenAI-compatible model provider support was added for Ollama-like endpoints. User problem solved: integrate a local model such as `llama3.1:8b`. Complexity impact: adds provider/prompt/schema validation code, justified if local agent iteration is a real goal.
- Model recommendation validation was hardened, including fallback to deterministic advice on invalid model output and command/action mismatch rejection. User problem solved: reduce bad local-model suggestions. Complexity impact: reduces operational risk more than it adds complexity.
- Complete sessions now short-circuit to deterministic `stop` before model calls. User problem solved: avoid wasting model calls and avoid re-opening completed work. Complexity impact: simplifies behavior for done sessions.
- `doctor` and `smoke-test` were added, then `smoke-test --agent-cycle` was added. User problem solved: prove the environment and workflow wiring without internet. Complexity impact: net simplification for onboarding; smoke test is beginning to own orchestration, but current refactor keeps it manageable.
- Runbook docs were added/organized: `docs/runbooks/runbooks.md`, `docs/runbooks/local-agent-runbook.md`, and README links. User problem solved: a future user/Codex session can find commands without reading the whole README. Complexity impact: reduces human complexity, adds some doc duplication that must stay synchronized.
- Recent cleanup refactored CLI agent summary printing and isolated optional smoke-test agent verification. User problem solved: keep fast-moving agent code maintainable. Complexity impact: small reduction.

## 8. Current Strengths

1. Execution timing is explicit and tested. `src/backtester_core/engine.py` queues bar `t` signals and fills on bar `t+1` open; tests include no same-bar fill, next-open fill, gap open, and final-bar no-fill cases in `tests/test_backtester_core.py`.
2. Reproducibility metadata is strong for a small project. `src/quant_lab/run_metadata.py` fingerprints raw data bytes and stores command tokens, costs, sizing, benchmark, git commit, and artifact paths in `run_metadata.json`; `verify-run` tests changed/missing data cases.
3. Reports are auditable back to raw files. `src/quant_lab/run_artifacts.py` writes metrics, equity curve, trades, charts, data quality, warnings, saved strategy payloads, metadata, and research index rows from one execution path.
4. The guided workflow is conservative. `src/quant_lab/research_plan_workflow.py` asks for baseline, trust report, sweep, validation, evidence summary, robustness, conclusion, and decision rather than jumping straight from a good run to a decision.
5. The project has a real offline health path. `quant-lab doctor` and `quant-lab smoke-test --agent-cycle` are implemented and tested; the latest full suite passed `381` tests, and the real smoke command verifies agent dry-run wiring without executing proposed commands.

## 9. Current Weaknesses

1. Information-design problem: too many human-facing reports. `report.md`, `run_trust_report.md`, `research.md`, `sweep_guardrails.md`, robustness reports, `evidence_summary.md`, `experiment_conclusion.md`, `session_manifest.md`, and agent Markdown files all compete unless the reader already knows the hierarchy.
2. Architecture/usability problem: workflow automation is split between one-command default flow and many lower-level commands. `experiment run-default` is coherent, but `research-plan next` and advanced workflows still require users to pass paths/ids/metadata; this is transparent but verbose.
3. Missing research capability: prior conclusions are not automatically reusable across experiments. `experiment_conclusion.json` stores do-not-repeat and next-useful-test fields, but new plans/runs do not query a cross-experiment knowledge base.
4. Correctness problem: adjusted prices, dividends, and splits are not directly modeled by the engine. Fetch uses `yfinance` `auto_adjust=True` and `actions=False`; the 2024 SPY dividend window now has a provider-internal adjusted OHLC audit, but there is still no independent second-source validation.
5. Missing research capability: risk controls are still narrow. The strategy schema supports `volatility_target`, but it does not yet support partial-exposure regimes, drawdown stops, trailing exits, cooldowns, or stacked controls with rich reporting.

## 10. One Concrete Experiment Walkthrough

This walkthrough uses only current capabilities.

1. Data preparation.
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli fetch `
     --symbol SPY `
     --start 2015-01-01 `
     --end 2025-12-31 `
     --out data/cache
   ```
   Creates normalized adjusted daily OHLCV CSV and provenance sidecar.

2. Strategy creation or strategy file used.
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli new-strategy `
     --template sma-long-cash `
     --symbol SPY `
     --length 200 `
     --strategy-id spy_sma_200_long_cash `
     --name "SPY 200-day SMA long/cash" `
     --out artifacts\research\spy_200d_long_cash\spy_sma_200_long_cash.json
   ```
   Creates the exact one-indicator SMA-200 long/cash rule.

3. Baseline run.
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli research-plan init `
     --title "SPY 200-day long/cash trend" `
     --hypothesis "A daily SPY close-above-200-day-SMA long/cash rule may improve drawdown-adjusted performance versus SPY buy-and-hold after realistic costs." `
     --strategy artifacts\research\spy_200d_long_cash\spy_sma_200_long_cash.json `
     --data data/cache\SPY_2015-01-01_2025-12-31.csv `
     --symbol SPY `
     --cost-preset retail-liquid `
     --out artifacts\research\spy_200d_long_cash
   ```
   Creates plan/registry/index files and prints the baseline `run` command.

   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli run `
     --strategy artifacts\research\spy_200d_long_cash\spy_sma_200_long_cash.json `
     --data data/cache\SPY_2015-01-01_2025-12-31.csv `
     --out artifacts\research\spy_200d_long_cash\baseline `
     --initial-cash 100000 `
     --sizing percent-equity `
     --allocation 1.0 `
     --benchmark buy-and-hold `
     --cost-preset retail-liquid `
     --experiments-path artifacts\research\spy_200d_long_cash\experiments.jsonl `
     --experiment-id EXP-001 `
     --index-path artifacts\research\spy_200d_long_cash\research_index.jsonl `
     --note "Baseline for SPY 200-day long/cash trend hypothesis."
   ```
   Creates the baseline run artifacts and links a run row to the experiment.

4. Main report to inspect.
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli show-run `
     --metadata artifacts\research\spy_200d_long_cash\baseline\run_metadata.json
   ```
   Creates no new artifact; prints one-run summary. Read `baseline/report.md` for human interpretation and `baseline/run_metadata.json` for audit.

5. Cost sensitivity.
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli robustness cost-sensitivity `
     --strategy artifacts\research\spy_200d_long_cash\spy_sma_200_long_cash.json `
     --data data/cache\SPY_2015-01-01_2025-12-31.csv `
     --out artifacts\research\spy_200d_long_cash\robustness\costs `
     --sizing percent-equity `
     --allocation 1.0 `
     --cost-preset none `
     --cost-preset retail-liquid `
     --cost-preset retail-conservative `
     --benchmark buy-and-hold `
     --experiments-path artifacts\research\spy_200d_long_cash\experiments.jsonl `
     --experiment-id EXP-001 `
     --index-path artifacts\research\spy_200d_long_cash\research_index.jsonl
   ```
   Creates child runs plus `cost_sensitivity_summary.csv` and `cost_sensitivity_report.md`.

6. Date sensitivity.
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli robustness date-sensitivity `
     --strategy artifacts\research\spy_200d_long_cash\spy_sma_200_long_cash.json `
     --data data/cache\SPY_2015-01-01_2025-12-31.csv `
     --out artifacts\research\spy_200d_long_cash\robustness\dates `
     --window 2015-01-01,2019-12-31 `
     --window 2020-01-01,2025-12-31 `
     --sizing percent-equity `
     --allocation 1.0 `
     --cost-preset retail-liquid `
     --benchmark buy-and-hold `
     --experiments-path artifacts\research\spy_200d_long_cash\experiments.jsonl `
     --experiment-id EXP-001 `
     --index-path artifacts\research\spy_200d_long_cash\research_index.jsonl
   ```
   Creates date-window child runs plus `date_sensitivity_summary.csv` and `date_sensitivity_report.md`.

7. Train/test or walk-forward validation.
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli sweep `
     --strategy artifacts\research\spy_200d_long_cash\spy_sma_200_long_cash.json `
     --data data/cache\SPY_2015-01-01_2025-12-31.csv `
     --out artifacts\research\spy_200d_long_cash\train_test_001 `
     --param sma_200.inputs.length=150,175,200,225,250 `
     --train-end 2019-12-31 `
     --test-start 2020-01-01 `
     --select-by sharpe_ratio `
     --sizing percent-equity `
     --allocation 1.0 `
     --benchmark buy-and-hold `
     --cost-preset retail-liquid `
     --experiments-path artifacts\research\spy_200d_long_cash\experiments.jsonl `
     --experiment-id EXP-001 `
     --index-path artifacts\research\spy_200d_long_cash\research_index.jsonl
   ```
   Creates train sweep runs, selected test run, `summary.csv`, `test_summary/summary.csv`, and `research.md`. Blocker risk: the parameter path must match the actual indicator id in the JSON.

   Optional walk-forward:
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli sweep `
     --strategy artifacts\research\spy_200d_long_cash\spy_sma_200_long_cash.json `
     --data data/cache\SPY_2015-01-01_2025-12-31.csv `
     --out artifacts\research\spy_200d_long_cash\walk_forward_001 `
     --param sma_200.inputs.length=150,175,200,225,250 `
     --walk-forward-window 2015-01-01,2017-12-31,2018-01-01,2019-12-31 `
     --walk-forward-window 2018-01-01,2020-12-31,2021-01-01,2022-12-31 `
     --walk-forward-window 2020-01-01,2022-12-31,2023-01-01,2025-12-31 `
     --select-by sharpe_ratio `
     --sizing percent-equity `
     --allocation 1.0 `
     --benchmark buy-and-hold `
     --cost-preset retail-liquid `
     --experiments-path artifacts\research\spy_200d_long_cash\experiments.jsonl `
     --experiment-id EXP-001 `
     --index-path artifacts\research\spy_200d_long_cash\research_index.jsonl
   ```
   Creates windowed train/test run artifacts and `walk_forward_summary.csv`.

8. Experiment summary or final conclusion.
   ```powershell
   .\.venv-win\Scripts\python.exe -m quant_lab.cli summarize-experiment `
     --experiments-path artifacts\research\spy_200d_long_cash\experiments.jsonl `
     --index-path artifacts\research\spy_200d_long_cash\research_index.jsonl `
     --experiment-id EXP-001 `
     --out artifacts\research\spy_200d_long_cash\evidence_summary.md

   .\.venv-win\Scripts\python.exe -m quant_lab.cli conclude-experiment `
     --experiments-path artifacts\research\spy_200d_long_cash\experiments.jsonl `
     --index-path artifacts\research\spy_200d_long_cash\research_index.jsonl `
     --experiment-id EXP-001 `
     --out artifacts\research\spy_200d_long_cash `
     --force
   ```
   Creates supporting evidence summary and canonical conclusion files. Read `experiment_conclusion.md` first.

## 11. Test and Correctness Status

- Command used: `.\.venv-win\Scripts\python.exe -m unittest discover -s tests`
- Passed tests: `381`
- Failed tests: `0`
- Skipped tests: `0` observed in unittest output.
- Test duration: `18.168s`

Coverage assessment:

- Next-open execution: directly tested in `tests/test_backtester_core.py` and `tests/test_portfolio_backtest.py`.
- No same-bar look-ahead: directly tested by no same-bar fill and incremental indicator tests.
- Final-bar signals: directly tested for single strategy and portfolio rebalance.
- Cash exits: partially tested through sell/position accounting and long/cash strategy behavior; not all edge cases around partial liquidation are exhaustive.
- Percent-equity sizing: directly tested in core execution, rule strategy, and CLI run tests.
- Commissions: directly tested in portfolio accounting, execution model, CLI cost options, and cost presets.
- Slippage: directly tested in execution model and CLI cost option paths.
- Adjusted price handling: indirectly implemented by `yfinance` `auto_adjust=True`; a real SPY 2024 dividend-window audit passed with `0.0` max close difference against yfinance raw `Adj Close` and `0.0` max adjusted-OHLC difference against raw OHLC multiplied by the provider adjustment ratio.
- Dividends: not directly modeled as cash flows; the SPY 2024 audit found the expected 2024 dividend dates in provider action rows and confirmed adjusted close consistency for that window.
- Splits: not directly modeled or tested; assumed folded into adjusted OHLC by provider.
- Benchmark alignment: directly tested for buy-and-hold/cash metrics and portfolio benchmark date alignment; single-symbol benchmark starts from the input series.
- Indicator warm-up: directly tested for incremental indicators returning `None` before enough data and no trades during unavailable indicator periods.
- Train/test separation: tests reject overlapping dates and cover selected train winner rerun on test data; correctness still depends on user-chosen split dates.
- Walk-forward selection: tests cover explicit windows and overlapping-window rejection; no automated economic validation of chosen windows.
- Data fingerprint verification: directly tested by `fingerprint_file()` and `verify-run` changed/missing data cases.
- Experiment linking: directly tested by run linking, registry updates, experiment summaries, and conclusion building.

Do not infer market correctness from the test count. The suite strongly checks deterministic plumbing and many accounting assumptions, but it does not prove the economic validity of any strategy or the provider-specific handling of corporate actions.

## 12. Reviewer Questions

1. Is the project currently useful for disciplined daily-data quant research?
   - Yes, for small long-only daily-data studies where transparency matters more than breadth. The SPY and QQQ generated artifacts show the workflow can reach a conclusion.
2. Is it over-engineered relative to its strategy capabilities?
   - Partly. The research-management layer is richer than the current strategy language, which still handles simple rule-based long-only strategies.
3. Are findings merely stored, or are they turned into reusable knowledge?
   - Both, but not fully automatically. Findings are synthesized into `experiment_conclusion.json/md`, do-not-repeat items, and next useful tests, but reuse depends on humans/Codex/agents reading those artifacts.
4. Do the pieces work together coherently?
   - Mostly yes. Data -> strategy -> run -> metadata/index -> summary/conclusion -> session/agent context is coherent, and `experiment run-default` proves the main path can be orchestrated. Advanced paths still involve enough manual path passing to feel more complex than they are.
5. Where does the workflow create unnecessary human-facing noise?
   - Around run reports, trust reports, sweep research, guardrails, evidence summaries, conclusions, session manifests, and agent Markdown files. The hierarchy exists but is not obvious without docs.
6. What should be simplified next?
   - Make the default one-experiment path more command-driven and reduce duplicated human reports by clearly elevating `session_manifest.md` for orientation and `experiment_conclusion.md` for conclusion.
7. What should not be removed?
   - `run_metadata.json`, `research_index.jsonl`, `experiment_conclusion.json/md`, next-open execution tests, data fingerprints, trust reports, and explicit benchmark/cost assumptions.
8. What is the single highest-priority correctness audit?
   - Second-source corporate-action validation: the provider-internal SPY 2024 adjusted-OHLC dividend audit passed, but the lab still needs either another provider or a broader known-event test before treating adjusted-price behavior as fully de-risked.
9. What is the single best next real experiment?
   - A partial-exposure SPY trend experiment, because the latest SMA long/cash and SMA plus 12% volatility-target tests both reduced drawdown but failed return-retention thresholds.
10. Is the project ready for further feature development, or should development pause for consolidation?
    - Pause feature expansion. The core is useful; the next work should audit price/benchmark economics before adding more strategy primitives or local-agent capabilities.

