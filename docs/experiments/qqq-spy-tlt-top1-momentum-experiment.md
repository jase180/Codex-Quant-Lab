# QQQ/SPY/TLT Top-1 Momentum Experiment

Report role: tracked experiment handoff.

This note preserves the first post-SPY-only portfolio/rotation experiment. The
generated artifacts live under:

```text
artifacts/research/qqq_spy_tlt_top1_momentum/
```

Those artifacts are ignored by Git. This tracked note keeps the result visible.

## Why This Was Run

The SPY-only timing campaigns repeatedly found the same pattern: simple
long/cash rules reduced drawdown but gave up too much SPY buy-and-hold growth.

This experiment moved to a different mechanism: monthly multi-asset relative
strength across `QQQ`, `SPY`, and `TLT`. The idea was to let the portfolio rotate
into the strongest asset class, including `TLT` during defensive regimes, instead
of only switching SPY exposure on and off.

## Hypothesis

```text
A monthly top-1 relative-strength rotation across QQQ, SPY, and TLT may improve
drawdown-adjusted performance versus SPY buy-and-hold by moving into the
strongest asset class, including TLT during defensive regimes.
```

Prespecified criteria:

- retain at least `70%` of SPY buy-and-hold CAGR;
- reduce max drawdown by at least `20%` relative to SPY buy-and-hold;
- improve Sharpe after realistic costs.

## Setup

- Experiment id: `EXP-044`
- Portfolio: `data/portfolios/qqq_spy_tlt_top1_momentum.json`
- Allocation model: `top_n_relative_strength`
- Lookback: `63` aligned sessions
- Top N: `1`
- Rebalance: monthly
- Symbols: `QQQ`, `SPY`, `TLT`
- Benchmark: SPY buy-and-hold
- Base cost preset: `retail-liquid`

The portfolio engine used intersection alignment across the three symbols. All
symbols had `2765` aligned rows from `2015-01-02` to `2025-12-30`.

## Commands

Create the experiment:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli new-experiment `
  --title "QQQ SPY TLT top-1 relative-strength rotation" `
  --hypothesis "A monthly top-1 relative-strength rotation across QQQ, SPY, and TLT may improve drawdown-adjusted performance versus SPY buy-and-hold by moving into the strongest asset class, including TLT during defensive regimes." `
  --tag portfolio `
  --tag relative-strength `
  --tag defensive-asset-switching `
  --tag opportunity:fragmented_etf_relative_strength `
  --strategy data\portfolios\qqq_spy_tlt_top1_momentum.json `
  --data data\cache\SPY_2015-01-01_2025-12-31.csv `
  --notes "Prespecified criteria: retain at least 70% of SPY CAGR, reduce max drawdown by at least 20% relative, and improve Sharpe after realistic costs. Caveat: QQQ cache provenance sidecar is missing in the current local cache listing."
```

Run the portfolio:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli portfolio-run `
  --portfolio data\portfolios\qqq_spy_tlt_top1_momentum.json `
  --out artifacts\research\qqq_spy_tlt_top1_momentum\baseline `
  --cost-preset retail-liquid `
  --experiment-id EXP-044
```

Run cost stress:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli portfolio-run `
  --portfolio data\portfolios\qqq_spy_tlt_top1_momentum.json `
  --out artifacts\research\qqq_spy_tlt_top1_momentum\cost_002_retail_conservative `
  --cost-preset retail-conservative `
  --experiment-id EXP-044

.\.venv-win\Scripts\python.exe -m quant_lab.cli portfolio-run `
  --portfolio data\portfolios\qqq_spy_tlt_top1_momentum.json `
  --out artifacts\research\qqq_spy_tlt_top1_momentum\cost_003_high_friction `
  --cost-preset high-friction `
  --experiment-id EXP-044
```

