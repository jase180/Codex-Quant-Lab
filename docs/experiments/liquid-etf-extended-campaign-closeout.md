# Liquid ETF Extended Campaign Closeout

Report role: bounded campaign closeout.

Generated artifacts live under:

```text
artifacts/campaigns/liquid_etf_extended_discovery_001/
```

Those artifacts are ignored by Git. This note records the first real campaign
run against the extended ETF universe.

## Why This Was Run

The project had just added:

```text
data/universes/liquid_etf_extended.json
data/campaigns/liquid_etf_extended_discovery_campaign.json
```

The goal was to check whether a broader ETF universe made the campaign more
useful than the prior 10-symbol core ETF loop.

## Command

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\liquid_etf_extended_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_extended_discovery_001 `
  --loop `
  --force
```

## Campaign Result

The campaign stopped before using the full 5-cycle budget:

```text
status=complete
stop_reason=SEARCH_SPACE_EXHAUSTED: no valid candidate remains in the bounded menu.
cycles_used=4
runs_used=44
remaining_cycles=1
remaining_runs=11
```

This is true search exhaustion under the current campaign scope, not budget
exhaustion.

The final report's candidate availability section says:

```text
status=search_space_exhausted
candidate_count=0
assessed_with_run_budget=True
```

## Experiments Attempted

Cycle 1:

- Experiment: `EXP-065`
- Title: `EEM RSI Pullback Reversion`
- Opportunity thesis: `retail_pullback_liquidity`
- Strategy template: `rsi-reversion`
- Research-system status: `valid`
- Strategy-hypothesis status: `partially_supported`
- Opportunity-thesis status: `weakened`
- Robustness: cost `failed`, date `failed`, benchmark `mixed`

Cycle 2:

- Experiment: `EXP-066`
- Title: `EFA Breakout Trend Persistence`
- Opportunity thesis: `liquid_etf_trend_defense`
- Strategy template: `breakout-trend`
- Research-system status: `valid`
- Strategy-hypothesis status: `partially_supported`
- Opportunity-thesis status: `weakened`
- Robustness: cost `failed`, date `failed`, benchmark `failed`

Cycle 3:

- Experiment: `EXP-067`
- Title: `EWT EMA 50 RSI trend-follow campaign follow-up`
- Opportunity thesis: `liquid_etf_trend_defense`
- Strategy template: `ema-trend-follow`
- Research-system status: `valid`
- Strategy-hypothesis status: `rejected`
- Opportunity-thesis status: `weakened`
- Robustness: cost `failed`, date `failed`, benchmark `mixed`

Cycle 4:

- Experiment: `EXP-068`
- Title: `EWZ SMA 200 long/cash campaign baseline`
- Opportunity thesis: `liquid_etf_trend_defense`
- Strategy template: `sma-long-cash`
- Research-system status: `valid`
- Strategy-hypothesis status: `rejected`
- Opportunity-thesis status: `weakened`
- Robustness: cost `failed`, date `failed`, benchmark `failed`

## Interpretation

The research system worked. The strategies did not become investable
candidates.

The broader ETF universe improved symbol diversity:

```text
EEM -> EFA -> EWT -> EWZ
```

But it did not fix the deeper limitation. The current campaign only has two
compatible opportunity theses and four executable campaign-safe templates. Once
the campaign weakened:

- `retail_pullback_liquidity` + `rsi-reversion`;
- `liquid_etf_trend_defense` + `breakout-trend`;
- `liquid_etf_trend_defense` + `ema-trend-follow`;
- `liquid_etf_trend_defense` + `sma-long-cash`;

there were no valid candidates left, even though the ETF universe had more
symbols and the campaign still had run budget.

## What This Teaches

More ETF data helped verify the loop, but it is not the main bottleneck now.

The next constraint is the size and quality of the bounded hypothesis space:

- more opportunity theses;
- more campaign-safe experiment templates;
- better mapping from opportunity theses to templates;
- and eventually a market-niche discovery layer.

Do not respond to this closeout by sweeping more parameters or forcing the
campaign to keep testing the same weakened branch on more ETFs. That would turn
the campaign into historical fitting.

## Next

Pause further ETF symbol expansion. The next useful build slice is a small
increase in bounded research vocabulary, preferably at the opportunity-thesis
and experiment-template layer, before another longer campaign.

One concrete candidate:

```text
Add one new opportunity thesis and one campaign-safe template that test a
different market mechanism than trend defense or RSI pullback.
```

Keep the template simple, prespecified, and compatible with existing engine
capabilities.
