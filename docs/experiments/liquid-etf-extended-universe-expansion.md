# Liquid ETF Extended Universe Expansion

Report role: data-expansion handoff.

This note records the first ETF data expansion after the campaign runner proved
it could run bounded loops, diversify candidate ranking, carry branch memory,
and report budget-versus-search exhaustion clearly.

## What Changed

Added:

```text
data/universes/liquid_etf_extended.json
data/campaigns/liquid_etf_extended_discovery_campaign.json
```

The extended universe contains `63` ETF symbols across:

- broad US equity indexes;
- style and factor ETFs;
- sectors and industries;
- fixed income and cashlike ETFs;
- real assets and currency exposure;
- international and country ETFs.

The campaign config uses a representative `24`-symbol subset, `5` cycles,
`55` projected runs, and a `16`-candidate menu cap.

## Why ETFs, Not Stocks Yet

This deliberately expands ETF breadth before individual-stock research.
Individual stocks would add survivorship, delisting, membership-history,
liquidity, and corporate-action problems that the current lab should not
pretend to control automatically.

This is still mostly liquid, institutionally visible ETF territory. It is useful
for campaign mechanics and cross-market behavior checks, but it is not yet the
small-capacity niche layer.

## Fetch Result

Missing extended-universe symbols were fetched through:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli fetch --symbol <SYMBOL> `
  --start 2015-01-01 `
  --end 2025-12-31 `
  --out data\cache
```

The first sandboxed attempt failed because yfinance could not reach Yahoo. After
network approval, all missing extended ETFs fetched successfully.

Coverage check:

```text
missing_count=0
```

Cache inventory after fetch:

```text
csv_files=64
extended symbols with CSV + provenance=63/63
```

The extra CSV is an older small SPY adjusted-price audit file:

```text
data/cache/SPY_2024-01-02_2024-01-10.csv
```

It is unrelated to the extended universe and still lacks provenance.

## Candidate Menu Probe

Command:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign init `
  --config data\campaigns\liquid_etf_extended_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_extended_menu_probe `
  --force

.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign candidates `
  --campaign artifacts\campaigns\liquid_etf_extended_menu_probe
```

Result:

```text
status=ready
candidates=16
total_candidates_before_shortlist=144
rejected_candidates=0
```

The first shortlist covered multiple symbols, templates, and theses, including
EEM RSI pullback, EFA breakout, EWT RSI pullback, EWZ EMA trend, GLD RSI
pullback, HYG SMA, INDA breakout, IWM RSI pullback, KRE EMA trend, LQD RSI
pullback, MTUM SMA, RSP breakout, SMH RSI pullback, TIP EMA trend, TLT RSI
pullback, and USMV SMA.

## Interpretation

The project is now ready to try a bounded extended ETF campaign. This does not
mean the strategies are likely to work. It means the data universe, cache, and
candidate menu are broad enough to make the next 5-cycle run more informative
than the previous 10-symbol core campaign.

## Next

Run a short extended campaign:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\liquid_etf_extended_discovery_campaign.json `
  --out artifacts\campaigns\liquid_etf_extended_discovery_001 `
  --loop `
  --force
```

Read `final_report.md` first. Pay special attention to:

- whether selections diversify beyond EEM/EFA/GLD;
- whether all strategy hypotheses weaken again;
- whether `Candidate Availability` says budget ended or search exhausted;
- whether the best not-run candidate suggests a better next campaign scope.
