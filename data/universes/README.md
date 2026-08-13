# Research Universes

This folder contains tracked universe definitions. A universe is not market data
and is not an executable strategy. It is the explicit list of symbols the lab is
allowed to research for a given phase.

Cached OHLCV files live in `data/cache/`, which is intentionally ignored by Git.
Fetch data through `quant-lab fetch` so each CSV gets a provenance sidecar.

## Current Universe

- `liquid_etf_core.json`: first expanded ETF universe for daily multi-asset
  research. It gives campaigns more room than SPY/QQQ/TLT while staying inside
  the current engine's strengths.
- `liquid_etf_extended.json`: second-stage ETF universe for broader campaign
  discovery after the core loop proved execution, memory, diversity ranking,
  and final-report stop semantics.

## Fetch The Universe

From PowerShell in the repo root:

```powershell
$universe = Get-Content data\universes\liquid_etf_core.json | ConvertFrom-Json
foreach ($symbol in $universe.symbols) {
  .\.venv-win\Scripts\python.exe -m quant_lab.cli fetch `
    --symbol $symbol `
    --start $universe.date_range.start `
    --end $universe.date_range.end `
    --out data\cache
}
```

To fetch only missing files for a larger universe:

```powershell
$universe = Get-Content data\universes\liquid_etf_extended.json | ConvertFrom-Json
foreach ($symbol in $universe.symbols) {
  $csv = "data\cache\$($symbol)_$($universe.date_range.start)_$($universe.date_range.end).csv"
  $prov = $csv -replace '\.csv$', '.provenance.json'
  if ((Test-Path $csv) -and (Test-Path $prov)) {
    Write-Host "skip $symbol"
    continue
  }
  .\.venv-win\Scripts\python.exe -m quant_lab.cli fetch `
    --symbol $symbol `
    --start $universe.date_range.start `
    --end $universe.date_range.end `
    --out data\cache
}
```

For a less disruptive refresh, skip symbols that already have both CSV and
provenance files. That preserves older run fingerprints unless the symbol really
needs to be refreshed.

After fetching, inspect the cache:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli list-data-cache --data-dir data\cache
```

`XLRE`, `XLC`, `QUAL`, and some other newer or narrower ETFs can have later
inceptions than the requested 2015 start date, so portfolio experiments that
include them should expect a shorter intersection unless the experiment
explicitly starts later.

## Boundary

Use ETF universes before individual-stock universes. Individual stocks add
survivorship, delisting, historical membership, liquidity, and corporate-action
risks that this repo is not ready to control automatically.
