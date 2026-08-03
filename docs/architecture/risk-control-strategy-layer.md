# Risk-Control Strategy Layer

Report role: design note.

The first post-v1 SPY research cycles showed that simple SMA long/cash rules can
reduce drawdown but may give up too much buy-and-hold return. The next strategy
capability should therefore focus on risk-control mechanisms that adjust
exposure deterministically, while preserving the backtest timing model.

## Boundary

Risk controls belong in the strategy/backtester layer first.

The local agent may recommend a mechanism and parameter range later, but it
should choose from a documented menu. It should not invent executable strategy
logic or rewrite the backtester.

## Current Implementation

Strategy schema v1 now accepts optional `risk_controls`.

Implemented control:

```json
{
  "kind": "volatility_target",
  "lookback": 20,
  "target_annual_vol": 0.12,
  "min_allocation": 0.25,
  "max_allocation": 1.0
}
```

Execution semantics:

- Signals are still evaluated on the daily close.
- Realized volatility uses close-to-close returns known at the signal close.
- The computed allocation scales only percent-equity entry orders.
- The scaled order still fills at the next bar open.
- Fixed-share sizing ignores risk controls.
- Multiple controls are represented as a list and combined by using the smallest
  allocation cap.

## Why Volatility Targeting First

The rejected SPY SMA tests suggest full long/cash exits are too blunt. A
volatility target gives the strategy a middle exposure state instead of forcing
every risk-control idea into either fully long or fully cash.

This directly tests whether partial exposure can keep more upside while still
reducing drawdown.

## Deferred Controls

Possible later controls:

- drawdown stop,
- trailing stop,
- cooldown after exit,
- partial trend exposure,
- risk-on/risk-off filter from another asset,
- stacked risk controls with explicit ordering and reporting.

Do not add these until the first volatility-target experiment has shown whether
the current hook is useful and understandable.

## Agent Use

Future agent recommendations should target the strict schema:

- mechanism: `volatility_target`,
- parameter candidates such as `lookback`, `target_annual_vol`,
  `min_allocation`, and `max_allocation`,
- reason grounded in the latest `experiment_conclusion.json`,
- no generated Python code.

