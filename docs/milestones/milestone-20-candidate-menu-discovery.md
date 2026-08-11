# Milestone 20: Candidate Menu Discovery

Status: planned.

## Why This Milestone Exists

The current campaign controller is safer than the discovery process feeding it.
The controller can read campaign state, validate strict proposals, reject
duplicates, preserve budgets, and stop without spending runs. The weak point is
that a model provider is still asked to invent the next experiment from a narrow
context.

The recent seeded Ollama checks showed a useful failure mode:

- With one symbol, two executable templates, and one weakened thesis, there may
  be no intelligent next run left.
- Before prompt hardening, `llama3.1:8b` repeated the rejected SMA 200 baseline.
- After prompt hardening, it stopped repeating the baseline but consistently
  returned `request_human_review`.

That is not a backtester failure. It means the search space is too narrow and
under-specified for useful autonomous discovery.

This milestone adds a deterministic candidate-menu layer between opportunity
theses and provider proposals. Python should generate valid, bounded candidates;
the provider should rank or choose among them.

## Goal

Change provider discovery from:

```text
LLM invents next experiment -> validator -> backtester
```

to:

```text
opportunity catalog
+ experiment template catalog
+ allowed parameter neighborhoods
+ prior conclusions
-> deterministic candidate generator
-> duplicate / do_not_repeat filter
-> information-value candidate menu
-> provider chooses one candidate
-> Python validation
-> existing experiment workflow
```

The provider should not invent unsupported indicators, templates, parameters,
or shell commands. Its job is to reason over a small menu of already-valid
research choices.

## Core Design Principle

Rank candidates by expected information value, not expected profit.

A useful next experiment should distinguish between plausible explanations for
prior results. For the current SPY drawdown-control campaign, examples are:

- The SMA 200 branch may be too slow.
- The RSI confirmation branch may reduce participation too much.
- Trend defense may reduce drawdown but structurally sacrifice too much CAGR.
- The liquid ETF trend-defense thesis may simply be weak for SPY.

The candidate menu should help answer which of those explanations is becoming
more likely.

## New Conceptual Layers

### 1. Opportunity Theses

Already introduced in Milestone 19.

These describe the market mechanism:

- market niche,
- counterparty or forced actor,
- why the edge might exist,
- why large capital might ignore it,
- capacity/friction evidence,
- persistence mechanism,
- crowding risk,
- edge-decay trigger,
- falsification tests,
- compatible strategy families,
- engine fit.

### 2. Experiment Template Catalog

This milestone adds a catalog above executable strategy JSON.

The catalog should describe bounded research templates, not one-off optimized
strategies. A template is a meaningfully distinct experiment family such as:

- price versus moving average state,
- dual moving-average confirmation,
- breakout long/cash,
- volatility-filtered trend,
- rolling-low reversion,
- static portfolio allocation.

Each template entry should state:

- template ID,
- strategy family,
- rationale,
- what claim it tests,
- supported symbols or universe type,
- required engine capabilities,
- supported executable mapping,
- default validation plan,
- parameter-neighborhood ID,
- known limitations,
- whether it is executable today.

### 3. Allowed Parameter Neighborhoods

Parameter neighborhoods are small prespecified sets, not open-ended sweeps.

Example:

```json
{
  "neighborhood_id": "trend_daily_basic",
  "parameters": {
    "lookback": [100, 150, 200],
    "confirmation_days": [0, 5]
  },
  "max_variants": 3,
  "rationale": "Tests nearby daily trend speeds without broad mining."
}
```

The candidate generator may sample or select from neighborhoods, but it should
never silently expand them during a campaign.

## Candidate Schema

Initial candidate artifacts should use a versioned schema:

```json
{
  "schema_version": "campaign_candidate.v1",
  "candidate_id": "trend_014",
  "title": "SPY dual moving-average trend confirmation",
  "opportunity_thesis_id": "liquid_etf_trend_defense",
  "template_id": "dual_ma_trend",
  "strategy_template": "ema-trend-follow",
  "symbol": "SPY",
  "parameters": {
    "fast_length": 50,
    "slow_length": 200
  },
  "hypothesis": "Dual moving-average confirmation may reduce whipsaw compared with price-vs-SMA state.",
  "tests_claim": "Trend confirmation itself improves the drawdown/growth tradeoff.",
  "distinguishes_from_prior": [
    "removes RSI dependency",
    "uses trend confirmation rather than a single price-vs-MA threshold"
  ],
  "novelty_reason": "Tests confirmation structure rather than only changing the SMA length.",
  "prior_overlap": "low",
  "expected_information_gain": "high",
  "parameter_mining_risk": "low",
  "engine_support_status": "ready",
  "success_criteria": {
    "minimum_cagr_retention": 0.8,
    "minimum_relative_drawdown_reduction": 0.2
  },
  "validation_plan": {
    "cost_sensitivity": true,
    "date_sensitivity": true,
    "train_test": true
  }
}
```

Allowed ratings:

- `prior_overlap`: `none`, `low`, `medium`, `high`
- `expected_information_gain`: `low`, `medium`, `high`
- `parameter_mining_risk`: `low`, `medium`, `high`
- `engine_support_status`: `ready`, `blocked`

## Candidate Menu Artifact

The generated menu should be JSON as source of truth and Markdown for humans:

```text
artifacts/campaigns/<campaign>/cycles/cycle_003/candidate_menu.json
artifacts/campaigns/<campaign>/cycles/cycle_003/candidate_menu.md
```

