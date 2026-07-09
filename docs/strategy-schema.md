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

`rolling_high` and `rolling_low` use the prior `length` closes, excluding the
current close. That makes breakout rules like `close > high_20` possible
without lookahead: the current close is compared with a level known before the
current close is added to the rolling window.

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

## Rejected inputs

Validation should fail fast and clearly for:

- any timeframe other than `1d`
- undeclared indicator references
- duplicate indicator IDs
- unsupported operators
- malformed value refs that include multiple keys or non-numeric constants
- direct price refs other than `close`
- indicator inputs with non-`close` sources

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
