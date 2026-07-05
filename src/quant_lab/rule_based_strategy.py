"""Executable strategy adapter for v1 rule-based strategy specs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from backtester_core.data import MarketBar
from backtester_core.strategy import Strategy

from .strategy_schema import Condition, ConditionSet, StrategySpec, ValueRef


Number = float | int
SizingMode = Literal["fixed-shares", "percent-equity"]


@dataclass(frozen=True)
class EvaluationContext:
    close: float
    previous_close: float | None
    indicators: dict[str, float | None]
    previous_indicators: dict[str, float | None]


class IndicatorState:
    """Incremental close-based indicator calculator."""

    def __init__(self, kind: str, length: int) -> None:
        self.kind = kind
        self.length = int(length)
        self.closes: list[float] = []
        self.current_value: float | None = None
        self.previous_value: float | None = None
        self._ema_value: float | None = None
        self._previous_close: float | None = None
        self._rsi_avg_gain: float | None = None
        self._rsi_avg_loss: float | None = None
        self._rsi_changes: list[float] = []

    def update(self, close: float) -> float | None:
        self.previous_value = self.current_value
        self.closes.append(float(close))

        if self.kind == "sma":
            self.current_value = self._update_sma()
        elif self.kind == "ema":
            self.current_value = self._update_ema(float(close))
        elif self.kind == "rsi":
            self.current_value = self._update_rsi(float(close))
        else:
            raise ValueError(f"unsupported indicator kind: {self.kind}")

        return self.current_value

    def _update_sma(self) -> float | None:
        if len(self.closes) < self.length:
            return None
        window = self.closes[-self.length :]
        return sum(window) / self.length

    def _update_ema(self, close: float) -> float | None:
        alpha = 2 / (self.length + 1)
        if self._ema_value is None:
            self._ema_value = close
        else:
            self._ema_value = (close * alpha) + (self._ema_value * (1 - alpha))
        return self._ema_value

    def _update_rsi(self, close: float) -> float | None:
        if self._previous_close is None:
            self._previous_close = close
            return None

        change = close - self._previous_close
        self._previous_close = close

        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        if self._rsi_avg_gain is None or self._rsi_avg_loss is None:
            self._rsi_changes.append(change)
            if len(self._rsi_changes) < self.length:
                return None
            gains = [max(raw_change, 0.0) for raw_change in self._rsi_changes]
            losses = [max(-raw_change, 0.0) for raw_change in self._rsi_changes]
            self._rsi_avg_gain = sum(gains) / self.length
            self._rsi_avg_loss = sum(losses) / self.length
        else:
            self._rsi_avg_gain = ((self._rsi_avg_gain * (self.length - 1)) + gain) / self.length
            self._rsi_avg_loss = ((self._rsi_avg_loss * (self.length - 1)) + loss) / self.length

        if self._rsi_avg_loss == 0:
            if self._rsi_avg_gain == 0:
                return 50.0
            return 100.0

        relative_strength = self._rsi_avg_gain / self._rsi_avg_loss
        return 100 - (100 / (1 + relative_strength))


class RuleBasedStrategy(Strategy):
    """Runs a validated v1 rule-based strategy spec against daily bars."""

    def __init__(
        self,
        spec: StrategySpec,
        order_quantity: float = 1,
        sizing: SizingMode = "fixed-shares",
        allocation: float = 1.0,
    ) -> None:
        super().__init__()
        if spec.strategy_type != "rule_based":
            raise ValueError("RuleBasedStrategy only supports rule_based specs.")
        if spec.position_mode != "long_only":
            raise ValueError("RuleBasedStrategy only supports long_only specs.")
        if order_quantity <= 0:
            raise ValueError("order_quantity must be positive.")
        if sizing not in {"fixed-shares", "percent-equity"}:
            raise ValueError("sizing must be 'fixed-shares' or 'percent-equity'.")
        if not 0 < allocation <= 1:
            raise ValueError("allocation must be greater than 0 and at most 1.")

        self.spec = spec
        self.order_quantity = float(order_quantity)
        self.sizing = sizing
        self.allocation = float(allocation)
        self._indicator_states = {
            indicator.id: IndicatorState(
                kind=indicator.kind,
                length=int(indicator.inputs["length"]),
            )
            for indicator in spec.indicators
        }
        self._previous_close: float | None = None

    def on_bar(self, bar: MarketBar):
        indicators = {
            indicator_id: state.update(bar.close)
            for indicator_id, state in self._indicator_states.items()
        }
        previous_indicators = {
            indicator_id: state.previous_value
            for indicator_id, state in self._indicator_states.items()
        }
        context = EvaluationContext(
            close=float(bar.close),
            previous_close=self._previous_close,
            indicators=indicators,
            previous_indicators=previous_indicators,
        )
        self._previous_close = float(bar.close)

        if self.portfolio is None:
            raise RuntimeError("Strategy must be bound to a portfolio before use.")

        if self.portfolio.position > 0 and evaluate_condition_set(self.spec.exit, context):
            return [self.sell(quantity=self.portfolio.position)]

        if self.portfolio.position == 0 and evaluate_condition_set(self.spec.entry, context):
            if self.sizing == "percent-equity":
                return [self.buy_with_cash_allocation(self.allocation)]
            return [self.buy(quantity=self.order_quantity)]

        return []


def evaluate_condition_set(condition_set: ConditionSet, context: EvaluationContext) -> bool:
    results = [evaluate_condition(condition, context) for condition in condition_set.conditions]
    if condition_set.when == "all":
        return all(results)
    if condition_set.when == "any":
        return any(results)
    raise ValueError(f"unsupported condition set mode: {condition_set.when}")


def evaluate_condition(condition: Condition, context: EvaluationContext) -> bool:
    left = _resolve_current(condition.left, context)
    right = _resolve_current(condition.right, context)
    if left is None or right is None:
        return False

    if condition.operator == "gt":
        return left > right
    if condition.operator == "gte":
        return left >= right
    if condition.operator == "lt":
        return left < right
    if condition.operator == "lte":
        return left <= right
    if condition.operator == "eq":
        return left == right
    if condition.operator == "crosses_above":
        return _crosses_above(condition.left, condition.right, left, right, context)
    if condition.operator == "crosses_below":
        return _crosses_below(condition.left, condition.right, left, right, context)

    raise ValueError(f"unsupported condition operator: {condition.operator}")


def _crosses_above(
    left_ref: ValueRef,
    right_ref: ValueRef,
    left: float,
    right: float,
    context: EvaluationContext,
) -> bool:
    previous_left = _resolve_previous(left_ref, context)
    previous_right = _resolve_previous(right_ref, context)
    if previous_left is None or previous_right is None:
        return False
    return previous_left <= previous_right and left > right


def _crosses_below(
    left_ref: ValueRef,
    right_ref: ValueRef,
    left: float,
    right: float,
    context: EvaluationContext,
) -> bool:
    previous_left = _resolve_previous(left_ref, context)
    previous_right = _resolve_previous(right_ref, context)
    if previous_left is None or previous_right is None:
        return False
    return previous_left >= previous_right and left < right


def _resolve_current(ref: ValueRef, context: EvaluationContext) -> float | None:
    return _resolve(ref, context.close, context.indicators)


def _resolve_previous(ref: ValueRef, context: EvaluationContext) -> float | None:
    return _resolve(ref, context.previous_close, context.previous_indicators)


def _resolve(
    ref: ValueRef,
    price_close: float | None,
    indicators: dict[str, float | None],
) -> float | None:
    if ref.kind == "price":
        return price_close
    if ref.kind == "indicator":
        return indicators[str(ref.value)]
    if ref.kind == "constant":
        return float(ref.value)
    raise ValueError(f"unsupported value reference kind: {ref.kind}")


def build_rule_based_strategy(
    spec: StrategySpec,
    order_quantity: float = 1,
    sizing: SizingMode = "fixed-shares",
    allocation: float = 1.0,
) -> RuleBasedStrategy:
    return RuleBasedStrategy(
        spec=spec,
        order_quantity=order_quantity,
        sizing=sizing,
        allocation=allocation,
    )


def indicator_values(kind: str, length: int, closes: Iterable[Number]) -> list[float | None]:
    state = IndicatorState(kind=kind, length=length)
    return [state.update(float(close)) for close in closes]
