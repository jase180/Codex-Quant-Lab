# SPY Opportunity Expansion Campaign Closeout

Report role: campaign closeout and next-research handoff.

This note preserves the first controlled expansion after the SPY trend-defense
campaign was closed as exhausted. Generated campaign artifacts are intentionally
ignored by Git; this tracked file records what the repo learned and what should
not be repeated.

## Campaign Question

Objective:

```text
Test a small set of non-nearby SPY opportunity candidates after the initial
trend-defense campaign exhausted its current templates.
```

Campaign scope:

- Config: `data/campaigns/spy_opportunity_expansion_campaign.json`
- Symbol: `SPY`
- Data: `data/cache/SPY_2015-01-01_2025-12-31.csv`
- Benchmark: `buy-and-hold`
- Cost preset: `retail-liquid`
- Allowed templates: `rsi-reversion`, `breakout-trend`
- Candidate budget: `2` cycles, `22` total projected runs
- Provider: `deterministic`

This was not a broad strategy search. It intentionally tested two already
supported executable templates that were materially different from another
nearby SMA or EMA trend-filter tweak.

## Command

The campaign was run with:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_opportunity_expansion_campaign.json `
  --out artifacts\campaigns\spy_opportunity_expansion_smoke_001 `
  --force

.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --out artifacts\campaigns\spy_opportunity_expansion_smoke_001 `
  --resume

.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --out artifacts\campaigns\spy_opportunity_expansion_smoke_001 `
  --resume
```

The first command ran cycle 1, the second ran cycle 2, and the third finalized
the campaign after the candidate menu was exhausted.

## Generated Artifacts

Local generated artifacts:

- `artifacts/campaigns/spy_opportunity_expansion_smoke_001/final_report.md`
- `artifacts/campaigns/spy_opportunity_expansion_smoke_001/final_report.json`
- `artifacts/campaigns/spy_opportunity_expansion_smoke_001/campaign_state.md`
- `artifacts/campaigns/spy_opportunity_expansion_smoke_001/cycles/cycle_001/experiment/experiment_conclusion.md`
- `artifacts/campaigns/spy_opportunity_expansion_smoke_001/cycles/cycle_002/experiment/experiment_conclusion.md`
- `artifacts/campaigns/spy_opportunity_expansion_smoke_001/cycles/cycle_003/candidate_menu.md`

Treat the generated `final_report.md` as the local evidence front door.

## Campaign Result

The campaign completed successfully as a research-system workflow.

Final status:

- Campaign status: `complete`
- Stop reason: `SEARCH_SPACE_EXHAUSTED`
- Runs used: `22`
- Remaining runs: `0`
- Remaining candidates: none

Experiments attempted:

- `EXP-042` `SPY RSI Pullback Reversion`
- `EXP-043` `SPY Breakout Trend Persistence`

Research-system outcomes:

- RSI pullback reversion: `valid`
- Breakout trend persistence: `valid`

Strategy-hypothesis outcomes:

- RSI pullback reversion: `partially_supported`
- Breakout trend persistence: `partially_supported`

Opportunity-thesis outcomes:

- `retail_pullback_liquidity`: `weakened`
- `liquid_etf_trend_defense`: `weakened`

## What Was Learned

The RSI pullback rule tested a different mechanism from slow SPY trend defense:
short-term liquidity/reversion after downside pressure.

Result:

- Return retention: failed
- Drawdown reduction: passed
- Strategy-hypothesis status: `partially_supported`
- Confidence label: `rejected`

The important failure was return retention. The observed CAGR retention was
`0.1399` versus a threshold of `0.7`, while drawdown reduction was `0.4397`
versus a threshold of `0.15`.

The breakout trend rule tested whether rolling-high/rolling-low persistence
behaved differently from moving-average state.

Result:

- Return retention: failed
- Drawdown reduction: passed
- Strategy-hypothesis status: `partially_supported`
- Confidence label: `rejected`

The observed CAGR retention was `0.5334` versus a threshold of `0.8`, while
drawdown reduction was `0.6528` versus a threshold of `0.2`.

## Interpretation

The lab again worked correctly as a measurement system. Both experiments were
technically valid, both saved canonical conclusions, and the campaign stopped
when the bounded candidate menu was exhausted.

The strategies did not achieve the investment objective. Both reduced drawdown,
but both failed return-retention thresholds after the full validation workflow.
This is a valid mixed or negative research result, not a repo failure.

The repeated pattern across SPY single-asset tests is now clear:

```text
Simple long/cash timing rules can reduce drawdown, but the tested variants give
up too much SPY buy-and-hold growth under the current objective.
```

## Do Not Repeat

Do not add another nearby SPY single-asset rule merely because the last one
reduced drawdown. That pattern is already known and insufficient.

Do not tune RSI thresholds, breakout channel lengths, SMA lengths, or EMA/RSI
combinations until there is a written hypothesis explaining why the return
retention problem should improve.

Do not call either `partially_supported` result promising without the failed
return-retention criterion beside it.

Do not use the campaign result to conclude that all mean reversion or all
breakout systems fail. The tested evidence is SPY-only, daily, long/cash, and
limited to the current executable templates.

## Remaining Caveats

The same project-level caveats remain:

- adjusted-price and benchmark economics still matter;
- the campaign used one symbol and one data source;
- both new templates exposed only one fixed variant;
- parameter-neighborhood evidence is not yet indexed as run rows;
- opportunity-thesis status is weakened by these tests but not fully rejected.

## Next Direction

Stop expanding SPY-only single-asset timing for now. The next useful research
step is a genuinely different niche or universe, not another SPY entry/exit
shape.

Preferred next directions:

- multi-asset or ETF-universe relative-strength candidates;
- defensive asset switching with an explicit alternative asset;
- less-liquid or fragmented ETF niches where small-capital advantage is more
  plausible;
- event-driven liquidity only after the data requirements are made explicit.

The campaign system is ready for that next step. The research question should
move from "which SPY timing rule?" to "which market niche has a structural reason
to exist and can the current engine test it honestly?"

## Closeout Decision

Close this campaign as:

```text
Research-system status: valid
Campaign status: complete
Candidate menu status: exhausted
Strategy result: partially supported on drawdown, failed on return retention
Opportunity-thesis status: weakened
Next action: leave SPY-only timing and expand to a different niche/universe
```

