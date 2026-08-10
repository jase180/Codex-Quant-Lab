# Milestone 19: Niche Discovery Layer

Status: in progress.

First implementation slice delivered:

- Added `src/quant_lab/opportunity_theses.py` with strict
  `opportunity_thesis.v1` validation.
- Added starter conceptual theses under `data/opportunity_catalog/`.
- Updated `quant-lab ideas suggest` so compatible strategy suggestions can cite
  a matching opportunity thesis without creating executable strategy JSON.

Second implementation slice delivered:

- Added optional `opportunity_thesis_id` support to `campaign_proposal.v1`.
- Added compact opportunity-thesis summaries to campaign provider context.
- Updated deterministic campaign proposals to cite the liquid ETF trend-defense
  thesis when using the current SPY trend templates.

## Goal

Shift Quant Lab from searching strategy space to searching economic-mechanism
space.

The agent should not start with:

```text
What strategy should I test?
```

It should start with:

```text
Where might a market participant be forced, constrained, inattentive, or
price-insensitive?
```

Then Quant Lab should ask whether a small account can test or exploit that
niche better than large capital, and use the existing backtester as the
falsification engine.

## Core Workflow

```text
market niche
-> counterparty / forced actor
-> small-capital advantage
-> institutional friction
-> evidence quality
-> persistence mechanism
-> edge-decay trigger
-> observable prediction
-> engine fit check
-> prespecified experiment
-> kill tests
-> thesis status update
```

## Design Boundary

This milestone adds a layer above executable strategies. It should not rebuild
the backtester, add an options engine, add an event database, or expand the
strategy language just because a thesis sounds interesting.

Rules:

- Every agent-generated research idea requires an `opportunity_thesis.v1`.
- Manual diagnostics and implementation sanity checks may skip the thesis
  layer.
- Do not generate executable strategy JSON unless the thesis is currently
  testable.
- Do not accept "institutions ignore it" without evidence-quality labeling.
- Do not confuse engine incapability with thesis rejection.
- Prefer small, annoying, capacity-limited niches over obvious mega-cap effects.

## Phase 1: Opportunity Thesis Schema

Add `opportunity_thesis.v1`.

Core fields:

```json
{
  "schema_version": "opportunity_thesis.v1",
  "id": "small_cap_index_deletion_rebound",
  "title": "Small-cap index deletion rebound",
  "universe": "US small-cap equities",
  "market_niche": "Index deletion events in less-liquid names",
  "phenomenon": "Forced benchmark/index selling may create temporary underpricing.",
  "counterparty_or_forced_actor": "Index funds and benchmark-constrained managers forced to sell deleted names.",
  "why_edge_might_exist": "Mechanical selling may prioritize mandate compliance over short-term price.",
  "why_small_capital_might_have_advantage": "A small account may enter positions without materially moving price.",
  "institutional_friction": "Low liquidity, small absolute P&L, data cleanup, operational overhead.",
  "institutional_constraint_evidence": {
    "expected_daily_dollar_volume": "unknown",
    "estimated_position_size": "unknown",
    "estimated_strategy_capacity": "unknown",
    "number_of_opportunities_per_year": "unknown",
    "estimated_absolute_pnl_at_capacity": "unknown",
    "evidence_quality": "speculative"
  },
  "capacity_hypothesis": "Likely limited; may degrade quickly above small capital.",
  "persistence_mechanism": "Mandate-driven selling may continue as long as passive/benchmark-constrained capital must rebalance.",
  "crowding_risk": "Public deletion calendars and specialist arbitrage could compress the effect.",
  "edge_decay_trigger": "Effect disappears after realistic spread/slippage or post-deletion liquidity improves materially.",
  "expected_holding_period": "Days to weeks",
  "execution_constraints": [
    "spread-sensitive",
    "avoid unusably illiquid names",
    "avoid event-date look-ahead"
  ],
  "data_requirements": [
    "index deletion dates",
    "daily OHLCV",
    "liquidity proxy",
    "spread/slippage proxy"
  ],
  "observable_predictions": [
    "Deleted names underperform into deletion date and partially rebound afterward.",
    "Effect is stronger where dollar volume is lower but still tradable."
  ],
  "falsification_tests": [
    "Fails after conservative spread/slippage assumptions.",
    "Only works in one era.",
    "Only works in names too illiquid to trade.",
    "Does not survive neighboring event windows."
  ],
  "engine_support": {
    "currently_testable": false,
    "missing_capabilities": [
      "event calendar ingestion",
      "liquidity filters",
      "spread proxy"
    ]
  },
  "rubric": {
    "structural_plausibility": "pass",
    "small_capital_advantage": "pass",
    "falsifiability": "pass",
    "deployability": "blocked",
    "engine_fit": "blocked"
  },
  "decision": "investigate_data"
}
```

