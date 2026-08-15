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

This slice ran the first no-trade diagnostic against SPY, QQQ, IWM, and TLT.

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

It does not simulate entries, exits, next-open fills, costs, sizing, or
benchmark-relative strategy performance.

## Result

Calendar rows:

- Total events: `174`
- Month-end events: `131`
- Quarter-end events: `43`

Summary:

| Symbol | Event Type | Events | Mean Window Return | Median Window Return | Positive Rate | Non-Event Mean Daily | Interpretation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| SPY | month_end | 131 | 0.75% | 0.82% | 64.12% | 0.04% | event windows higher than non-event days |
| SPY | quarter_end | 43 | 0.89% | 0.72% | 62.79% | 0.04% | event windows higher than non-event days |
| QQQ | month_end | 131 | 0.79% | 1.13% | 64.12% | 0.08% | similar to non-event days |
| QQQ | quarter_end | 43 | 0.73% | 0.84% | 65.12% | 0.08% | event windows lower than non-event days |
| IWM | month_end | 131 | 0.70% | 0.84% | 54.96% | 0.02% | event windows higher than non-event days |
| IWM | quarter_end | 43 | 0.37% | -0.02% | 48.84% | 0.02% | event windows higher than non-event days |
| TLT | month_end | 131 | 0.18% | 0.05% | 51.15% | -0.01% | event windows higher than non-event days |
| TLT | quarter_end | 43 | -0.42% | 0.04% | 51.16% | -0.01% | event windows lower than non-event days |

## Interpretation

The diagnostic found a visible positive month-end window average in SPY and IWM,
with QQQ positive in absolute terms but less distinct versus its non-event daily
average. TLT does not show the same clean behavior.

This is raw mechanism evidence, not alpha. Quarter-end rows overlap month-end
rows, so they are not independent samples. The current return definition uses
daily close-to-close returns inside a predeclared event window, which is useful
for direction-finding but not sufficient for an executable trading rule.

## What Carries Forward

This result makes the calendar/rebalance mechanism more concrete:

- There is enough directional evidence to justify a more careful no-trade
  event-study refinement.
- The next refinement should separate pre-event and post-event windows more
  explicitly instead of immediately creating a trading strategy.
- Any future strategy must predefine whether it is trying to capture pre-event
  drift, post-event reversal, or full-window exposure.

## Next

Do not create a calendar strategy yet. The next useful slice is to improve the
event-study summary so it can compare:

- pre-event window only,
- event day only,
- post-event window only,
- month-end excluding quarter-end,
- quarter-end separately.

That will tell us whether the apparent effect is concentrated before the event,
after the event, or just a broad positive-equity-window artifact.
