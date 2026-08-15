# Event Calendars

This folder stores generated event calendars used as raw material for
mechanism-first research.

Event calendars are not strategies. They define dated windows before joining
returns, indicators, or backtest results. That distinction matters because the
event rows should be chosen from market structure or calendar rules, not from
observed performance.

Current generated calendar:

- `calendar_rebalance_daily_proxy_2015_2025.csv`: month-end and quarter-end
  trading-day events generated from the SPY trading-date calendar for
  2015-01-01 through 2025-12-31.
- `calendar_rebalance_daily_proxy_2015_2025.provenance.json`: source file
  fingerprint, construction settings, counts, and skipped edge-window notes.

Inspect it with:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli event-calendar inspect `
  --calendar data\event_calendars\calendar_rebalance_daily_proxy_2015_2025.csv
```

Run the first no-trade event study with:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli event-calendar study `
  --calendar data\event_calendars\calendar_rebalance_daily_proxy_2015_2025.csv `
  --data SPY=data\cache\SPY_2015-01-01_2025-12-31.csv `
  --data QQQ=data\cache\QQQ_2015-01-01_2025-12-31.csv `
  --data IWM=data\cache\IWM_2015-01-01_2025-12-31.csv `
  --data TLT=data\cache\TLT_2015-01-01_2025-12-31.csv `
  --out artifacts\event-studies\calendar_rebalance_daily_proxy_2015_2025
```

This command joins returns for inspection only. It does not simulate a strategy.
Use repeatable `--era NAME=START,END` arguments when you want the same
diagnostic split across time periods.

Regenerate it with:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli event-calendar generate `
  --reference-data data\cache\SPY_2015-01-01_2025-12-31.csv `
  --out data\event_calendars\calendar_rebalance_daily_proxy_2015_2025.csv `
  --start 2015-01-01 `
  --end 2025-12-31 `
  --window-trading-days 5 `
  --created-at-utc 2026-08-14T00:00:00Z `
  --force
```
