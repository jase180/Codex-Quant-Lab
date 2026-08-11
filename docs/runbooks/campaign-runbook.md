# Campaign Runbook

Use this runbook when you want the lab to run a bounded sequence of experiments
without giving an agent permission to edit code or invent unsupported strategy
features.

## Current Boundary

`quant-lab campaign run` currently has three provider modes:

- `deterministic`: proposes, validates, executes one campaign cycle, reads the
  canonical conclusion, and updates campaign memory.
- `ollama`: asks a local OpenAI-compatible Ollama model for one strict proposal,
  saves the provider context/prompt/raw response/proposal, validates it, and
  stops before execution. This is a dry-run safety step. If the first model
  attempt fails or validates false, the controller allows one retry with the
  prior error or validation reasons in the second context. If the retry also
  fails, it writes a deterministic fallback proposal for inspection only.
- `codex`: writes the same provider context and prompt artifacts, returns a
  valid `request_human_review` handoff proposal, and stops. The standalone CLI
  does not call the current Codex chat session.

Deterministic run commands execute one campaign cycle:

1. Read `campaign_config.json` and `campaign_state.json`.
2. Read relevant `data/opportunity_catalog/*.json` theses for the campaign's
   allowed templates.
3. Propose one bounded experiment.
4. Validate the proposal against allowed templates, data, budgets, and
   `do_not_repeat` memory.
5. Convert the proposal into the existing `experiment run-default` workflow.
6. Execute that workflow.
7. Read `experiment_conclusion.json`.
8. Update `campaign_state.json` and `campaign_state.md`.

For model-backed providers, `provider_context.json` includes compact
opportunity-thesis summaries. The provider can name an `opportunity_thesis_id`
in its strict proposal, but the controller still owns validation, conversion,
execution, budgets, and stopping. The thesis is context for choosing the next
experiment; it is not executable strategy JSON.

The same context also includes `forbidden_proposals`, a compact list of already
completed experiment titles and thesis outcomes. Treat that list as anti-examples
for the model: a valid provider should not repeat the same title, unchanged
template/parameter branch, or rejected experiment. The prompt intentionally does
not include a copyable strategy-specific JSON example, because local models can
otherwise parrot the example instead of using campaign memory.

When a proposal cites `opportunity_thesis_id`, validation checks that the thesis
exists in `data/opportunity_catalog/`, is marked `decision: test_now`, has
`engine_fit: ready`, and is compatible with the proposed strategy template's
strategy family. A provider cannot cite a blocked event-data thesis to justify a
currently supported SPY trend-template run.

Validation also rejects obvious prompt-example placeholder text in the
hypothesis, rationale, or difference-from-prior-work fields. This prevents a
model from returning syntactically valid JSON that merely copies the example
instead of making a real proposal.

Non-run actions are also validated. `request_human_review` and `stop_campaign`
must not include partial executable experiment fields such as `symbol`,
`strategy_template`, `parameters`, `success_criteria`, or `validation_plan`.
`request_human_review` may still include `opportunity_thesis_id` when the model
is asking a human to review a specific thesis rather than proposing a run.
`stop_campaign` must leave the thesis ID empty.

For executed campaign experiments, the thesis ID is also carried into the
generated `experiment run-default` command as an `opportunity:<id>` experiment
tag. That tag appears in the canonical `experiment_conclusion.json`, and
campaign memory copies it into `completed_experiments[].opportunity_thesis_id`
for the next cycle.

Campaign-safe template metadata lives in `src/quant_lab/campaign_templates.py`.
When adding a template to campaign execution, update that one mapping so provider
context and proposal validation keep using the same strategy-family relationship.

When the deterministic sequence is exhausted, it writes `final_report.md` and
`final_report.json`. Ollama dry runs do not update campaign state or consume
backtest budget yet.

The campaign runner must not modify source code, add indicators, change success
criteria after seeing results, or silently expand parameter grids.

## First SPY Campaign

The checked-in sample config is:

```text
data/campaigns/spy_drawdown_control_campaign.json
```

It intentionally allows only:

- symbol: `SPY`
- templates: `sma-long-cash`, `ema-trend-follow`
- benchmark: `buy-and-hold`
- cost preset: `retail-liquid`
- max cycles: `3`
- max total runs: `33`

