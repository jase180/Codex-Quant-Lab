# EEM RSI Pullback ETF Shortlist Probe

Report role: tracked campaign probe handoff.

Generated artifacts live under:

```text
artifacts/campaigns/liquid_etf_core_shortlist_probe_001/
```

Those artifacts are ignored by Git. This note records the result from the first
actual ETF campaign cycle after candidate-menu shortlisting was added.

## Why This Was Run

The prior ETF campaign probe proved the campaign runner could use the broader
ETF universe, but it also showed that deterministic selection was biased toward
baseline-style SMA candidates. Candidate-menu shortlisting was added so the
provider sees a smaller, more diverse, information-oriented menu.

This probe checked whether the new shortlist path could execute one cycle and
carry the conclusion forward correctly.

## Setup

- Campaign config: `data/campaigns/liquid_etf_core_discovery_campaign.json`
- Universe: `data/universes/liquid_etf_core.json`
- Candidate menu cap: `12`
- Provider: `deterministic`
- Selected candidate: `eem_rsi_pullback_reversion_001`
- Experiment: `EXP-047`
- Strategy: `EEM RSI Pullback Reversion`
- Opportunity thesis: `retail_pullback_liquidity`

The candidate menu had `60` valid candidates before shortlist and `12` after
shortlist. The selected candidate was the first ranked menu item, not a
baseline-first fallback.

## Command

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\liquid_etf_core_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_core_shortlist_probe_001 `
  --force
```

## Result

Research-system status: `valid`.

The campaign selected a candidate from the shortlisted menu, generated strategy
JSON, ran the default experiment workflow, wrote canonical conclusion artifacts,
and updated campaign memory.

Strategy-hypothesis status: `partially_supported`.

The selected validation record passed both measurable criteria:

- return retention: `pass`, observed `1.8864`
- drawdown reduction: `pass`, observed `0.7850`

But the full evidence was not clean:

- cost sensitivity: `failed`
- date sensitivity: `failed`
- benchmark sensitivity: `mixed`

Opportunity-thesis status: `weakened`.

## Important Interpretation

Do not promote this as an EEM RSI pullback edge. The attractive selected test
window is contradicted by baseline weakness and failed robustness.

Useful engineering result: the shortlist mechanism worked and the canonical
conclusion correctly prevented a superficially good validation row from becoming
clean `supported` campaign memory.

Useful research result: this exact EEM RSI pullback candidate is not sturdy
enough to widen or tune. The next cycle should either explain the failure mode or
test a clearly different symbol/template/thesis candidate from the shortlist.

## Next

Before a longer unattended campaign, run one resumed cycle and check that
campaign memory filters or deprioritizes this exact branch rather than simply
trying nearby RSI variants.
