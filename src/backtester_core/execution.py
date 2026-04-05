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
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("order quantity must be positive")


@dataclass(frozen=True)
class Fill:
    """Execution result for an order."""

    side: OrderSide
    quantity: int
    price: float
    timestamp: object


class ExecutionModel:
    """Executes queued market orders on the next bar open."""

    def execute(self, order: Order, bar: MarketBar) -> Fill:
        return Fill(
            side=order.side,
            quantity=order.quantity,
            price=bar.open,
            timestamp=bar.timestamp,
        )
