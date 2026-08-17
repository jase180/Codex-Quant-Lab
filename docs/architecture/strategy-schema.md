# Strategy Schema v1

`strategy-schema` defines a narrow, strict representation for simple rule-based long-only daily strategies.

## Design goals

- Keep v1 explicit enough for deterministic validation and safe parsing.
- Keep the structure machine-friendly so an LLM can later emit the same normalized fields.
- Limit the surface area to the minimum needed for initial research and backtesting.

## Backtesting semantics

These rules are part of the v1 contract, not implementation details:

- Daily OHLCV only: `market.timeframe` must be exactly `1d`.
- Long-only only: short entries, leverage, and position sizing logic are out of scope for v1.
- Signals are evaluated on the daily close.
- Fills occur on the next trading day's open.
- Indicator inputs are close-only in v1, so every indicator and direct price comparison is derived from the same end-of-day signal snapshot.
- Event-window indicators use predeclared event calendars and are evaluated
  from the bar date at the same signal point. They do not inspect returns when
  deciding whether a date is inside a window.

This keeps the schema deterministic for backtesting and simple enough for future LLM generation.

## Schema shape

Each strategy document is a JSON object with these top-level fields:

- `schema_version`: must be `v1`
- `strategy_id`: stable snake_case identifier
- `name`: human-readable strategy name
- `description`: short explanation of intent
- `strategy_type`: must be `rule_based`
- `position_mode`: must be `long_only`
- `market`: `{symbol, timeframe}`
- `indicators`: array of declared indicators
- `entry`: condition set for opening a position
- `exit`: condition set for closing a position
- `risk_controls`: optional array of deterministic allocation controls

### Indicators

Indicators are declared before they are referenced in rules:

```json
{
  "id": "sma_20",
  "kind": "sma",
  "inputs": {
    "source": "close",
    "length": 20
  }
}
```

Supported v1 indicator kinds:

- `sma`
- `ema`
- `rsi`
- `rolling_high`
- `rolling_low`
- `event_window`

`rolling_high` and `rolling_low` use the prior `length` closes, excluding the
current close. That makes breakout rules like `close > high_20` possible
without lookahead: the current close is compared with a level known before the
current close is added to the rolling window.

`event_window` is date-based rather than price-based:

```json
{
  "id": "regular_month_end_window",
  "kind": "event_window",
  "inputs": {
    "calendar_path": "data/event_calendars/calendar_rebalance_daily_proxy_2015_2025.csv",
    "include_event_types": ["month_end"],
    "exclude_event_types": ["quarter_end"]
  }
}
```

It returns `1.0` when the bar date is inside an included predeclared event
window and `0.0` otherwise. Excluded event types remove included rows with the
same `event_date`, which is how regular month-end can exclude quarter-end
overlap. Signals still fill at the next open, so the first possible entry is
the next open after an in-window close.

### Conditions

Rules use a normalized left-operator-right shape:

```json
{
  "left": {"indicator": "sma_20"},
  "operator": "crosses_above",
  "right": {"indicator": "sma_50"}
}
```

Supported value references:

- `{"price": "close"}`
- `{"indicator": "declared_indicator_id"}`
- `{"value": 30}`

In v1, `{"price": "close"}` is the only allowed direct price reference. `open`, `high`, `low`, and `volume` are intentionally excluded from rule expressions to avoid ambiguous same-bar interpretations.

Supported operators:

- `gt`
- `gte`
- `lt`
- `lte`
- `eq`
- `crosses_above`
- `crosses_below`

### Risk controls

Risk controls are optional. They do not create entry or exit signals. They only
scale the allocation used by percent-equity entry orders after an entry signal
has already fired.

The first supported control is `volatility_target`:

```json
{
  "kind": "volatility_target",
  "lookback": 20,
  "target_annual_vol": 0.12,
  "min_allocation": 0.25,
  "max_allocation": 1.0
}
```

Semantics:

- realized volatility is computed from close-to-close returns available at the
  signal close,
- the scaled allocation is attached to the order that fills on the next open,
- allocation is clamped between `min_allocation` and `max_allocation`,
- fixed-share sizing ignores risk controls in v1,
- multiple controls are combined conservatively by using the smallest allocation
  cap.

This keeps risk controls close-based and avoids same-bar lookahead.

## Rejected inputs

Validation should fail fast and clearly for:

- any timeframe other than `1d`
- undeclared indicator references
- duplicate indicator IDs
- unsupported operators
- malformed value refs that include multiple keys or non-numeric constants
- direct price refs other than `close`
- indicator inputs with non-`close` sources
- event-window indicators without a calendar path or included event types
- unknown risk control kinds
- volatility-target controls with non-positive lookbacks, non-positive target
  volatility, invalid allocation bounds, or `min_allocation > max_allocation`

## Why this is LLM-friendly later

This structure is intentionally close to how a natural-language extraction pipeline would normalize intent:

- "Buy when the 20-day SMA crosses above the 50-day SMA" maps cleanly into two declared indicators plus one `crosses_above` condition.
- "Exit when RSI gets above 55" maps into an indicator reference, a numeric constant, and a comparison operator.
- "Buy when close breaks above the prior 20-day high" maps into a
  `rolling_high` indicator plus a `gt` condition.
- Because indicators, operators, and reference types are enumerated, an NLP or LLM system can target a small controlled vocabulary instead of emitting free-form code.

That makes a future NLP layer easier to build in two stages:

1. Extract candidate fields from text into this schema.
2. Run the same strict validator used for hand-authored strategies and return actionable errors for anything missing or ambiguous.

## Deferred for later versions

Intentionally not included in v1:

- intraday or weekly timeframes
- short-selling or multi-position modes
- stop loss, take profit, trailing exits, or bracket orders
- multi-asset universes and portfolio allocation rules
- parameter ranges or optimization metadata inside strategy files
- richer indicator graphs or indicators built from non-close sources
