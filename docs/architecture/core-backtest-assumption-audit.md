# Core Backtest Assumption Audit

Report role: supporting interpretation.

This audit records the current simulation assumptions that experiment
conclusions depend on. It is not a claim that the backtester is production
grade. It names what the lab currently does, what tests cover, and what should
stay visible in future research.

## Scope

Audited areas:

- market data adjustment assumptions,
- dividends and splits,
- next-open fills,
- cash after exits,
- benchmark date alignment,
- indicator warm-up,
- final-bar signals,
- transaction costs.

## Current Verdict

The current engine is acceptable for a small daily-bar research lab when reports
stay explicit about the assumptions.

The biggest unresolved uncertainty is market data semantics. `quant-lab fetch`
uses `yfinance` with `auto_adjust=True` and `actions=False`, so the saved CSV is
adjusted OHLCV data without separate dividend or split event rows. That is fine
for learning and broad research checks, but not enough for institutional-grade
total-return accounting or provider reconciliation.

## Market Data And Adjustments

Current behavior:

- `quant_lab.data_fetch.fetch_market_data` calls `yfinance.download` with:
  - `auto_adjust=True`
  - `actions=False`
  - `interval="1d"`
- `normalize_ohlcv_frame` writes the daily columns:
  - `date`
  - `open`
  - `high`
  - `low`
  - `close`
  - `volume`
- Provenance sidecars record provider, requested range, actual range, row
  count, fetch timestamp, CSV fingerprint, and price-adjustment policy:
  - `auto_adjust=True`
  - `actions=False`
- `show-data-source`, single-run trust reports, and portfolio data trust
  reports display the recorded price-adjustment policy when provenance is
  available.
- `audit-adjusted-prices` can write a provider-internal audit for one
  corporate-action window by downloading both adjusted OHLCV and raw OHLCV with
  `Adj Close`, dividends, and splits. It compares adjusted close to raw
  `Adj Close` and compares adjusted open/high/low/close to raw OHLC multiplied
  by the raw `Adj Close / Close` adjustment ratio. It can also accept manually
  supplied expected dividend amounts in `YYYY-MM-DD=amount` form and compare
  those amounts to the provider's raw dividend action rows.

Implication:

- Prices are adjusted according to the provider's `auto_adjust` behavior.
- Dividends and splits are reflected indirectly in adjusted prices, not stored
  as explicit cash flows or corporate-action rows.
- Volume is retained from the provider output but is not currently used by the
  execution model.

Current coverage:

- Data fetch and provenance tests cover CSV shape, the actual
  `yfinance.download` adjustment arguments, price-adjustment policy metadata,
  provenance writing, and cache inspection.
- Trust report tests cover showing the recorded adjustment policy in single-run
  and portfolio evidence reports.
- Adjusted-price audit tests cover comparing `auto_adjust=True` close to the
  provider's `Adj Close`, comparing adjusted open/high/low/close to raw OHLC
  adjusted by the provider's `Adj Close / Close` ratio, expected event-date
  checks, expected dividend-amount mismatch warnings, and the CLI command with
  a mocked provider.
- Run trust reports can verify that a later local CSV still matches the saved
  run fingerprint.

Known gap:

- The lab does not automatically fetch a second source for dividend or split
  events. Important experiments can now pass manually verified dividend amounts
  into `audit-adjusted-prices`, but the human or Codex still has to source
  those values.
- The lab does not model dividends as cash distributions.
- The lab does not preserve unadjusted OHLC plus corporate actions.
- `audit-adjusted-prices` is provider-internal verification, not proof that
  yfinance agrees with another vendor or official corporate-action source.

Status:

- Acceptable for local research if conclusions say provider assumptions may
  matter.
- Current improvement: fetched CSV provenance now records the adjusted-price
  policy, trust reports surface it, and `audit-adjusted-prices` can inspect a
  known corporate-action window across adjusted OHLC and manually supplied
  dividend amounts. Future improvement: add optional second-source checks
  against another provider.

## Next-Open Fills

Current behavior:

- `BacktestEngine.run` records orders generated on bar `t`.
- Those pending orders are filled on bar `t+1` using that next bar's `open`.
- Portfolio history is recorded after queued fills and marked at the same day's
  `close`.
- When the input CSV was fetched with the default policy, both the fill `open`
  and mark-to-market `close` are provider-adjusted prices.

Implication:

- Strategy signals can use bar `t` close data without pretending they traded at
  that already-known close.
- Gaps between signal close and next open are included in the result.
- Fills are internally coherent with the adjusted series because the strategy,
  execution price, mark-to-market price, and buy-and-hold benchmark all use the
  same adjusted OHLC data. They are not literal historical raw exchange prints.

Current coverage:

- `tests/test_backtester_core.py` covers:
  - no fill on the signal bar,
  - next-bar-open fill price and timestamp,
  - gap-up and gap-down fills,
  - final-bar signals not filling.
- `tests/test_rule_based_strategy.py` covers final-bar signal behavior through
  the rule-based strategy path.
- `tests/test_portfolio_backtest.py` covers next-open rebalance fills for
  static-weight portfolio runs.

Status:

- Acceptable and central to the lab. Preserve this rule unless a future schema
  explicitly introduces another execution timing model.

## Cash, Positions, And Exits

Current behavior:

- `Portfolio.apply_fill` subtracts buy cost plus commission from cash.
- Sells add proceeds minus commission to cash.
- Position quantity is reduced on sells.
- Portfolio equity is `cash + position * current_close`.
- Percent-equity buys solve quantity so the requested cash allocation includes
  commission and slippage-adjusted price.

