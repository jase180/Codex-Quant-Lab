# Calendar/Rebalance Event Study

Report role: tracked no-trade mechanism diagnostic.

Generated artifacts live under:

```text
artifacts/event-studies/calendar_rebalance_daily_proxy_2015_2025/
```

Those artifacts are ignored by Git. This note records the result so future
research does not need to rediscover it from the conversation.

## Why This Was Run

The project is moving away from generic ETF-indicator churn and toward
mechanism-first research. The `calendar_rebalance_effects` mechanism needed a
small auditable dataset before any strategy or backtest could be justified.

The prior slice created:

```text
data/event_calendars/calendar_rebalance_daily_proxy_2015_2025.csv
data/event_calendars/calendar_rebalance_daily_proxy_2015_2025.provenance.json
```

This slice ran and then refined the first no-trade diagnostic against SPY, QQQ,
IWM, and TLT.

## Command

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli event-calendar study `
  --calendar data\event_calendars\calendar_rebalance_daily_proxy_2015_2025.csv `
  --data SPY=data\cache\SPY_2015-01-01_2025-12-31.csv `
  --data QQQ=data\cache\QQQ_2015-01-01_2025-12-31.csv `
  --data IWM=data\cache\IWM_2015-01-01_2025-12-31.csv `
  --data TLT=data\cache\TLT_2015-01-01_2025-12-31.csv `
  --out artifacts\event-studies\calendar_rebalance_daily_proxy_2015_2025 `
  --force
```

## What The Command Does

This is not a backtest. It:

- validates the event calendar,
- loads close-to-close daily returns,
- compounds returns inside each event window,
- compares event windows with non-event days for the same symbol,
- writes `event_study_report.md`, `event_study.json`, and `event_returns.csv`.

It separates full-window, pre-event, event-day, and post-event close-to-close
returns. It also creates a derived `month_end_excluding_quarter_end` summary
view so regular month-end behavior can be inspected without quarter-end overlap.

It does not simulate entries, exits, next-open fills, costs, sizing, or
benchmark-relative strategy performance.

## Result

Calendar rows:

- Total events: `174`
- Month-end events: `131`
- Quarter-end events: `43`

Summary:

| Symbol | Event View | Events | Mean Window Return | Mean Pre | Mean Event Day | Mean Post | Positive Rate | Interpretation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| SPY | month_end | 131 | 0.75% | 0.37% | -0.05% | 0.45% | 64.12% | event windows higher than non-event days |
| SPY | month_end_excluding_quarter_end | 88 | 0.68% | 0.39% | -0.14% | 0.45% | 64.77% | event windows higher than non-event days |
| SPY | quarter_end | 43 | 0.89% | 0.32% | 0.11% | 0.45% | 62.79% | event windows higher than non-event days |
| QQQ | month_end | 131 | 0.79% | 0.29% | 0.03% | 0.48% | 64.12% | similar to non-event days |
| QQQ | month_end_excluding_quarter_end | 88 | 0.82% | 0.46% | -0.03% | 0.40% | 63.64% | similar to non-event days |
| QQQ | quarter_end | 43 | 0.73% | -0.07% | 0.16% | 0.65% | 65.12% | event windows lower than non-event days |
| IWM | month_end | 131 | 0.70% | 0.50% | -0.16% | 0.38% | 54.96% | event windows higher than non-event days |
| IWM | month_end_excluding_quarter_end | 88 | 0.87% | 0.60% | -0.30% | 0.58% | 57.95% | event windows higher than non-event days |
| IWM | quarter_end | 43 | 0.37% | 0.28% | 0.14% | -0.04% | 48.84% | event windows higher than non-event days |
| TLT | month_end | 131 | 0.18% | 0.32% | 0.14% | -0.28% | 51.15% | event windows higher than non-event days |
| TLT | month_end_excluding_quarter_end | 88 | 0.47% | 0.43% | 0.24% | -0.20% | 51.14% | event windows higher than non-event days |
| TLT | quarter_end | 43 | -0.42% | 0.08% | -0.07% | -0.43% | 51.16% | event windows lower than non-event days |

## Interpretation

The diagnostic found a visible positive month-end window average in SPY and IWM,
including month-end rows that exclude quarter-end overlap. QQQ is positive in
absolute terms but less distinct versus its own non-event daily average. TLT
does not show the same clean behavior.

The split matters: for SPY and IWM, the average regular month-end event day is
negative, while pre-event and post-event windows are positive. That means the
next research question should not be "buy month-end day." It should ask whether
there is a prespecified pre-event drift, post-event rebound, or broader window
effect that survives tighter checks.

This is raw mechanism evidence, not alpha. Quarter-end rows overlap month-end
rows, so they are not independent samples. The current return definition uses
daily close-to-close returns inside a predeclared event window, which is useful
for direction-finding but not sufficient for an executable trading rule.

## What Carries Forward

This result makes the calendar/rebalance mechanism more concrete:

- There is enough directional evidence to justify a more careful no-trade
  event-study refinement.
- The next refinement should compare these derived segments across more ETFs
  and eras instead of immediately creating a trading strategy.
- Any future strategy must predefine whether it is trying to capture pre-event
  drift, post-event reversal, or full-window exposure.

## Next

Do not create a calendar strategy yet. The next useful slice is a cross-symbol
and era robustness pass for this same no-trade event study. The specific
question is whether the month-end-excluding-quarter-end pre/post pattern appears
across other liquid ETFs and time slices, or whether it is mostly a SPY/IWM
sample artifact.