The Markdown should answer:

- What campaign state was read?
- Which completed experiments were treated as forbidden?
- Which opportunity theses were considered?
- Which templates were compatible?
- Which candidates survived filtering?
- Why were other candidates rejected?
- Which candidates appear most informative?

## Provider Contract Change

The provider should receive a small candidate menu, not a blank page.

Future proposal shape should either:

```json
{
  "action": "choose_candidate",
  "candidate_id": "trend_014",
  "rationale": "This best distinguishes whether trend confirmation failed because RSI reduced participation."
}
```

or keep the existing `run_experiment` shape but require the proposal to copy a
candidate by ID:

```json
{
  "action": "run_experiment",
  "candidate_id": "trend_014",
  "..."
}
```

The smallest implementation should avoid a schema migration if possible:

- generate candidates first,
- let the provider choose `candidate_id`,
- convert the chosen candidate into the existing `campaign_proposal.v1`,
- run the existing validator unchanged where practical.

If schema changes become necessary, keep them additive and versioned.

## Proposed CLI

Start with inspection commands before execution integration:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign candidates `
  --campaign artifacts\campaigns\spy_research_001
```

Outputs:

```text
candidate_menu: artifacts\campaigns/<campaign>/cycles/cycle_003/candidate_menu.json
read_first: artifacts\campaigns/<campaign>/cycles/cycle_003/candidate_menu.md
```

Then add provider selection:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign choose-candidate `
  --campaign artifacts\campaigns\spy_research_001 `
  --provider ollama `
  --model llama3.1:8b
```

Only after those are proven should `campaign run` call candidate generation
automatically.

## Implementation Slices

### Slice 1: Plan And Catalog Shape

Goal: create the stable conceptual plan and catalog schema before writing
campaign logic.

Deliverables:

- This milestone file.
- Updated docs index and milestone overview.
- Draft catalog location:

```text
data/experiment_template_catalog/
data/parameter_neighborhoods/
```

Exit criteria:

- Future Codex can explain the discovery problem without reading chat history.
- The next code slice has a clear file and schema target.

### Slice 2: Template And Neighborhood Catalogs

Goal: add static conceptual catalog files without changing campaign execution.

Deliverables:

- Strict JSON schema parser for experiment templates.
- Strict JSON schema parser for parameter neighborhoods.
- Starter entries for current supported families only.
- Tests for valid and invalid catalog entries.

Exit criteria:

- The repo can load catalogs and identify executable-ready templates.
- No campaign behavior changes yet.

### Slice 3: Deterministic Candidate Generator

Goal: create candidate menus from current state and catalogs.

Deliverables:

- `campaign candidates` command.
- Candidate JSON/Markdown artifacts.
- Deduplication against completed experiment titles and `do_not_repeat`.
- Filtering by allowed symbols, allowed templates, engine fit, and budgets.
- Candidate fields for information value and mining risk.

Exit criteria:

- Seeded SPY campaign produces either a small candidate menu or an explicit
  `SEARCH_SPACE_EXHAUSTED` result.
- No model provider is required.

### Slice 4: Provider Chooses From Menu

Goal: make Ollama/Codex choose from candidates instead of inventing proposals.

Deliverables:

- Provider context includes `candidate_menu`.
- Provider output is a strict candidate choice or human-review/stop action.
- Python validates candidate IDs and converts selected candidates into existing
  campaign proposals.
- Invalid choices are saved, retried once, then stopped/fallback.

Exit criteria:

- Ollama no longer writes arbitrary experiment details for campaign discovery.
- A repeated stale branch can only appear if Python generated it, which should
  be treated as a candidate-generator bug.

### Slice 5: Campaign Integration

Goal: make the normal campaign loop use candidate generation.

Deliverables:

- `campaign run` generates a candidate menu before asking model providers.
- Deterministic provider can select the top valid candidate or stop when the
  menu is empty.
- Final campaign reports mention whether the search space was exhausted.

Exit criteria:

- A seeded campaign with no valid remaining candidates stops as
  `SEARCH_SPACE_EXHAUSTED`.
- A campaign with new catalog scope can run one chosen candidate through the
  existing `experiment run-default` workflow.

## Non-Goals

Do not build these in this milestone:

- A giant flat strategy database.
- New indicators just to create more choices.
- Options, intraday, event-data, or second-source data infrastructure.
- Freeform provider-generated Python or shell commands.
- Campaign-time source-code modifications.
- Broad parameter mining.
- Automatic success-criteria changes after seeing results.
- A fully autonomous long-running research agent.

## First Test Campaign Scope

Keep the first test narrow:

- Symbol: `SPY`
- Current thesis: `liquid_etf_trend_defense`
- Existing executable templates only, unless a template already maps cleanly to
  current engine capabilities.
- Budget: one candidate-menu cycle, no execution until the menu is inspected.

The expected useful outcomes are:

- A small set of valid candidates ranked by information value.
- Or an explicit `SEARCH_SPACE_EXHAUSTED` result.

Either outcome is useful. A forced new experiment is not.

## How This Wraps The Current Discovery Issue

The current issue is not that the campaign runner cannot execute. It can.

The issue is that the provider is being asked to invent from too little search
space. Candidate-menu discovery fixes that by moving combinatorial generation
into deterministic Python and leaving reasoning/selection to the provider.

This keeps the agent useful without handing it the keys to overfit the research
process.
