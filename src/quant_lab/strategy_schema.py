"""Strict v1 schema for simple rule-based daily trading strategies."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_ALLOWED_INDICATORS = {"sma", "ema", "rsi"}
_ALLOWED_SIGNAL_PRICE_FIELDS = {"close"}
_ALLOWED_OPERATORS = {
    "gt",
    "gte",
    "lt",
    "lte",
    "eq",
    "crosses_above",
    "crosses_below",
}
_ALLOWED_POSITION_MODES = {"long_only"}


class StrategySchemaError(ValueError):
    """Raised when a strategy document violates the v1 schema."""


@dataclass(frozen=True)
class MarketSpec:
    symbol: str
    timeframe: str


@dataclass(frozen=True)
class IndicatorSpec:
    id: str
    kind: Literal["sma", "ema", "rsi"]
    inputs: dict[str, Any]


@dataclass(frozen=True)
class ValueRef:
    kind: Literal["price", "indicator", "constant"]
    value: str | float | int


@dataclass(frozen=True)
class Condition:
    left: ValueRef
    operator: Literal["gt", "gte", "lt", "lte", "eq", "crosses_above", "crosses_below"]
    right: ValueRef


@dataclass(frozen=True)
class ConditionSet:
    when: Literal["all", "any"]
    conditions: list[Condition]


@dataclass(frozen=True)
class StrategySpec:
    schema_version: Literal["v1"]
    strategy_id: str
    name: str
    description: str
    strategy_type: Literal["rule_based"]
    position_mode: Literal["long_only"]
    market: MarketSpec
    indicators: list[IndicatorSpec]
    entry: ConditionSet
    exit: ConditionSet


def load_strategy(path: str | Path) -> StrategySpec:
    """Load a strategy from a JSON file and validate it."""

    strategy_path = Path(path)
    if strategy_path.suffix.lower() != ".json":
        raise StrategySchemaError(
            f"Unsupported strategy file format '{strategy_path.suffix}'. v1 loader accepts JSON files."
        )

    try:
        payload = json.loads(strategy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StrategySchemaError(f"Strategy file does not exist: {strategy_path}") from exc
    except json.JSONDecodeError as exc:
        raise StrategySchemaError(
            f"Invalid JSON in strategy file '{strategy_path}': {exc.msg}"
        ) from exc

    return parse_strategy(payload)


def parse_strategy(payload: dict[str, Any]) -> StrategySpec:
    """Validate an in-memory strategy document and convert it into Python objects."""

    if not isinstance(payload, dict):
        raise StrategySchemaError("Strategy document must be a JSON object.")

    schema_version = _require_literal(payload, "schema_version", {"v1"})
    strategy_id = _require_identifier(payload, "strategy_id")
    name = _require_non_empty_string(payload, "name")
    description = _require_non_empty_string(payload, "description")
    strategy_type = _require_literal(payload, "strategy_type", {"rule_based"})
    position_mode = _require_literal(payload, "position_mode", _ALLOWED_POSITION_MODES)
    market = _parse_market(_require_mapping(payload, "market"))
    indicators = _parse_indicators(_require_list(payload, "indicators"))
    indicator_ids = {indicator.id for indicator in indicators}
    entry = _parse_condition_set(_require_mapping(payload, "entry"), indicator_ids, "entry")
    exit_rules = _parse_condition_set(_require_mapping(payload, "exit"), indicator_ids, "exit")

    _reject_unknown_keys(
        payload,
        allowed={
            "schema_version",
            "strategy_id",
            "name",
            "description",
            "strategy_type",
            "position_mode",
            "market",
            "indicators",
            "entry",
            "exit",
        },
        context="strategy",
    )

    return StrategySpec(
        schema_version=schema_version,
        strategy_id=strategy_id,
        name=name,
        description=description,
        strategy_type=strategy_type,
        position_mode=position_mode,
        market=market,
        indicators=indicators,
        entry=entry,
        exit=exit_rules,
    )


def _parse_market(payload: dict[str, Any]) -> MarketSpec:
    symbol = _require_non_empty_string(payload, "symbol")
    timeframe = _require_literal(payload, "timeframe", {"1d"}, "market")

    _reject_unknown_keys(payload, {"symbol", "timeframe"}, "market")
    return MarketSpec(symbol=symbol, timeframe=timeframe)


def _parse_indicators(payload: list[Any]) -> list[IndicatorSpec]:
    if not payload:
        raise StrategySchemaError("indicators must contain at least one indicator.")

    indicators: list[IndicatorSpec] = []
    seen_ids: set[str] = set()

    for index, raw_indicator in enumerate(payload):
        if not isinstance(raw_indicator, dict):
            raise StrategySchemaError(f"indicators[{index}] must be an object.")

        indicator_id = _require_identifier(raw_indicator, "id", context=f"indicators[{index}]")
        if indicator_id in seen_ids:
            raise StrategySchemaError(f"Duplicate indicator id '{indicator_id}'.")
        seen_ids.add(indicator_id)

        kind = _require_literal(raw_indicator, "kind", _ALLOWED_INDICATORS, f"indicators[{index}]")
        inputs = _require_mapping(raw_indicator, "inputs", f"indicators[{index}]")
        _validate_indicator_inputs(kind, inputs, index)
        _reject_unknown_keys(raw_indicator, {"id", "kind", "inputs"}, f"indicators[{index}]")
        indicators.append(IndicatorSpec(id=indicator_id, kind=kind, inputs=inputs))

    return indicators


def _validate_indicator_inputs(kind: str, inputs: dict[str, Any], index: int) -> None:
    required_keys = {"source", "length"}
    if set(inputs.keys()) != required_keys:
        raise StrategySchemaError(
            f"indicators[{index}].inputs must contain exactly {sorted(required_keys)}."
        )

    source = inputs.get("source")
    if source not in _ALLOWED_SIGNAL_PRICE_FIELDS:
        raise StrategySchemaError(
            f"indicators[{index}].inputs.source must be 'close' in v1 so signals are fully close-based."
        )

    length = inputs.get("length")
    if not isinstance(length, int) or length <= 0:
        raise StrategySchemaError(f"indicators[{index}].inputs.length must be a positive integer.")

    if kind == "rsi" and length < 2:
        raise StrategySchemaError("RSI length must be at least 2.")


def _parse_condition_set(
    payload: dict[str, Any], indicator_ids: set[str], context: str
) -> ConditionSet:
    when = _require_literal(payload, "when", {"all", "any"}, context)
    raw_conditions = _require_list(payload, "conditions", context)
    if not raw_conditions:
        raise StrategySchemaError(f"{context}.conditions must contain at least one condition.")

    conditions = [
        _parse_condition(condition, indicator_ids, f"{context}.conditions[{index}]")
        for index, condition in enumerate(raw_conditions)
    ]
    _reject_unknown_keys(payload, {"when", "conditions"}, context)
    return ConditionSet(when=when, conditions=conditions)


def _parse_condition(payload: Any, indicator_ids: set[str], context: str) -> Condition:
    if not isinstance(payload, dict):
        raise StrategySchemaError(f"{context} must be an object.")

    left = _parse_value_ref(_require_mapping(payload, "left", context), indicator_ids, f"{context}.left")
    operator = _require_literal(payload, "operator", _ALLOWED_OPERATORS, context)
    right = _parse_value_ref(
        _require_mapping(payload, "right", context), indicator_ids, f"{context}.right"
    )
    _reject_unknown_keys(payload, {"left", "operator", "right"}, context)
    return Condition(left=left, operator=operator, right=right)


def _parse_value_ref(payload: dict[str, Any], indicator_ids: set[str], context: str) -> ValueRef:
    keys = set(payload.keys())
    if keys == {"price"}:
        price_field = payload["price"]
        if price_field not in _ALLOWED_SIGNAL_PRICE_FIELDS:
            raise StrategySchemaError(
                f"{context}.price must be 'close' in v1 because signals are evaluated on the daily close."
            )
        return ValueRef(kind="price", value=price_field)

    if keys == {"indicator"}:
        indicator_id = payload["indicator"]
        if not isinstance(indicator_id, str) or indicator_id not in indicator_ids:
            raise StrategySchemaError(f"{context}.indicator must reference a declared indicator id.")
        return ValueRef(kind="indicator", value=indicator_id)

    if keys == {"value"}:
        value = payload["value"]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise StrategySchemaError(f"{context}.value must be numeric.")
        return ValueRef(kind="constant", value=value)

    raise StrategySchemaError(
        f"{context} must contain exactly one of 'price', 'indicator', or 'value'."
    )


def _require_mapping(payload: dict[str, Any], key: str, context: str = "strategy") -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise StrategySchemaError(f"{context}.{key} must be an object.")
    return value


def _require_list(payload: dict[str, Any], key: str, context: str = "strategy") -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise StrategySchemaError(f"{context}.{key} must be a list.")
    return value


def _require_non_empty_string(payload: dict[str, Any], key: str, context: str = "strategy") -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StrategySchemaError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_identifier(payload: dict[str, Any], key: str, context: str = "strategy") -> str:
    value = _require_non_empty_string(payload, key, context)
    if not _ID_PATTERN.match(value):
        raise StrategySchemaError(
            f"{context}.{key} must match pattern '{_ID_PATTERN.pattern}'."
        )
    return value


def _require_literal(
    payload: dict[str, Any], key: str, allowed: set[str], context: str = "strategy"
) -> str:
    value = payload.get(key)
    if value not in allowed:
        raise StrategySchemaError(f"{context}.{key} must be one of {sorted(allowed)}.")
    return value


def _reject_unknown_keys(payload: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(payload.keys()) - allowed)
    if unknown:
        raise StrategySchemaError(f"{context} contains unsupported fields: {unknown}.")