Write supporting summaries:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli summarize-portfolio-data-trust `
  --metadata artifacts\research\qqq_spy_tlt_top1_momentum\baseline\portfolio_metadata.json

.\.venv-win\Scripts\python.exe -m quant_lab.cli summarize-portfolio-experiment `
  --experiment-id EXP-044 `
  --out artifacts\research\qqq_spy_tlt_top1_momentum\portfolio_evidence_summary.md
```

Record the decision:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli decide-experiment `
  --experiment-id EXP-044 `
  --outcome reject `
  --rationale "Research-system status is valid_with_caveats: the portfolio run saved metadata, aligned QQQ/SPY/TLT over 2765 rows, linked three cost-preset runs, and wrote a portfolio data-trust report, but the QQQ cache is missing a provenance sidecar. Strategy-hypothesis status is rejected because the retail-liquid baseline retained only about 32.5% of SPY CAGR, increased max drawdown relative to SPY, had lower Sharpe, and all cost presets had large negative excess return versus SPY buy-and-hold." `
  --supporting-run artifacts\research\qqq_spy_tlt_top1_momentum\baseline\portfolio_metadata.json `
  --contradicting-run artifacts\research\qqq_spy_tlt_top1_momentum\baseline\portfolio_metadata.json `
  --next-action "Do not tune this QQQ/SPY/TLT top-1 momentum branch. If continuing portfolio research, first fix QQQ provenance or test a materially different predefined portfolio mechanism with cleaner data-trust coverage." `
  --tag portfolio-result `
  --tag relative-strength-result `
  --tag valid-with-caveats
```

## Result

Research-system status: `valid_with_caveats`.

The repo aligned the portfolio inputs, saved metadata, linked three cost-preset
runs to the experiment, wrote a data-trust report, and wrote a portfolio evidence
summary. The caveat is that the local `QQQ` cache is missing a provenance
sidecar, while `SPY` and `TLT` have yfinance provenance sidecars.

Strategy-hypothesis status: `rejected`.

Retail-liquid baseline:

- Portfolio total return: `60.38%`
- SPY benchmark total return: `302.73%`
- Excess total return: `-242.35%`
- Portfolio CAGR: `4.40%`
- SPY benchmark CAGR: `13.54%`
- CAGR retention: about `32.5%`
- Portfolio max drawdown: `-50.86%`
- SPY benchmark max drawdown: `-33.72%`
- Portfolio Sharpe: `0.3287`
- SPY benchmark Sharpe: `0.8032`

Cost stress:

- Retail conservative total return: `44.50%`
- High-friction total return: `11.18%`
- No linked portfolio run beat SPY buy-and-hold on excess return.

## Interpretation

This portfolio did not provide defensive switching. It underperformed SPY
buy-and-hold badly, had worse drawdown, and had much lower Sharpe. The result is
not close under the stated criteria.

The useful research lesson is that simply rotating among `QQQ`, `SPY`, and `TLT`
by trailing 63-session relative strength is not a good next branch to tune. It
can chase the wrong asset class and does not appear to solve the return-retention
problem found in SPY-only timing.

## Do Not Repeat

Do not tune this exact Top-1 relative-strength branch by changing only the
lookback, rebalance month, or ETF order.

Do not call it a defensive asset-switching result. It is closer to broad
relative-strength rotation, and it failed to behave defensively.

Do not ignore the missing `QQQ` provenance sidecar if this family is revisited.
Fixing data provenance should happen before putting more confidence in
multi-asset QQQ/SPY/TLT results.

## Next

If continuing portfolio research, choose one of these before running:

- a true SPY-to-TLT or SPY-to-SHY regime-switch rule, after the engine can express
  signal-driven switching cleanly;
- a static or dynamic defensive allocation with a lower return-retention target
  and a clearly defensive objective;
- a different ETF universe where the opportunity thesis is genuinely about
  fragmented mandates rather than broad mega-cap asset timing.

Do not continue by parameter-sweeping this exact rotation rule.

