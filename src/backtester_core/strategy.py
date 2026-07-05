"""Strategy base class."""

from __future__ import annotations

from .data import MarketBar
from .execution import Order
from .portfolio import Portfolio


class Strategy:
    """Base strategy with helper methods for buy/sell signals."""

    def __init__(self) -> None:
        self.portfolio: Portfolio | None = None

    def bind(self, portfolio: Portfolio) -> None:
        self.portfolio = portfolio

    def on_start(self) -> None:
        """Hook called before bar iteration begins."""

    def on_bar(self, bar: MarketBar) -> list[Order]:
        """Return zero or more orders to be filled on the next bar open."""
        raise NotImplementedError

    def on_finish(self) -> None:
        """Hook called after the last bar is processed."""

    def buy(self, quantity: float) -> Order:
        return Order(side="buy", quantity=quantity)

    def buy_with_cash_allocation(self, allocation: float) -> Order:
        return Order(side="buy", cash_allocation=allocation)

    def sell(self, quantity: float) -> Order:
        return Order(side="sell", quantity=quantity)
