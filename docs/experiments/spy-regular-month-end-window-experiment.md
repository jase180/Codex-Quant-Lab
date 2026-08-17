# SPY Regular Month-End Window Experiment

Report role: tracked strategy-result note.

Generated artifacts live under:

```text
artifacts/research/spy_regular_month_end_window_002/
```

Those artifacts are ignored by Git. This note records the result so the next
research cycle starts from the conclusion, not from memory.

## Why This Was Run

The no-trade calendar/rebalance event study found that regular month-end
windows, excluding quarter-end overlap, were broadly positive across liquid ETFs
in 2019-2021 and 2022-2025. Before adding any timing sweep, the project tested
one prespecified SPY rule.

Opportunity thesis:

```text
calendar_flow_pressure
```

## Prespecified Hypothesis

A predeclared regular month-end SPY event-window strategy may improve
drawdown-adjusted behavior versus SPY buy-and-hold by only being exposed around
month-end windows that exclude quarter-end overlap.

Trade timing caveat:

```text
Signals are produced from the event-window state at bar t close and fill at bar
t+1 open. The strategy therefore enters after the first in-window close and
exits after the first out-of-window close.
```

## Success Criteria

The strategy was not required to beat SPY total return. Because this is a
low-exposure timing rule, success was defined as:

- positive total return,
- at least 50% relative max-drawdown reduction versus SPY buy-and-hold,
- Sharpe ratio no worse than SPY buy-and-hold.

## Command

The command was run through `quant_lab.cli.main([...])` from inline Python
because the local shell wrapper stripped JSON quotes from `--success-criterion`
arguments. The actual CLI arguments were:

```text
quant-lab experiment run-default
  --title "SPY regular month-end window timing"
  --strategy data/strategies/spy_regular_month_end_window.json
  --data data/cache/SPY_2015-01-01_2025-12-31.csv
  --symbol SPY
  --cost-preset retail-liquid
  --tag opportunity:calendar_flow_pressure
  --tag mechanism:calendar_rebalance_effects
  --tag template:calendar-month-end
  --tag event_window
  --tag no_timing_sweep
  --primary-metric sharpe
  --success-criterion positive_total_return >= 0
  --success-criterion drawdown_reduction >= 50%
  --success-criterion sharpe_not_worse_than_benchmark >= 0
  --param regular_month_end_window.inputs.calendar_path=data/event_calendars/calendar_rebalance_daily_proxy_2015_2025.csv
  --train-end 2020-12-31
  --test-start 2021-01-01
  --date-window 2015-01-02,2018-12-31
  --date-window 2019-01-01,2021-12-31
  --date-window 2022-01-01,2025-12-30
  --out artifacts/research/spy_regular_month_end_window_002
```

The single `--param` is a no-op calendar-path override. It exists only because
the current default workflow always runs sweep/train-test validation and
requires at least one parameter value.

## Result

Canonical conclusion:

```text
artifacts/research/spy_regular_month_end_window_002/experiment_conclusion.md
```

Outcomes:

- Research-system status: `valid`
- Strategy-hypothesis status: `partially_supported`
- Opportunity-thesis status: `weakened`
- Confidence label: `rejected`
- Registry decision: `reject`

Prespecified criteria:

| Criterion | Result | Observed |
| --- | --- | ---: |
| positive total return | pass | 38.33% in selected test record |
| drawdown reduction | pass | 63.51% relative reduction |
| Sharpe not worse than benchmark | fail | -0.1850 Sharpe delta |

Baseline full-period strategy metrics:

| Metric | Value |
| --- | ---: |
| Total return | 60.73% |
| CAGR | 4.42% |
| Max drawdown | -15.22% |
| Sharpe | 0.48 |
| Trades | 176 |

## Validation

Train/test:

- Train selected run total return: 16.20%
- Test total return: 38.33%
- Test excess total return versus SPY buy-and-hold: -61.24%

Date sensitivity:

| Window | Return | Excess vs Buy-and-Hold | Drawdown | Sharpe |
| --- | ---: | ---: | ---: | ---: |
| 2015-2018 | -1.31% | -33.07% | -11.46% | 0.00 |
| 2019-2021 | 23.55% | -76.13% | -15.22% | 0.66 |
| 2022-2025 | 31.83% | -20.21% | -8.94% | 0.74 |

Cost sensitivity:

| Cost Preset | Return | Excess vs Buy-and-Hold | Drawdown | Sharpe |
| --- | ---: | ---: | ---: | ---: |
| retail-liquid | 60.73% | -241.99% | -15.22% | 0.48 |
| retail-conservative | 34.79% | -267.93% | -17.36% | 0.32 |
| high-friction | -13.37% | -316.10% | -32.74% | -0.08 |

## Interpretation

The repo succeeded: it executed the event-window strategy through the normal
next-open, costed, validated workflow and saved the strategy plus input
metadata.

The strategy did not clear its prespecified investment hurdle. It made money
and reduced drawdown, but the Sharpe criterion failed, date sensitivity failed,
and stricter costs damaged the result materially. The `calendar_flow_pressure`
thesis is therefore weakened, not fully rejected: the no-trade evidence remains
interesting, but this exact SPY full-window timing rule is not strong enough.

## What Carries Forward

Do not repeat this exact branch:

```text
opportunity=calendar_flow_pressure
template=calendar-month-end
symbol=SPY
timing=full_regular_month_end_window
```

Future work should first explain the failure mode. Plausible explanations:

- next-open execution gives up too much of the close-to-close diagnostic effect,
- turnover and costs are too high for the small edge,
- the broad window mixes pre-event and post-event behavior that should be
  tested separately,
- SPY is too efficient for this visible calendar effect.

## Next

Do not widen into a timing sweep yet. The next useful slice is consolidation:
make event-window strategy support more explicit in docs/schema, then decide
whether to test a different symbol or a genuinely different timing hypothesis.
