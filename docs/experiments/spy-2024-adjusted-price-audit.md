# SPY 2024 Adjusted-Price Audit

Report role: correctness audit handoff.

This note records the first broader adjusted-price audit for the cached SPY
daily data used by recent strategy experiments. The generated audit artifacts
are ignored by Git; this tracked note preserves the result and its limits.

## Question

Do the provider-adjusted SPY prices used by the lab line up with the same
provider's raw `Adj Close` field and visible dividend rows around known 2024
SPY distribution dates?

This matters because the lab fetches daily prices with:

- `auto_adjust=True`
- `actions=False`

That means dividends and splits are reflected indirectly through adjusted OHLCV
prices, not stored as explicit cash-flow or split events in the cached run data.

## External Event Dates Used

Expected 2024 SPY ex-dividend dates:

- `2024-03-15`
- `2024-06-21`
- `2024-09-20`
- `2024-12-20`

These dates were cross-checked against public SPY distribution listings before
running the audit. The yfinance audit itself remains provider-internal because
it compares yfinance adjusted data to yfinance raw/action data.

## Command

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli audit-adjusted-prices `
  --symbol SPY `
  --start 2024-01-01 `
  --end 2025-01-10 `
  --out artifacts\data-audits\spy_2024_dividends `
  --expected-dividend-date 2024-03-15 `
  --expected-dividend-date 2024-06-21 `
  --expected-dividend-date 2024-09-20 `
  --expected-dividend-date 2024-12-20
```

The command needed normal network access to yfinance. A sandboxed attempt
returned empty provider data; the same command succeeded after network
escalation.

## Generated Artifacts

- `artifacts/data-audits/spy_2024_dividends/adjusted_price_audit.md`
- `artifacts/data-audits/spy_2024_dividends/adjusted_price_audit.json`
- `artifacts/data-audits/spy_2024_dividends/adjusted_price_comparison.csv`

## Result

Audit result: `pass`

- Rows compared: `257`
- Max close difference: `0.0`
- Tolerance: `0.01`
- Corporate-action rows found: `4`
- Missing expected dividends: none
- Missing expected splits: none
- Warnings: none

Event rows found:

| date | auto-adjust close | raw Adj Close | raw close | dividend | stock split |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2024-03-15` | `496.43817138671875` | `496.43817138671875` | `509.8299865722656` | `1.595` | `0.0` |
| `2024-06-21` | `531.9177856445312` | `531.9177856445312` | `544.510009765625` | `1.759` | `0.0` |
| `2024-09-20` | `556.8113403320312` | `556.8113403320312` | `568.25` | `1.746` | `0.0` |
| `2024-12-20` | `581.199951171875` | `581.199951171875` | `591.1500244140625` | `1.966` | `0.0` |

## Interpretation

This supports the current cached SPY data policy for the audited 2024 dividend
window. The adjusted close returned by `auto_adjust=True` matched yfinance's raw
`Adj Close` field exactly on all compared rows, and the expected 2024 dividend
dates appeared as action rows in the raw/action view.

This does not prove every SPY backtest result is economically correct. It is
still not a second-source validation, and the backtester still does not model
dividends as separate cash payments. The result says the provider views are
internally consistent for this audited window.

## Carry-Forward Judgment

Current SPY conclusions can continue using the cached adjusted-price data, with
this caveat:

- acceptable for provider-adjusted daily research,
- not sufficient for institutional-grade corporate-action validation,
- not a replacement for an independent data-source comparison.

Before making stronger claims, run either:

- a second-source audit against another provider, or
- a wider event audit across more SPY dividend years and any known split-heavy
  symbols used in future experiments.
