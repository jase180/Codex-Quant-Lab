# ETF Campaign Branch-Filter Probe

Report role: campaign memory and candidate-filtering proof.

Generated artifacts live under:

```text
artifacts/campaigns/liquid_etf_core_branch_filter_probe/
```

Those artifacts are ignored by Git. This note records the behavior that matters
for future campaign runs.

## Why This Was Run

The first ETF shortlist probe selected `eem_rsi_pullback_reversion_001`. Its
canonical conclusion was technically valid, but the opportunity thesis was
weakened because robustness evidence was poor.

Resuming that original campaign exposed a design issue: exact title filtering
prevented repeating the same EEM RSI experiment, but the next cycle selected EFA
RSI pullback. That was a different title, but effectively the same weakened
opportunity/template branch:

```text
opportunity=retail_pullback_liquidity
template=rsi-reversion
```

That is not the behavior we want from an autonomous or semi-autonomous campaign.
When a branch is weakened, the next cycle should move to a materially different
question instead of hopping sideways to a neighboring symbol.

## Change Being Proved

Campaign memory now carries forward weakened branch rules like:

```text
Do not repeat weakened branch: opportunity=retail_pullback_liquidity; template=rsi-reversion.
```

The candidate menu treats that as a branch-level exclusion. It can still test
the same opportunity thesis through a meaningfully different template, or the
same template under a different opportunity thesis, but it should not keep
running the same weakened opportunity/template pair.

## Replay Commands

Fresh cycle:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\liquid_etf_core_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_core_branch_filter_probe `
  --force
```

Resume for the second cycle:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --out artifacts\campaigns\liquid_etf_core_branch_filter_probe `
  --resume
```

## Observed Result

Cycle 1 selected:

```text
EEM RSI Pullback Reversion
opportunity=retail_pullback_liquidity
template=rsi-reversion
```

Cycle 2 selected:

```text
EEM Breakout Trend Persistence
opportunity=liquid_etf_trend_defense
template=breakout-trend
```

The cycle 2 candidate menu rejected the remaining RSI pullback candidates with
`violates do_not_repeat`, including the nearby EFA RSI candidate that the older
logic had selected.

## Interpretation

This is not evidence of a profitable ETF strategy. It is evidence that campaign
memory is becoming more useful.

The campaign can now distinguish:

- exact experiment repetition,
- same weak branch on a different symbol,
- and a materially different branch.

That makes longer campaign runs safer because the controller is less likely to
spend budget on superficial variants after a weakened conclusion.

## Remaining Caveat

Resolved for new campaign runs: campaign conversion now tags generated
experiments with `template:<strategy_template>`, canonical
`experiment_conclusion.json` exposes `experiment.strategy_template`, and
campaign memory stores that field in `completed_experiments[]`.

Older conclusions without the field can still fall back to title inference, but
new branch-memory decisions no longer depend on experiment naming conventions.
