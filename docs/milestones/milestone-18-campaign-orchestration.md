# Milestone 18: Campaign Orchestration

Status: in progress.

## Goal

Add a bounded research campaign controller that repeatedly runs existing
research workflows without giving an agent ownership of the codebase.

The destination command is:

```bash
quant-lab campaign run \
  --provider codex \
  --duration 60m \
  --max-cycles 5 \
  --max-total-runs 55 \
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

Current progress:

- `campaign_config.json`, `campaign_state.json`, and `campaign_state.md`
  persistence exists.
- `quant-lab campaign init` creates campaign state.
- `quant-lab campaign status` prints compact orientation.
- `quant-lab campaign run` can create a deterministic proposal, validate it,
  save cycle artifacts, execute one default workflow, and update campaign
  memory.

### 18B: Proposal Contract And Validation

Define `campaign_proposal.v1` with permitted actions:

- `run_experiment`
- `request_human_review`
- `stop_campaign`

Validate allowed templates, symbols, parameters, success criteria, data paths,
budgets, material difference from prior work, and `do_not_repeat` constraints.

Exit criterion: invalid proposals are saved, rejected with reasons, retried at
most once, then stop or fall back deterministically.

Current progress:

- `campaign_proposal.v1` exists for `run_experiment`, `request_human_review`,
  and `stop_campaign`.
- `campaign_validation.v1` saves valid/rejected status, reasons, and projected
  run count.
- The deterministic provider proposes the first SPY SMA 200 long/cash campaign
  baseline.
- Validation checks allowed template, allowed symbol, supported parameters,
  required local data, success criteria, budget, and campaign `do_not_repeat`.
- Valid `run_experiment` proposals are converted into cycle-local
  `strategy.json`, `run_default_args.json`, and `run_default_command.md`
  handoff artifacts.

Still missing:

- retry-on-invalid behavior,
- material-difference checks beyond simple `do_not_repeat`.

### 18C: One Real Campaign Cycle

Convert a valid proposal into existing workflow inputs and call
`experiment run-default`. Do not reimplement backtesting, sweeps, robustness, or
conclusions.

Exit criterion: one cycle runs an existing experiment workflow and reads
`experiment_conclusion.json`.

Current progress:

- Conversion-only handoff is implemented in `src/quant_lab/campaign_conversion.py`.
- `quant-lab campaign run` now writes planned default-workflow inputs under the
  cycle directory after proposal validation succeeds.
- `src/quant_lab/campaign_execution.py` executes the generated
  `experiment run-default` arguments through the existing Python workflow.
- Each executed cycle writes `campaign_execution.json` and
  `campaign_execution.md`, including the experiment id, readable conclusion, and
  machine-readable `experiment_conclusion.json`.

Still missing:

- retry-on-invalid behavior before execution.

### 18D: Campaign Knowledge Update

After each conclusion, update completed experiments, current findings,
`do_not_repeat`, unresolved questions, runs used, elapsed time, and remaining
budget.

Exit criterion: cycle 2 demonstrably uses cycle 1's conclusion and avoids a
rejected branch.

Current progress:

- Completed executions update `campaign_state.json` and `campaign_state.md`.
- Campaign state records completed experiment id, title, research-system
  status, strategy-hypothesis status, confidence label, conclusion paths,
  projected run count, and elapsed seconds.
- Conclusion `current_conclusion`, `do_not_repeat`, and `open_questions` are
  carried into campaign-level memory.
- Rejected strategy hypotheses add an explicit unchanged-branch guardrail so a
  resumed deterministic campaign does not rerun the same failed proposal.
- The deterministic provider can propose an EMA 50 plus RSI trend-follow
  follow-up after the SMA 200 long/cash baseline has been tested.
- A resume smoke check ran the SMA 200 baseline, then the EMA 50 plus RSI
  follow-up, then produced a `stop_campaign` proposal once the deterministic
  sequence was exhausted.
- Campaign proposal generation now goes through `src/quant_lab/campaign_provider.py`
  so future Ollama and Codex adapters can return the same strict proposal
  contract without taking over execution.

Still missing:

- a smarter deterministic fallback proposal after the first branch is blocked,
- retry-on-invalid behavior,
- richer material-difference checks across non-identical proposals.

### 18E: Final Campaign Report

Write `final_report.md` and `final_report.json` with attempted experiments,
invalid proposals, supported/rejected/inconclusive hypotheses, cumulative
findings, consumed budgets, unresolved risks, and stop reason.

Exit criterion: stopped campaigns leave one readable front-door report.

Current progress:

- `stop_campaign` marks campaign state complete and writes `final_report.md`
  plus `final_report.json`.
- The final report summarizes attempted experiments, research-system statuses,
  strategy-hypothesis outcomes, cumulative findings, `do_not_repeat`,
  unresolved risks, consumed budget, remaining budget, and why the campaign
  stopped.
- The report labels the best remaining candidate cautiously and does not claim
  that a partially supported strategy is investable.

### 18F: Ollama Provider

Reuse the existing OpenAI-compatible provider boundary, but return the campaign
proposal schema instead of an agent recommendation schema.

Exit criterion: a bounded three-cycle campaign can run with `--provider ollama`
without unsupported actions.

Current progress:

- `src/quant_lab/campaign_provider.py` now builds a structured campaign context
  and prompt for the Ollama provider.
- Ollama uses the existing OpenAI-compatible HTTP pattern and asks for
  `campaign_proposal.v1`.
- A model dry run writes `provider_context.json`, `provider_prompt.md`,
  `provider_raw_response.txt`, and `provider_proposal.json` under the cycle
  attempt directory.
- The parsed proposal is validated by the same deterministic validator.
- `quant-lab campaign run` deliberately skips execution for non-deterministic
  providers in this slice, so a model can be inspected before it spends
  backtest budget.
- Invalid or failed model attempts are saved under `provider_attempt_001/` and
  `provider_attempt_002/`.
- Attempt 2 receives `prior_attempt_feedback` containing the first attempt's
  provider error or validation reasons.
- If both model attempts fail, the controller writes a deterministic fallback
  proposal for inspection only. Because the campaign provider is still `ollama`,
  execution remains skipped.
- A valid model-originated `run_experiment` proposal can execute only when the
  user passes `--execute-model-proposal`. Dry-run remains the default.
- Deterministic fallback proposals remain inspection-only even when
  `--execute-model-proposal` is passed.
- `quant-lab campaign run --loop` can now run repeated cycles through the same
  proposal, validation, execution, conclusion, and state-update path until a
  stop condition is reached.

Still missing:

- real successful multi-cycle Ollama smoke with the local model responding
  within timeout.

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
- max total runs: `33`,
- max variants per experiment: `3`,
- duration: `30m`.

Not allowed in the first campaign:

- new indicators,
- source changes,
- portfolio rotation,
- shorting,
- leverage,
- broad parameter mining.
