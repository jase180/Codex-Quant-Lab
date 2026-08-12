# Liquid ETF Diversity-Ranking Probe

Report role: candidate-ranking behavior handoff.

Generated artifacts live under:

```text
artifacts/campaigns/liquid_etf_core_diversity_probe/
```

Those artifacts are ignored by Git. This note records the behavior after
campaign candidate ranking started using completed campaign history when
building the next shortlist.

## Why This Was Run

The prior three-cycle campaign proved the loop could run unattended, but it was
too symbol-sticky:

```text
EEM RSI pullback
EEM breakout trend
EEM EMA/RSI trend
```

That was mechanically valid but not a great use of campaign budget. Once EEM had
already weakened a branch, the next candidates needed a stronger reason to stay
on EEM instead of asking whether the same broad thesis behaved differently on
another ETF.

## Change Being Proved

Candidate shortlisting now seeds its diversity counts from completed campaign
experiments:

- previously tested symbols receive a ranking penalty;
- previously tested strategy templates receive a smaller ranking penalty;
- previously tested opportunity theses receive a smaller ranking penalty;
- branch-level `do_not_repeat` exclusions still hard-block weakened
  opportunity/template pairs.

This does not force novelty. It nudges the deterministic menu toward better
information coverage when multiple comparable candidates are available.

## Command

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\liquid_etf_core_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_core_diversity_probe `
  --loop `
  --force
```

## Result

The loop completed all three allowed cycles:

```text
status=complete
stop_reason=maximum campaign cycles completed
runs_used=33
```

Selections:

1. `EEM RSI Pullback Reversion`
2. `EFA Breakout Trend Persistence`
3. `GLD EMA 50 RSI trend-follow campaign follow-up`

That is the intended project-level behavior change: after EEM was tested, the
next ranked candidates moved to different symbols instead of selecting another
EEM branch.

## Research Results

Cycle 1:

- Research-system status: `valid`
- Strategy-hypothesis status: `partially_supported`
- Opportunity-thesis status: `weakened`
- Robustness: cost `failed`, date `failed`, benchmark `mixed`

Cycle 2:

- Research-system status: `valid`
- Strategy-hypothesis status: `partially_supported`
- Opportunity-thesis status: `weakened`
- Robustness: cost `failed`, date `failed`, benchmark `failed`

Cycle 3:

- Research-system status: `valid`
- Strategy-hypothesis status: `rejected`
- Opportunity-thesis status: `weakened`
- Robustness: cost `failed`, date `failed`, benchmark `mixed`

## Interpretation

This is not evidence of an investable ETF strategy. The campaign still weakened
every tested thesis branch.

It is evidence that the campaign runner is closer to a useful unattended
research loop. The loop now:

- runs without manual experiment selection;
- carries branch memory forward;
- avoids exact and weakened-branch repeats;
- spreads the next shortlist across symbols when prior work already used one
  symbol;
- stops cleanly at the configured budget.

## Remaining Issue

The final campaign report still says `Best Remaining Candidate: none` when the
campaign stops because the run/cycle budget is exhausted. That is technically
true for the campaign as configured, but it can be misread as true search-space
exhaustion.

Next cleanup should distinguish:

- no remaining candidate because budget ended;
- no remaining candidate because the bounded search space is actually
  exhausted.

That matters before a 30-minute run because the user needs to know whether the
campaign ran out of time or genuinely ran out of justified ideas.
