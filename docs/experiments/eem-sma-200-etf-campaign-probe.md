# EEM SMA 200 ETF Campaign Probe

Report role: tracked campaign probe handoff.

Generated artifacts live under:

```text
artifacts/campaigns/liquid_etf_core_probe_001/
```

Those artifacts are ignored by Git. This note records why the probe mattered.

## Why This Was Run

After adding `data/universes/liquid_etf_core.json`, the next question was whether
the campaign runner could use a broader ETF universe without Codex manually
choosing the symbol.

The probe used:

- Campaign config: `data/campaigns/liquid_etf_core_discovery_campaign.json`
- Universe: `data/universes/liquid_etf_core.json`
- Provider: `deterministic`
- Selected candidate: `eem_price_vs_sma_trend_003`
- Experiment: `EXP-046`
- Strategy: `EEM SMA 200 long/cash campaign baseline`

## Command

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\liquid_etf_core_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_core_probe_001 `
  --force
```

## Result

Research-system status: `valid`.

The campaign successfully expanded the tracked universe into allowed symbols and
data paths, selected a candidate, generated strategy JSON, ran the default
experiment workflow, wrote a canonical conclusion, and updated campaign memory.

Strategy-hypothesis status: `partially_supported`.

The EEM 200-day SMA long/cash rule passed the two prespecified measurable
criteria in the selected validation record:

- return retention: `pass`, observed `1.0656`
- drawdown reduction: `pass`, observed `0.4914`

But the full evidence was mixed:

- cost sensitivity: `failed`
- date sensitivity: `failed`
- benchmark sensitivity: `mixed`

Opportunity-thesis status: `weakened`.

The campaign should not carry this forward as a cleanly supported liquid ETF
trend-defense result. It is a useful probe because it proved the broader ETF
campaign path works and exposed a conclusion-quality issue: passing measurable
criteria is not enough when planned robustness checks fail.

## Code Follow-Up

The conclusion builder was tightened after this probe. If prespecified
measurable criteria pass but planned robustness checks are `mixed` or `failed`,
`strategy_hypothesis_status` is now downgraded to `partially_supported`.

## Next

Before a 30-minute unattended campaign, improve candidate selection so the
runner chooses from a smaller, information-oriented menu instead of relying on
deterministic ordering across many symbol/template combinations.