The `33` run budget matters because each current default workflow cycle projects
`11` backtests. A smaller budget can make later valid proposals impossible.

## Run The Campaign

Start a fresh campaign:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_drawdown_control_campaign.json `
  --out artifacts\campaigns\spy_research_001 `
  --force
```

Resume for the next cycle:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --out artifacts\campaigns\spy_research_001 `
  --resume
```

Run the resume command until it writes:

```text
final_report: artifacts\campaigns\spy_research_001\final_report.md
```

Or let the controller keep running cycles until a stop condition:

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

`--loop` reuses the same one-cycle machinery. It stops when the campaign state
is no longer `running`, a proposal is invalid, a provider dry run is reached, a
`stop_campaign` proposal writes the final report, or the safety iteration cap is
hit.

Budget overrides are only applied when initializing a new campaign with
`--config`. They are written into the saved `campaign_config.json` and initial
`campaign_state.json`. Resumed campaigns use their saved budgets; the CLI
rejects budget overrides on `--resume` so the state and config cannot drift.
The same rule applies to `--provider`: it can set the provider when creating a
new campaign, but resumed campaigns use the saved provider.

Supported duration forms:

```text
30m
1h
90s
30
```

Bare numbers mean minutes. Seconds are rounded up to the nearest minute because
campaign config stores duration in minutes.

## Generate Candidate Menu

Use this when you want to inspect the deterministic search space before asking a
model provider to choose anything:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign candidates `
  --campaign artifacts\campaigns\spy_research_001
