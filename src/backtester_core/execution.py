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
    commission: float = 0.0


@dataclass(frozen=True)
class TransactionCostModel:
    """Simple per-fill transaction cost assumptions.

    ``commission_fixed`` is a flat cash charge per fill. ``commission_rate`` is
    a fraction of trade notional, so 0.001 means 0.10%. ``slippage_bps`` uses
    basis points, where 1 bp is 0.01%.
    """

    commission_fixed: float = 0.0
    commission_rate: float = 0.0
    slippage_bps: float = 0.0

    def __post_init__(self) -> None:
        if self.commission_fixed < 0:
            raise ValueError("commission_fixed must not be negative")
        if self.commission_rate < 0:
            raise ValueError("commission_rate must not be negative")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must not be negative")
        if self.slippage_bps >= 10_000:
            raise ValueError("slippage_bps must be less than 10000")

    def execution_price(self, side: OrderSide, open_price: float) -> float:
        slippage_fraction = self.slippage_bps / 10_000
        if side == "buy":
            return open_price * (1 + slippage_fraction)
        if side == "sell":
            return open_price * (1 - slippage_fraction)
        raise ValueError(f"unsupported order side: {side}")

    def commission_for(self, quantity: float, price: float) -> float:
        return self.commission_fixed + (quantity * price * self.commission_rate)


class ExecutionModel:
    """Executes queued market orders on the next bar open."""

    def __init__(self, cost_model: TransactionCostModel | None = None) -> None:
        self.cost_model = cost_model or TransactionCostModel()

    def execute(self, order: Order, bar: MarketBar, available_cash: float | None = None) -> Fill:
        price = self.cost_model.execution_price(order.side, bar.open)
        if order.cash_allocation is not None:
            if available_cash is None:
                raise ValueError("available_cash is required for cash allocation orders")
            cash_budget = available_cash * order.cash_allocation
            fixed_commission = self.cost_model.commission_fixed
            if cash_budget <= fixed_commission:
                raise ValueError("available cash allocation does not cover fixed commission")
            # For allocation-style buys, solve quantity so price * quantity plus
            # commission fits inside the requested cash budget.
            quantity = (cash_budget - fixed_commission) / (price * (1 + self.cost_model.commission_rate))
        else:
            quantity = order.quantity

        if quantity is None:
            raise ValueError("order did not resolve to a quantity")
        commission = self.cost_model.commission_for(quantity, price)

        return Fill(
            side=order.side,
            quantity=quantity,
            price=price,
            timestamp=bar.timestamp,
            commission=commission,
        )
