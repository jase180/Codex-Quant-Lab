# SPY/TLT Static 60/40 Allocation Experiment

## Role

Tracked experiment handoff for ignored local artifacts in:

```text
artifacts/research/spy_tlt_static_60_40_allocation/
```

Read the portfolio evidence summary first when artifacts are available:

```text
artifacts/research/spy_tlt_static_60_40_allocation/portfolio_evidence_summary.md
```

## Why This Was Run

After several SPY single-asset timing ideas were rejected, this run tested a
different research family: static diversification. Codex selected this path
without Ollama because it is structurally different from another moving-average
cash-timing rule.

## Portfolio

Executable portfolio spec:

```text
data/portfolios/spy_tlt_static_60_40.json
```

Allocation:

- 60% SPY.
- 40% TLT.
- Monthly rebalance.
- Benchmark: SPY buy-and-hold over the same aligned date range.

## Data

Tracked SPY cache already existed:

```text
data/cache/SPY_2015-01-01_2025-12-31.csv
```

TLT was fetched with the project CLI:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli fetch `
  --symbol TLT `
  --start 2015-01-01 `
  --end 2025-12-31 `
  --out data\cache
```

Fetched TLT provenance:

- Provider: `yfinance`.
- Rows: `2765`.
- Data start: `2015-01-02`.
- Data end: `2025-12-30`.
- File SHA-256: `c90fde013d7154b4107042558c86c887df9387b2d2e411c1be8222ea7e9f800a`.
- Adjustment policy: `auto_adjust=true`, `actions=false`.

The raw cache files are ignored by Git.

## Prespecified Hypothesis

A static 60% SPY and 40% TLT allocation may reduce max drawdown versus SPY
buy-and-hold while retaining at least 60% of SPY CAGR.

## Prespecified Success Criteria

- `drawdown_reduction`: reduce max drawdown by at least `25%` relative to SPY
  buy-and-hold.
- `return_retention`: retain at least `60%` of SPY buy-and-hold CAGR.

## Commands

Create the experiment:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli new-experiment `
  --title "SPY TLT static 60/40 allocation test" `
  --hypothesis "A static 60% SPY and 40% TLT allocation may reduce max drawdown versus SPY buy-and-hold while retaining at least 60% of SPY CAGR." `
  --tag portfolio `
  --tag allocation `
  --tag diversification `
  --strategy data\portfolios\spy_tlt_static_60_40.json `
  --data data\cache\SPY_2015-01-01_2025-12-31.csv `
  --notes "Prespecified criteria: reduce max drawdown by at least 25% relative and retain at least 60% of SPY CAGR."
```

Run the baseline:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli portfolio-run `
  --portfolio data\portfolios\spy_tlt_static_60_40.json `
  --out artifacts\research\spy_tlt_static_60_40_allocation\baseline `
  --cost-preset retail-liquid `
  --experiment-id EXP-010
```

Run cost stress:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli portfolio-run `
  --portfolio data\portfolios\spy_tlt_static_60_40.json `
  --out artifacts\research\spy_tlt_static_60_40_allocation\cost_002_retail_conservative `
  --cost-preset retail-conservative `
  --experiment-id EXP-010

.\.venv-win\Scripts\python.exe -m quant_lab.cli portfolio-run `
  --portfolio data\portfolios\spy_tlt_static_60_40.json `
  --out artifacts\research\spy_tlt_static_60_40_allocation\cost_003_high_friction `
  --cost-preset high-friction `
  --experiment-id EXP-010
```

Write data-trust and evidence summaries:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli summarize-portfolio-data-trust `
  --metadata artifacts\research\spy_tlt_static_60_40_allocation\baseline\portfolio_metadata.json

.\.venv-win\Scripts\python.exe -m quant_lab.cli summarize-portfolio-experiment `
  --experiment-id EXP-010 `
  --out artifacts\research\spy_tlt_static_60_40_allocation\portfolio_evidence_summary.md
```

Record decision:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli decide-experiment `
  --experiment-id EXP-010 `
  --outcome reject `
  --rationale "Research-system status is valid: SPY and TLT data aligned with no data-trust warnings, three cost presets were tested, and all artifacts were saved. Strategy-hypothesis status is rejected for the exact 60/40 allocation because max drawdown improved only about 18.35% versus the 25% threshold, although CAGR retention passed at about 60.65% versus the 60% threshold." `
  --supporting-run artifacts\research\spy_tlt_static_60_40_allocation\baseline\portfolio_metadata.json `
  --contradicting-run artifacts\research\spy_tlt_static_60_40_allocation\baseline\portfolio_metadata.json `
  --next-action "Do not tune SPY/TLT weights immediately. Either test a genuinely different portfolio family or predefine a lower-drawdown defensive allocation before running." `
  --tag portfolio-result `
  --tag static-allocation
```

## Result

- Experiment id: `EXP-010`.
- Research-system status: `valid`.
- Strategy-hypothesis status: `rejected`.
- Decision: `reject`.
- Data trust: no warnings for SPY or TLT aligned inputs.
- Baseline total return: `137.71%`.
- SPY buy-and-hold total return: `302.73%`.
- Baseline excess total return: `-165.02%`.
- Baseline CAGR: `8.21%`.
- SPY benchmark CAGR: `13.54%`.
- CAGR retention: about `60.65%`, passing the `60%` threshold.
- Baseline max drawdown: `-27.53%`.
- SPY benchmark max drawdown: `-33.72%`.
- Relative drawdown reduction: about `18.35%`, failing the `25%` threshold.
- Baseline Sharpe: `0.7675`.
- SPY benchmark Sharpe: `0.8032`.

Cost stress:

- Retail conservative total return: `136.79%`, drawdown `-27.55%`, Sharpe `0.76`.
- High friction total return: `134.09%`, drawdown `-27.60%`, Sharpe `0.75`.

## What This Means

The repo succeeded at measuring the idea honestly and reproducibly. The exact
60/40 SPY/TLT allocation did not meet the predefined investment objective.

This is more nuanced than a simple failure. The allocation did what
diversification usually promises in a mild way: it lowered drawdown and retained
some growth. It did not lower drawdown enough to justify the lost SPY upside
under the threshold chosen before the run.

## Do Not Repeat

- Do not immediately tune SPY/TLT weights to rescue the result.
- Do not call the allocation successful just because CAGR retention barely
  passed.
- Do not ignore that the primary drawdown-reduction criterion failed.

## Next

If continuing portfolio research, use a materially different predefined idea,
such as a more defensive static allocation with a lower return-retention target
or a different asset mix. Do not sweep many weights without first writing why
the next hypothesis should behave differently.
