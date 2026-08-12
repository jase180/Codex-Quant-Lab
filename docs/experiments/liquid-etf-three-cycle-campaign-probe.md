# Liquid ETF Three-Cycle Campaign Probe

Report role: bounded campaign behavior handoff.

Generated artifacts live under:

```text
artifacts/campaigns/liquid_etf_core_three_cycle_probe/
```

Those artifacts are ignored by Git. This note records the current campaign-loop
behavior after explicit `strategy_template` metadata was added to conclusions
and campaign state.

## Why This Was Run

The previous branch-filter probe showed that weakened branches can be carried
forward as opportunity/template exclusions. The remaining question was whether a
short loop could run without Codex manually driving each cycle, and whether the
new metadata made campaign memory cleaner.

## Command

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\liquid_etf_core_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_core_three_cycle_probe `
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

Cycle 1:

- Experiment: `EXP-053`
- Title: `EEM RSI Pullback Reversion`
- Opportunity thesis: `retail_pullback_liquidity`
- Strategy template: `rsi-reversion`
- Research-system status: `valid`
- Strategy-hypothesis status: `partially_supported`
- Thesis status: `weakened`
- Criteria: return retention passed at `1.8864`; drawdown reduction passed at `0.7850`
- Robustness: cost `failed`, date `failed`, benchmark `mixed`

Cycle 2:

- Experiment: `EXP-054`
- Title: `EEM Breakout Trend Persistence`
- Opportunity thesis: `liquid_etf_trend_defense`
- Strategy template: `breakout-trend`
- Research-system status: `valid`
- Strategy-hypothesis status: `partially_supported`
- Thesis status: `weakened`
- Criteria: return retention failed at `-0.8385`; drawdown reduction passed at `0.2777`
- Robustness: cost `failed`, date `failed`, benchmark `mixed`

Cycle 3:

- Experiment: `EXP-055`
- Title: `EEM EMA 50 RSI trend-follow campaign follow-up`
- Opportunity thesis: `liquid_etf_trend_defense`
- Strategy template: `ema-trend-follow`
- Research-system status: `valid`
- Strategy-hypothesis status: `rejected`
- Thesis status: `weakened`
- Criteria: return retention failed at `-1.0606`; drawdown reduction failed at `0.1576`
- Robustness: cost `failed`, date `failed`, benchmark `failed`

## What This Proves

The campaign loop is now usable as a bounded research executor:

- It generated candidate menus.
- It selected one candidate per cycle.
- It converted candidates into existing `experiment run-default` inputs.
- It ran the existing backtest, validation, robustness, and conclusion workflow.
- It copied explicit `experiment.strategy_template` into campaign memory.
- It carried forward branch-level `do_not_repeat` rules.
- It stopped cleanly when the configured cycle and run budgets were consumed.

This is a repo success even though the tested strategies did not become
investment candidates.

## What This Does Not Prove

This does not prove an EEM edge. All three hypotheses were weakened after
robustness checks, and the final report should not be read as a trading
recommendation.

The final report names EEM RSI pullback as the best completed result only
because it was the least-bad completed branch in this bounded run. It still had
failed cost and date sensitivity.

## Important Bottleneck

The campaign is still too symbol-sticky. All three selected experiments used
EEM while rotating templates. That means branch filtering works, but candidate
ranking still over-prioritizes the top-ranked symbol instead of deliberately
spreading information across symbols, theses, and templates.

The next improvement should not add new strategy features. It should improve
candidate selection so a bounded campaign can ask more informative questions,
for example:

- avoid selecting the same symbol repeatedly unless the proposal explicitly
  justifies why that symbol remains the best information source;
- reward testing a different symbol after one symbol/thesis pair weakens;
- show the selected candidate's information-gain rationale in the final report;
- distinguish `budget exhausted` from true `search space exhausted`.

## Next

Improve candidate-ranking diversity before running a longer 30-minute campaign.
The campaign loop itself is coherent enough to use; the problem is now the
quality of the next-experiment menu and selection policy.