## Phase 2: Opportunity Catalog

Add:

```text
data/opportunity_catalog/
  README.md
  small_capacity_equity.json
  event_driven_scraps.json
  calendar_flow_effects.json
  fragmented_universes.json
  options_microstructure.json
```

Start with 10 to 15 strong theses, not a giant database. Each thesis is
conceptual and must stay separate from executable strategy JSON.

## Phase 3: Gated Rubric

Do not use additive scoring. The system should not compute fake precision from
words like high, medium, and low.

Use discrete gates:

```json
{
  "rubric": {
    "structural_plausibility": "pass | weak | fail",
    "small_capital_advantage": "pass | weak | fail",
    "falsifiability": "pass | fail",
    "deployability": "ready | blocked",
    "engine_fit": "ready | blocked"
  },
  "decision": "test_now | investigate_data | watchlist | reject"
}
```

Rules:

- If no plausible forced actor exists, downgrade or reject.
- If institutional friction has no evidence, mark evidence quality as
  `speculative`.
- If engine fit is blocked, do not generate strategy JSON.
- If deployability is blocked, do not pretend the idea is actionable.

## Phase 4: Opportunity Suggest Command

Add:

```bash
quant-lab opportunities suggest
```

It should read:

- opportunity catalog,
- prior `experiment_conclusion.json` files,
- campaign state when provided,
- strategy catalog,
- current engine capabilities,
- user objective.

It should output:

- one proposed opportunity thesis,
- rubric decision,
- why it was selected,
- whether it is currently testable,
- if testable, a draft experiment hypothesis,
- if not testable, missing data or capability blockers.

It must not create executable strategy JSON.

## Phase 5: Link Theses To Experiments

Add optional experiment/conclusion linkage:

```json
{
  "opportunity_thesis_id": "small_cap_index_deletion_rebound"
}
```

Conclusions should answer separately:

```text
Did the strategy fail?
Did the test weaken the thesis?
Did the test fail to measure the thesis?
Is the thesis still untested?
```

Formal thesis status:

```json
{
  "thesis_status": {
    "status": "supported | weakened | rejected | untested | measurement_failure",
    "reason": "...",
    "confidence": "low | medium | high"
  }
}
```

This prevents failed first implementations from automatically killing a good
market-structure idea, and prevents later parameter changes from pretending the
original thesis was confirmed.

## Phase 6: Campaign Integration

Update campaign/provider context so agents see:

- campaign objective,
- prior conclusions,
- do-not-repeat items,
- strategy catalog,
- opportunity catalog,
- allowed engine capabilities,
- current opportunity thesis if one exists.

Campaign proposal flow becomes:

```text
select opportunity thesis
-> check engine fit
-> propose one experiment only if currently testable
-> otherwise request human/data work
```

## Phase 7: Guardrails

Add explicit guardrails:

- Do not add a strategy feature just because one experiment failed.
- Do not run broad parameter sweeps before the structural thesis is written.
- Do not claim institutions ignore an opportunity without measurable or
  explicitly unknown evidence.
- Do not confuse "engine cannot test this" with "idea is bad."
- Do not force a fixed distribution of testable/blocked/rejected theses.

## Phase 8: First Use

Prompt:

```text
Find small-capacity, structurally plausible market opportunities that a small
personal account could investigate but large institutions may ignore.
```

Output:

- 10 opportunity theses.
- Each classified honestly by rubric.
- No forced distribution of testable, blocked, watchlist, or rejected ideas.

Then choose one `test_now` thesis and run the existing Quant Lab workflow.

## Do Not Build Yet

Do not build yet:

- options backtester,
- intraday engine,
- event database,
- spread database,
- short/borrow model,
- giant strategy library,
- fully autonomous agent loop.

## Success Criteria

Milestone 19 is done when:

1. Agent-generated research ideas require `opportunity_thesis.v1`.
2. Opportunity theses identify a plausible counterparty or forced actor.
3. Institutional friction and capacity claims carry evidence quality or
   `unknown`.
4. Suggestions use gated rubric decisions, not fake arithmetic scores.
5. The system can say whether the current engine can test a thesis.
6. Experiments can optionally link back to an opportunity thesis.
7. Conclusions can distinguish strategy failure from thesis failure.
8. At least one real experiment begins from a niche thesis rather than a
   strategy template.
