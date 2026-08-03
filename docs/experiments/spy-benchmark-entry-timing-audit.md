# SPY Benchmark Entry-Timing Audit

Report role: correctness audit handoff.

This note checks whether the canonical SPY 200-day SMA long/cash conclusion
depends on the current buy-and-hold benchmark entering at the first input close
while the strategy itself uses next-open fills.

## Question

Would the SPY 200-day SMA long/cash experiment look materially better if
buy-and-hold used an execution-symmetric next-open entry instead of the current
first-close benchmark construction?

This matters because the current benchmark is a simple comparison curve:

- fully invested at the first input close,
- marked at each later close,
- no transaction costs,
- dividends embedded only when the input price series is adjusted.

The strategy is different: signals generated on bar `t` fill at bar `t+1`
open, with configured costs and slippage.

## Method

Using `data/cache/SPY_2015-01-01_2025-12-31.csv`, compare:

- current benchmark total return:
  `final adjusted close / first adjusted close - 1`
- execution-symmetric benchmark total return:
  `final adjusted close / second-row adjusted open - 1`

For the linked `EXP-003` SPY default-workflow runs, recompute both benchmark
returns for each run's saved `data_start` and `data_end`, then check whether
the strategy's excess return changes sign.

The audited experiment conclusion is:

- `artifacts/research/spy_200_sma_long_cash_default_benchmark/experiment_conclusion.md`

## Baseline Result

Full-window baseline:

| Item | Value |
| --- | ---: |
| Start date | `2015-01-02` |
| First adjusted close | `169.68785095214844` |
| Next date | `2015-01-05` |
| First next adjusted open | `168.6470505972124` |
| End date | `2025-12-30` |
| Final adjusted close | `683.3783569335938` |
| Current first-close benchmark return | `302.73%` |
| Next-open benchmark return | `305.21%` |
| Difference | `+2.49 percentage points` |
| Strategy return | `148.39%` |
| Current excess return | `-154.34 percentage points` |
| Next-open excess return | `-156.83 percentage points` |

The timing adjustment makes the benchmark slightly harder, not easier, for this
baseline window.

## Linked-Run Sweep

`EXP-003` linked buy-and-hold comparisons checked: `16`

- Largest absolute benchmark-return difference:
  `2.67 percentage points`
- Excess-return sign changes:
  `0`
- Largest difference occurred in:
  `date_sensitivity_run/window_002`
- `window_002` first-close benchmark return:
  `130.77%`
- `window_002` next-open benchmark return:
  `133.44%`
- `window_002` strategy return:
  `85.03%`
- `window_002` current excess return:
  `-45.74 percentage points`
- `window_002` next-open excess return:
  `-48.41 percentage points`

Representative windows:

| Run | Dates | Strategy return | First-close benchmark | Next-open benchmark | Excess sign changed |
| --- | --- | ---: | ---: | ---: | --- |
| baseline | `2015-01-02` to `2025-12-30` | `148.39%` | `302.73%` | `305.21%` | no |
| train window | `2015-01-02` to `2020-12-31` | `44.78%` | `104.59%` | `105.85%` | no |
| test selected | `2021-01-04` to `2025-12-30` | `41.83%` | `99.56%` | `99.94%` | no |
| date window 002 | `2020-01-02` to `2025-12-30` | `85.03%` | `130.77%` | `133.44%` | no |
| date window 003 | `2018-01-02` to `2022-12-30` | `21.02%` | `54.98%` | `54.87%` | no |

## Interpretation

The current SPY conclusion does not depend on the benchmark entering at the
first close. Replacing the current benchmark with a next-open entry would not
turn any linked buy-and-hold comparison from negative excess return to positive
excess return. In the main full-window baseline, it would make the long/cash
strategy underperform by slightly more.

This does not mean the current benchmark construction is perfect. The
first-close benchmark should stay visibly labeled as a simple comparison hurdle,
not a live executable trade simulation. But this audit says the entry-timing
choice is not the reason the SPY 200-day SMA long/cash branch failed.

## Carry-Forward Judgment

- Keep the current buy-and-hold benchmark for now.
- Do not add an execution-symmetric benchmark mode yet; the measured difference
  is too small to justify another public option before more real experiments.
- Keep recording benchmark assumptions in `report.md` and `run_metadata.json`.
- Revisit an execution-symmetric benchmark only if a future strategy's excess
  return is close enough that a 1-3 percentage-point benchmark construction
  difference could change the decision.