```

The command reads:

- `campaign_config.json`
- `campaign_state.json`
- `data/opportunity_catalog/*.json`
- `data/experiment_template_catalog/*.json`
- `data/parameter_neighborhoods/*.json`

It writes:

```text
artifacts/campaigns/<campaign>/cycles/cycle_NNN/candidate_menu.json
artifacts/campaigns/<campaign>/cycles/cycle_NNN/candidate_menu.md
```

`candidate_menu.json` is the future provider input. `candidate_menu.md` is the
human front door.

If the output status is:

```text
SEARCH_SPACE_EXHAUSTED
```

that is a valid research result. It means the current campaign scope has no
remaining valid, non-duplicate, prespecified candidates after completed titles
and `do_not_repeat` constraints are applied. Do not treat it as a CLI failure.

## Choose From Candidate Menu

Use this after inspecting the candidate menu and before integrating candidates
into `campaign run`:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign choose-candidate `
  --campaign artifacts\campaigns\spy_research_001
```

The command:

1. regenerates the deterministic candidate menu,
2. asks the campaign's configured provider to choose one candidate ID, request
   human review, or stop,
3. validates the choice,
4. writes choice artifacts,
5. converts a valid `choose_candidate` result into a normal
   `campaign_proposal.v1`,
6. stops before execution.

Useful files:

```text
artifacts/campaigns/<campaign>/cycles/cycle_NNN/candidate_menu.md
artifacts/campaigns/<campaign>/cycles/cycle_NNN/candidate_choice.json
artifacts/campaigns/<campaign>/cycles/cycle_NNN/candidate_choice_validation.md
artifacts/campaigns/<campaign>/cycles/cycle_NNN/proposal_validation.md
```

For Ollama-backed campaigns:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign choose-candidate `
  --campaign artifacts\campaigns\spy_ollama_research_001 `
  --model llama3.1:8b `
  --timeout-seconds 120
```

Ollama now receives `campaign_candidate_choice.v1`, not a full freeform
experiment proposal. It may only choose an existing `candidate_id`,
`request_human_review`, or `stop_campaign`. Invalid choices are saved and retried
once with validation feedback.

## Ollama Proposal Dry Run

Use this only to inspect whether a local model can produce a valid bounded
proposal. The command saves and validates the proposal but does not generate
strategy files, run backtests, update campaign state, or write conclusions.

Use the base campaign config and set the provider at initialization:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_drawdown_control_campaign.json `
  --provider ollama `
  --out artifacts\campaigns\spy_ollama_dry_run_001 `
  --model llama3.1:8b `
  --force
```

The useful files are:

```text
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_001/provider_context.json
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_001/provider_prompt.md
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_001/provider_raw_response.txt
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_001/provider_proposal.json
artifacts/campaigns/<campaign>/cycles/cycle_001/proposal_validation.md
```

If a retry happens, inspect:

```text
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_002/provider_context.json
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_002/proposal_validation.md
```

The second context includes `prior_attempt_feedback`, which is the exact error
or validation failure the model was asked to correct.

For resumed seeded dry runs, also inspect `forbidden_proposals` inside
`provider_context.json`. If the model repeats one of those titles, the controller
should reject it with:

```text
proposal appears to violate do_not_repeat campaign memory
```

If the model cannot find a clean next run, a valid `request_human_review` is an
acceptable result. That is a request for human judgment, not a failed campaign
run.

If the proposal is valid, the CLI prints:

```text
execution: skipped_provider_dry_run
```

That is expected. Dry-run remains the default even though explicit execution is
available.

## Execute A Valid Ollama Proposal

After inspecting a dry run, execute a valid model proposal with an explicit
opt-in:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_drawdown_control_campaign.json `
  --provider ollama `
  --out artifacts\campaigns\spy_ollama_exec_001 `
  --model llama3.1:8b `
  --execute-model-proposal `
  --force
```

This still does not let the model run shell commands or edit source. The model
returns one proposal; Python validates it; only then does the controller convert
it into the existing `experiment run-default` workflow.

If both model attempts fail and the controller writes a deterministic fallback,
`--execute-model-proposal` still does not execute it. Fallback proposals are for
inspection only.

`--loop` can be combined with `--execute-model-proposal`, but it still stops on
provider dry runs, invalid proposals, deterministic fallbacks, or exhausted
campaign state. In practice, use one dry-run cycle first, then a short explicit
execution loop only after inspecting the provider artifacts.

## Codex Handoff

Use this when you want Codex to inspect the exact campaign context but do not
want the standalone campaign CLI to pretend it can control this chat session:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_drawdown_control_campaign.json `
  --provider codex `
  --out artifacts\campaigns\spy_codex_handoff_001 `
  --force
```

The command writes:

```text
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_001/provider_context.json
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_001/provider_prompt.md
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_001/provider_proposal.json
artifacts/campaigns/<campaign>/cycles/cycle_001/proposal_validation.md
```

It prints:

```text
execution: skipped_human_review
```

That means the handoff is ready for a human or this Codex session to review,
but no experiment was executed.

## Current Deterministic Sequence

The deterministic provider currently proposes:

1. `SPY SMA 200 long/cash campaign baseline`
2. `SPY EMA 50 RSI trend-follow campaign follow-up`
3. `stop_campaign`

It stops after those known proposals instead of inventing a third strategy.

## What To Read

During a running campaign, read:

```text
artifacts/campaigns/<campaign>/campaign_state.md
```

For one cycle's proposal gate, read:

```text
artifacts/campaigns/<campaign>/cycles/cycle_001/proposal_validation.md
```

For one cycle's main research conclusion, read:

```text
artifacts/campaigns/<campaign>/cycles/cycle_001/experiment/experiment_conclusion.md
```

After the campaign stops, read:

```text
artifacts/campaigns/<campaign>/final_report.md
```

Treat `final_report.md` as the campaign front door. Use the JSON version for
future automation:

```text
artifacts/campaigns/<campaign>/final_report.json
```

## How To Interpret Results

The campaign keeps two separate outcomes:

- `Research-system status`: whether the repo measured the experiment honestly
  and reproducibly.
- `Strategy-hypothesis status`: whether the strategy met its prespecified
  investment criteria.

A result can be:

```text
Research-system status: valid
Strategy-hypothesis status: rejected
```

That means the lab worked and the strategy failed. Do not treat that as a repo
failure.

The final report may name a best remaining candidate. That is not a trading
recommendation. It means the candidate is the least-bad branch from this bounded
campaign and still needs review against unresolved risks.

## Stop Conditions

The current campaign stops when:

- the deterministic provider has no materially different proposal left,
- the run budget is too small for the next projected workflow,
- cycle budget is exhausted,
- proposal validation fails,
- or the provider returns `stop_campaign`.

Ollama and Codex providers must keep the same boundary: providers return
strict proposal JSON, while the controller owns validation, execution, state,
and stopping.
