# Campaign Runbook

Use this runbook when you want the lab to run a bounded sequence of experiments
without giving an agent permission to edit code or invent unsupported strategy
features.

## Current Boundary

`quant-lab campaign run` currently has three provider modes:

- `deterministic`: generates a candidate menu, chooses the best valid candidate,
  converts it into a campaign proposal, executes one campaign cycle, reads the
  canonical conclusion, and updates campaign memory.
- `ollama`: asks a local OpenAI-compatible Ollama model to choose one candidate
  ID from the generated menu, saves the provider context/prompt/raw
  response/choice, validates it, and stops before execution. This is a dry-run
  safety step. If the first model attempt fails or validates false, the
  controller allows one retry with the prior error or validation reasons in the
  second context. If the retry also fails, it writes a deterministic fallback
  choice for inspection only.
- `codex`: writes the same provider context and prompt artifacts, returns a
  valid `request_human_review` handoff choice, and stops. The standalone CLI
  does not call the current Codex chat session.

Deterministic run commands execute one campaign cycle:

1. Read `campaign_config.json` and `campaign_state.json`.
2. Read `data/research_mechanisms/*.json` and relevant
   `data/opportunity_catalog/*.json` theses for the campaign's
   allowed templates.
3. Read `data/experiment_template_catalog/*.json` and
   `data/parameter_neighborhoods/*.json`.
4. Generate `candidate_menu.json` and `candidate_menu.md`.
5. Choose and validate one `campaign_candidate_choice.v1`.
6. Convert the chosen candidate into a normal `campaign_proposal.v1`.
7. Validate the proposal against allowed templates, data, budgets, and
   `do_not_repeat` memory.
8. Convert the proposal into the existing `experiment run-default` workflow.
9. Execute that workflow.
10. Read `experiment_conclusion.json`.
11. Update `campaign_state.json` and `campaign_state.md`.

For model-backed providers, `provider_context.json` includes the complete
candidate menu, mechanism summaries, opportunity-thesis context, and campaign
memory. The provider can only choose a candidate ID, request human review, or
stop. It cannot invent strategy JSON, parameters, indicators, success criteria,
or shell commands during `campaign run`.

The candidate menu applies completed-title and `do_not_repeat` filters. Campaign
memory can now carry branch-level rules such as:

```text
Do not repeat weakened branch: opportunity=retail_pullback_liquidity; template=rsi-reversion.
```

That prevents the campaign from responding to a weakened branch by simply
running the same opportunity/template pair on a neighboring symbol. Treat
rejected candidates as useful evidence: they explain why a branch is not
available instead of forcing the model to improvise.

Candidate generation checks that each thesis exists in
`data/opportunity_catalog/`, references a valid `mechanism_id` in
`data/research_mechanisms/`, is marked `decision: test_now`, has `engine_fit:
ready`, and is compatible with the selected experiment-template family. A
blocked event-data thesis cannot leak into a currently supported SPY
trend-template run.

Candidate menus now show both:

```text
Thesis: etf_flow_persistence
Mechanism: etf_flow_pressure
```

This is the project boundary we want: the mechanism explains the market
imperfection being investigated, while the thesis narrows it to a falsifiable
claim for the current engine.

For executed campaign experiments, the thesis ID is also carried into the
generated `experiment run-default` command as an `opportunity:<id>` experiment
tag. That tag appears in the canonical `experiment_conclusion.json`, and
campaign memory copies it into `completed_experiments[].opportunity_thesis_id`
for the next cycle.

The campaign strategy template is carried the same way with a
`template:<strategy_template>` tag. New canonical conclusions expose it as
`experiment.strategy_template`, and campaign memory copies it into
`completed_experiments[].strategy_template`. This keeps branch-memory rules from
depending on title parsing.

Campaign-safe template metadata lives in `src/quant_lab/campaign_templates.py`.
When adding a template to campaign execution, update that one mapping so provider
context and proposal validation keep using the same strategy-family relationship.
The current campaign-safe templates are:

- `sma-long-cash`: trend following with an exposed `sma_length` parameter.
- `ema-trend-follow`: fixed EMA/RSI trend confirmation.
- `rsi-reversion`: fixed RSI pullback/reversion proxy.
- `breakout-trend`: fixed rolling-high/rolling-low breakout proxy.
- `calendar-month-end`: fixed regular month-end event-window branch.

`calendar-month-end` is intentionally single-variant. The generated default
workflow handoff includes a no-op event-calendar path parameter only because the
default workflow currently expects sweep/train-test input. Do not treat that as
permission to search entry/exit windows after seeing results.

When the candidate menu is exhausted, or when the campaign hits its run or cycle
budget, the loop writes `final_report.md` and `final_report.json`. Ollama dry
runs do not update campaign state or consume backtest budget unless
`--execute-model-proposal` is explicitly supplied.

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

## First ETF Universe Campaign

The checked-in expanded-universe config is:

```text
data/campaigns/liquid_etf_core_discovery_campaign.json
```

It reads the tracked universe:

```text
data/universes/liquid_etf_core.json
```

The campaign loader expands that universe into normal `allowed_symbols` and
`data_paths` using the universe date range and `data_dir`. This avoids manually
maintaining one path per ETF in the campaign config.

The checked-in config intentionally uses a representative subset of the full
universe: small-cap equity, sectors, bonds, gold, and international equity. The
full 29-symbol universe remains available, but the first candidate menu should
stay small enough for inspection.

