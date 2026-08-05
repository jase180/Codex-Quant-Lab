# Milestone 18: Campaign Orchestration

Status: planned, first skeleton slice in progress.

## Goal

Add a bounded research campaign controller that repeatedly runs existing
research workflows without giving an agent ownership of the codebase.

The destination command is:

```bash
quant-lab campaign run \
  --provider codex \
  --duration 60m \
  --max-cycles 5 \
  --max-total-runs 30 \
  --out artifacts/campaigns/spy_research_001
```

The controller owns state, budgets, validation, execution, retries, stopping,
and artifact persistence. Providers only propose one strict next action.

## Design Boundary

Campaign execution may:

- read accumulated conclusions and campaign state,
- ask a provider for one structured proposal,
- validate the proposal,
- convert a valid proposal into existing strategy or portfolio inputs,
- call existing experiment workflows,
- read canonical conclusions,
- update campaign knowledge.

Campaign execution must not:

- modify source code,
- invent new indicators or strategy features,
- run unrestricted shell commands,
- change success criteria after seeing results,
- repeat rejected branches,
- silently expand parameter grids.

## Roadmap

### 18A: Offline Campaign Skeleton

Build state files, `campaign init`, `campaign status`, deterministic provider
plumbing, budget fields, and resume-safe file layout. No model provider and no
full experiment loop yet.

Exit criterion: campaign config and state can be created, inspected, and resumed
without losing budget or objective context.

### 18B: Proposal Contract And Validation

Define `campaign_proposal.v1` with permitted actions:

- `run_experiment`
- `request_human_review`
- `stop_campaign`

Validate allowed templates, symbols, parameters, success criteria, data paths,
budgets, material difference from prior work, and `do_not_repeat` constraints.

Exit criterion: invalid proposals are saved, rejected with reasons, retried at
most once, then stop or fall back deterministically.

### 18C: One Real Campaign Cycle

Convert a valid proposal into existing workflow inputs and call
`experiment run-default`. Do not reimplement backtesting, sweeps, robustness, or
conclusions.

Exit criterion: one cycle runs an existing experiment workflow and reads
`experiment_conclusion.json`.

### 18D: Campaign Knowledge Update

After each conclusion, update completed experiments, current findings,
`do_not_repeat`, unresolved questions, runs used, elapsed time, and remaining
budget.

Exit criterion: cycle 2 demonstrably uses cycle 1's conclusion and avoids a
rejected branch.

### 18E: Final Campaign Report

Write `final_report.md` and `final_report.json` with attempted experiments,
invalid proposals, supported/rejected/inconclusive hypotheses, cumulative
findings, consumed budgets, unresolved risks, and stop reason.

Exit criterion: stopped campaigns leave one readable front-door report.

### 18F: Ollama Provider

Reuse the existing OpenAI-compatible provider boundary, but return the campaign
proposal schema instead of an agent recommendation schema.

Exit criterion: a bounded three-cycle campaign can run with `--provider ollama`
without unsupported actions.

### 18G: Codex Provider

Codex returns proposal JSON only. The campaign controller still owns execution
and state. Codex must not edit source files during campaign execution.

Exit criterion: switching provider from Ollama to Codex does not change
campaign logic.

### 18H: Timed Campaigns

Add `--duration`, graceful stop, resume support, and interruption-safe final
reports.

Exit criterion: a 30-minute proving campaign can stop safely and resume before
trusting a 60-minute campaign.

## First Campaign Scope

Keep the first real campaign narrow:

- objective: simple SPY drawdown-control research,
- allowed symbols: `SPY`,
- allowed templates: `sma-long-cash`, `ema-trend-follow`,
- benchmark: `buy-and-hold`,
- cost preset: `retail-liquid`,
- max cycles: `3`,
- max total runs: `20`,
- max variants per experiment: `3`,
- duration: `30m`.

Not allowed in the first campaign:

- new indicators,
- source changes,
- portfolio rotation,
- shorting,
- leverage,
- broad parameter mining.
