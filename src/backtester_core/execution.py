"""Order execution primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .data import MarketBar

OrderSide = Literal["buy", "sell"]


@dataclass(frozen=True)
class Order:
    """Simple market order intended for the next execution opportunity."""

    side: OrderSide
    quantity: float | None = None
    cash_allocation: float | None = None

    def __post_init__(self) -> None:
        has_quantity = self.quantity is not None
        has_cash_allocation = self.cash_allocation is not None
        if has_quantity == has_cash_allocation:
            raise ValueError("order must specify exactly one of quantity or cash_allocation")
        if self.quantity is not None and self.quantity <= 0:
            raise ValueError("order quantity must be positive")
        if self.cash_allocation is not None and not 0 < self.cash_allocation <= 1:
            raise ValueError("order cash_allocation must be greater than 0 and at most 1")
        if self.cash_allocation is not None and self.side != "buy":
            raise ValueError("cash_allocation orders are only supported for buys")


@dataclass(frozen=True)
class Fill:
    """Execution result for an order."""

    side: OrderSide
    quantity: float
    price: float
    timestamp: object


class ExecutionModel:
    """Executes queued market orders on the next bar open."""

    def execute(self, order: Order, bar: MarketBar, available_cash: float | None = None) -> Fill:
        if order.cash_allocation is not None:
            if available_cash is None:
                raise ValueError("available_cash is required for cash allocation orders")
            quantity = (available_cash * order.cash_allocation) / bar.open
        else:
            quantity = order.quantity

        if quantity is None:
            raise ValueError("order did not resolve to a quantity")

        return Fill(
            side=order.side,
            quantity=quantity,
            price=bar.open,
            timestamp=bar.timestamp,
        )