Implication:

- Exits return cash immediately at the fill timestamp.
- Uninvested cash stays in the account as cash.
- There is no interest on idle cash unless the selected benchmark is `cash`,
  which is only a comparison curve, not strategy account interest.

Current coverage:

- Tests cover buy/sell cash updates, commissions, insufficient position errors,
  equity reconciliation, and percent-equity sizing with costs.

Known gap:

- No margin, borrowing, short selling, cash interest, tax accounting, or partial
  fills.

Status:

- Acceptable for long-only daily research.

## Benchmarks And Date Alignment

Current behavior:

- Strategy benchmarks use the same input data rows as the strategy run.
- Buy-and-hold buys with all initial cash at the first `close`, then marks at
  each later `close`.
- Cash benchmark stays flat over the same dates.
- Strategy excess return is `strategy_total_return - benchmark_total_return`.
- With the default fetched CSV, buy-and-hold uses the provider-adjusted close
  series. That makes it a total-return-style comparison to the same adjusted
  price series used by strategy signals and marks.

Implication:

- Strategy fills use next opens, but buy-and-hold benchmark enters at first
  close. This is simple and reproducible, but not identical execution timing.
- Benchmark comparison is aligned to the strategy input rows.
- Because the benchmark uses adjusted close values, dividend effects embedded
  in the provider adjustment are reflected through the adjusted price path, not
  through explicit dividend cash payments.

Current coverage:

- Benchmark tests cover buy-and-hold and cash curve behavior.
- Benchmark tests cover that buy-and-hold total return follows the input close
  series exactly, which is the adjusted close series for default fetched data.
- Run and sweep tests check benchmark fields in reports, summaries, metadata,
  and research index rows.

Known gap:

- Buy-and-hold does not currently pay transaction costs.
- Buy-and-hold entry timing is first close, not first next open.
- Buy-and-hold does not model dividend cash flows separately from adjusted
  prices.
- There is no blended or multi-benchmark strategy baseline yet.

Status:

- Acceptable as a simple comparison hurdle, but conclusions should avoid
  treating benchmark excess return as a precise live-tradable spread.

## Indicator Warm-Up And Signal Inputs

Current behavior:

- v1 indicators are close-based.
- SMA returns `None` until it has `length` closes.
- EMA seeds from the first close and returns a value immediately after the first
  update.
- RSI returns `None` until it has enough close-to-close changes.
- `rolling_high` and `rolling_low` use the prior `length` closes, excluding the
  current close.
- Conditions with a `None` input evaluate to `False`.
- Crossover operators require both current and previous values.

Implication:

- SMA/RSI warm-up naturally suppresses early signals.
- EMA can produce early values sooner than SMA.
- Breakout rules compare today's close against a prior-window level, not a
  window contaminated by today's close.

Current coverage:

- Rule-based strategy tests cover rolling high/low prior-window behavior,
  final-bar no-fill, and percent-equity next-open sizing.
- Strategy schema tests enforce close-only indicator inputs in v1.

Known gap:

- The lab does not yet have a dedicated audit table for warm-up behavior across
  every indicator kind in docs.
- EMA seeding choice is simple and deterministic, but different platforms seed
  EMA differently.

Status:

- Acceptable for v1 if reports keep indicator assumptions visible.

## Final-Bar Signals

Current behavior:

- Signals generated on the last available bar are queued but never filled
  because there is no next open.

Implication:

- Backtests do not invent an execution price after the dataset ends.
- Final equity may include an open position marked at the final close.

Current coverage:

- Core engine tests and rule-based strategy tests cover final-bar no-fill.
- Portfolio tests cover final-bar rebalance no-fill.

Status:

- Acceptable and should remain unchanged.

## Transaction Costs

Current behavior:

- Cost presets live in `quant_lab.costs`:
  - `none`
  - `retail-liquid`
  - `retail-conservative`
  - `high-friction`
- Explicit cost flags override preset numeric values.
- Buy fills pay above open when slippage is nonzero.
- Sell fills receive below open when slippage is nonzero.
- Commission is fixed fee plus rate times notional.
- Costs are stored in run metadata, sweep summaries, and research index rows.

Implication:

- Costs affect strategy fills, cash, and equity.
- Benchmark curves do not currently include transaction costs.

Current coverage:

- Core tests cover execution price, commission, and cash-allocation sizing with
  costs.
- CLI tests cover cost preset metadata and explicit override behavior.
- Robustness commands can rerun a setup across cost presets.

Known gap:

- No market impact, spread model beyond fixed bps, partial fills, liquidity
  limits, or order-size constraints.

Status:

- Acceptable for small daily-bar research and skepticism checks.

## Do Not Hide These Caveats

Experiment conclusions and README/workflow docs should keep these caveats
visible:

- Provider-adjusted data may not match another data source.
- Dividends and splits are not explicit cash-flow events.
- Benchmarks are simple comparison curves, not perfect live trading
  simulations.
- The execution model is daily next-open market fills only.
- No liquidity, margin, shorting, taxes, or market impact is modeled.

## Recommended Follow-Ups

1. Add a small doc table showing warm-up behavior for each indicator.
2. Add an automated second-source data verification path for important
   experiments.
3. Add a visible corporate-action check to the canonical SPY experiment.
4. Consider a buy-and-hold benchmark entry timing option that buys at first next
   open for stricter execution symmetry.
5. Keep core behavior unchanged until tests are written for any proposed
   realism change.