It also sets `max_candidate_menu_size` to keep provider context bounded. The
menu builder ranks candidates by expected information gain, low parameter-mining
risk, low prior overlap, and diversity across symbols, mechanisms, templates,
and opportunity theses.

When resuming a campaign, the shortlist also considers completed campaign
history. A symbol, mechanism, strategy template, or opportunity thesis that has
already been tested receives a ranking penalty, while explicit `do_not_repeat`
rules can still hard-block weakened opportunity/template branches. This is meant
to spend small campaign budgets on broader information, not variety for its own
sake.

Before running it, fetch the universe data described in
`data/universes/README.md` and confirm the cache inventory shows provenance for
the requested date range. The first use should usually inspect candidates before
execution:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign init `
  --config data\campaigns\liquid_etf_core_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_core_discovery_001 `
  --force

.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign candidates `
  --campaign artifacts\campaigns\liquid_etf_core_discovery_001
```

This is broader than the SPY campaign, but it is still not a license for
unbounded search. Treat it as a candidate-inspection campaign until the selected
experiments look structurally useful.

## Extended ETF Campaign

The checked-in broader ETF config is:

```text
data/campaigns/liquid_etf_extended_discovery_campaign.json
```

It reads:

```text
data/universes/liquid_etf_extended.json
```

Use this after the core ETF campaign loop is behaving sensibly. The extended
universe adds style/factor ETFs, industry ETFs, more bonds, real assets,
currency, and more international ETFs, but it is still ETF-only. Do not treat it
as a small-capacity niche universe.

Fetch missing data first using `data/universes/README.md`, then inspect
candidates before running:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign init `
  --config data\campaigns\liquid_etf_extended_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_extended_discovery_001 `
  --force

.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign candidates `
  --campaign artifacts\campaigns\liquid_etf_extended_discovery_001
```

Only move to a loop after the candidate menu looks coherent.

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
is no longer `running`, a candidate choice or converted proposal is invalid, a
provider dry run is reached, a `stop_campaign` choice writes the final report,
or the safety iteration cap is hit.

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

Use this after inspecting the candidate menu when you want to test provider
selection without executing a cycle:

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

## Ollama Candidate Dry Run

Use this only to inspect whether a local model can choose a valid bounded
candidate. The command saves and validates the choice and generated proposal but
does not generate strategy files, run backtests, update campaign state, or write
conclusions.

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
artifacts/campaigns/<campaign>/cycles/cycle_001/candidate_choice_validation.md
artifacts/campaigns/<campaign>/cycles/cycle_001/proposal_validation.md
```

`provider_proposal.json` is a legacy filename in this path; for candidate-menu
providers it contains the parsed `campaign_candidate_choice.v1`.

If a retry happens, inspect:

```text
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_002/provider_context.json
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_002/candidate_choice_validation.md
```

The second context includes `prior_attempt_feedback`, which is the exact error
or validation failure the model was asked to correct.

For resumed seeded dry runs, inspect `candidate_menu.json`. If a stale branch is
unavailable, the menu should include the rejection reason:

```text
violates do_not_repeat
```

If the model cannot find a clean next run, a valid `request_human_review` is an
acceptable result. That is a request for human judgment, not a failed campaign
run.

If the candidate choice and generated proposal are valid, the CLI prints:

```text
execution: skipped_provider_dry_run
```

That is expected. Dry-run remains the default even though explicit execution is
available.

## Execute A Valid Ollama Choice

After inspecting a dry run, execute a valid model-selected candidate with an
explicit opt-in:

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
returns one candidate choice; Python validates it, converts it into a proposal,
validates the proposal, and only then converts it into the existing
`experiment run-default` workflow.

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
artifacts/campaigns/<campaign>/cycles/cycle_001/candidate_menu.md
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_001/provider_context.json
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_001/provider_prompt.md
artifacts/campaigns/<campaign>/cycles/cycle_001/provider_attempt_001/provider_proposal.json
artifacts/campaigns/<campaign>/cycles/cycle_001/candidate_choice_validation.md
```

`provider_proposal.json` uses the same legacy filename noted above, but the
payload is a candidate choice, not a freeform proposal.

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
3. another candidate only if the candidate menu still contains a materially
   valid non-forbidden branch within budget

It stops when the menu is exhausted or campaign budgets are consumed. The exact
third-step behavior depends on conclusions carried forward into
`campaign_state.json`; a `do_not_repeat` item can remove nearby SMA variants.

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

The final report includes a `Candidate Availability` section. Read it before
assuming the campaign ran out of ideas:

- `available_but_budget_exhausted` means the campaign stopped because cycles,
  runs, or time were exhausted, but valid candidates still existed.
- `search_space_exhausted` means no valid candidate remained after the bounded
  catalog, completed work, and `do_not_repeat` filters.
- `available` means the campaign stopped for another reason while candidates
  were still available under the current budget.

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

The final report may name a best completed result. That is not a trading
recommendation. It means the completed branch was the least-bad result from this
bounded campaign and still needs review against unresolved risks. `Best
Remaining Candidate` can be a not-run candidate when the campaign budget ended
before the bounded search space was exhausted.

## Stop Conditions

The current campaign stops when:

- the candidate menu has no materially different candidate left,
- the run budget is too small for the next projected workflow,
- cycle budget is exhausted,
- candidate-choice or proposal validation fails,
- or the provider returns `stop_campaign`.

Ollama and Codex providers must keep the same boundary: providers return
strict candidate-choice JSON, while the controller owns validation, execution,
state, and stopping.
