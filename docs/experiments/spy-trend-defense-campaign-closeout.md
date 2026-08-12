# SPY Trend-Defense Campaign Closeout

Report role: campaign closeout and next-research handoff.

This note closes the first bounded campaign that used deterministic
candidate-menu discovery. The generated campaign artifacts are intentionally
ignored by Git; this tracked note keeps the conclusion and next direction
visible.

## Campaign Question

Objective:

```text
Find simple, defensible SPY drawdown-control rules that retain most long-term growth.
```

Campaign scope:

- Symbol: `SPY`
- Data: `data/cache/SPY_2015-01-01_2025-12-31.csv`
- Benchmark: `buy-and-hold`
- Cost preset: `retail-liquid`
- Opportunity thesis: `liquid_etf_trend_defense`
- Allowed templates: `sma-long-cash`, `ema-trend-follow`
- Max cycles: `3`
- Max total runs: `33`
- Provider: `deterministic`

The campaign was intentionally narrow. It was not allowed to invent new
indicators, add strategy features, change success criteria after results, or
silently widen the parameter search.

## Repeatability Check

The campaign loop was run twice after candidate-menu integration. The repeated
run used:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_drawdown_control_campaign.json `
  --out artifacts\campaigns\spy_candidate_loop_review_003 `
  --loop `
  --duration 5m `
  --max-cycles 3 `
  --max-total-runs 33 `
  --force
```

The repeated run matched the prior run at the campaign-decision level:

1. Cycle 1 selected `spy_price_vs_sma_trend_003`.
2. Cycle 2 selected `spy_ema_rsi_trend_confirmation_001`.
3. Cycle 3 stopped with `SEARCH_SPACE_EXHAUSTED`.

That is the desired behavior. The controller generated the same bounded
candidate sequence, carried forward the same do-not-repeat knowledge, and
stopped instead of forcing another SPY trend variant.

## Generated Artifacts

Main local artifacts from the repeat run:

- `artifacts/campaigns/spy_candidate_loop_review_003/final_report.md`
- `artifacts/campaigns/spy_candidate_loop_review_003/final_report.json`
- `artifacts/campaigns/spy_candidate_loop_review_003/campaign_state.md`
- `artifacts/campaigns/spy_candidate_loop_review_003/cycles/cycle_001/experiment/experiment_conclusion.md`
- `artifacts/campaigns/spy_candidate_loop_review_003/cycles/cycle_002/experiment/experiment_conclusion.md`
- `artifacts/campaigns/spy_candidate_loop_review_003/cycles/cycle_003/candidate_menu.md`

Treat `final_report.md` as the local front door for the generated evidence.

## Campaign Result

The campaign completed successfully as a research-system workflow.

Research-system outcome:

- Cycle 1 research-system status: `valid`
- Cycle 2 research-system status: `valid`
- Final campaign status: `complete`
- Stop reason: `SEARCH_SPACE_EXHAUSTED`

Strategy-hypothesis outcomes:

- `SPY SMA 200 long/cash campaign baseline`: `rejected`
- `SPY EMA 50 RSI trend-follow campaign follow-up`: `partially_supported`

Opportunity-thesis outcome:

- `liquid_etf_trend_defense`: `weakened` in both completed experiments

Interpretation:

The lab did its job. It measured two prespecified SPY trend-defense branches
honestly, saved the evidence, carried forward do-not-repeat constraints, and
stopped when the bounded search space was exhausted. The tested strategies did
not satisfy the investment objective well enough to justify more nearby SPY
trend-parameter variants.

## What Was Learned

The SMA 200 long/cash branch reduced risk but failed the return-retention and
drawdown criteria together:

- Strategy hypothesis: `rejected`
- Return retention failed.
- Drawdown reduction failed the campaign criterion.
- Cost and date sensitivity did not rescue the branch.

The EMA/RSI trend-follow branch improved drawdown behavior but still failed
return retention:

- Strategy hypothesis: `partially_supported`
- Return retention failed.
- Drawdown reduction passed.
- Overall confidence remained `rejected`.

The broader lesson is not "trend defense can never work." The narrower and more
useful lesson is:

```text
Within this SPY-only, daily, long/cash or EMA/RSI trend-defense campaign,
the current templates do not provide enough return retention to justify more
nearby variants.
```

## Do Not Repeat

Do not keep broadening this exact branch by adding SMA 100, SMA 150, SMA 250, or
another close trend-filter variant unless there is a written hypothesis that
explains why the prior contradiction should not repeat.

Do not treat the EMA/RSI branch as investable just because it was the best
completed result. It was the least-bad completed branch in a bounded campaign,
not a remaining candidate or a trading recommendation.

Do not use this campaign as evidence that the repo failed. The repo succeeded
by producing a valid negative or mixed result.

## Remaining Caveats

The campaign still inherits the project-level caveats:

- adjusted-price and corporate-action assumptions remain important;
- benchmark economics must stay consistent with the adjusted-price series;
- candidate-menu generation only searches the current opportunity/template
  catalog;
- the campaign has no second-source market-data reconciliation;
- the result is SPY-only and should not be generalized to all trend-following.

## Next Direction

The next work should expand the opportunity space, not mutate this exhausted SPY
trend-defense campaign.

Recommended next slice:

1. Add a small, controlled set of opportunity theses or experiment templates.
2. Keep each thesis tied to a market mechanism, forced actor, institutional
   friction argument, and falsification test.
3. Let Python generate a candidate menu from that bounded search space.
4. Ask the provider or Codex to choose among candidates, not invent strategies.
5. Run one short campaign and close it the same way.

Good candidate expansion directions:

- retail pullback liquidity;
- fragmented ETF relative strength;
- defensive asset switching;
- event-driven liquidity only after data requirements are explicit.

Do not build a giant strategy database yet. The right next move is a larger
bounded hypothesis space, not template roulette.

## Closeout Decision

Close the current SPY trend-defense campaign as:

```text
Research-system status: valid
Campaign status: complete
Strategy family result: rejected / partially supported but not actionable
Opportunity-thesis status: weakened
Next action: expand opportunity space before running another campaign
```

