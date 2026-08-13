# ETF Flow Breakout Probe

Report role: tracked campaign-result note.

Generated artifacts live under:

```text
artifacts/campaigns/liquid_etf_flow_probe_001/
```

Those artifacts are ignored by Git. This note records the result so the next
research slice does not need to rediscover it from the conversation.

## Why This Was Run

The prior extended ETF campaign exhausted its bounded candidate menu after four
cycles. A follow-up slice added:

```text
data/opportunity_catalog/etf_flow_persistence.json
data/experiment_template_catalog/etf_flow_breakout_continuation.json
```

It also narrowed the campaign repeat matcher so the same executable strategy can
test a different opportunity thesis without being blocked by older branch
memory.

## Command

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\liquid_etf_extended_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_flow_probe_001 `
  --max-cycles 1 `
  --max-total-runs 11 `
  --duration 5m `
  --force
```

## What Ran

- Experiment: `EXP-069`
- Title: `EEM ETF Flow Breakout Continuation`
- Opportunity thesis: `etf_flow_persistence`
- Strategy template: `breakout-trend`
- Selected candidate: `eem_etf_flow_persistence_etf_flow_breakout_continuation_001`
- Runs used: `11`

## Result

- Research-system status: `valid`
- Strategy-hypothesis status: `partially_supported`
- Opportunity-thesis status: `weakened`
- Confidence label: `rejected`

The strategy met the drawdown-reduction criterion but failed return retention:

```text
return_retention: fail, observed cagr strategy_vs_benchmark_ratio = -0.8385
drawdown_reduction: pass, observed relative max-drawdown reduction = 0.2777
```

Robustness was weak:

- Cost sensitivity: `failed`
- Date sensitivity: `failed`
- Benchmark sensitivity: `mixed`

## Interpretation

The research system worked. The tested EEM breakout continuation strategy did
not satisfy the prespecified investment criteria.

This weakens the initial ETF-flow persistence branch, but it does not fully
reject the broader idea. The conclusion says a follow-up should explain why the
failure mode should differ before running another variant.

## What Carries Forward

Campaign memory recorded:

```text
Do not repeat weakened branch: opportunity=etf_flow_persistence; template=breakout-trend.
```

That means the next campaign should not simply run another ETF-flow breakout
candidate on a different symbol. It should either:

- use a materially different template to test ETF flow persistence,
- revise the ETF-flow thesis with a sharper mechanism,
- or move to a different opportunity thesis.

## Next

Do not add more symbols just because this failed. The next useful slice is to
make candidate generation better at choosing among opportunity theses and
templates based on what has already been weakened, then run another small
bounded probe.
