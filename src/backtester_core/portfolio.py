"""Portfolio accounting models."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .execution import Fill


@dataclass(frozen=True)
class Trade:
    """Executed trade ledger entry recorded at the fill timestamp."""

    timestamp: pd.Timestamp
    side: str
    quantity: int
    price: float
    cash_after: float
    position_after: int


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Point-in-time portfolio state."""

    timestamp: pd.Timestamp
    cash: float
    position: int
    market_price: float
    holdings_value: float
    total_value: float


class Portfolio:
    """Tracks cash, position, trades, and end-of-day portfolio history."""

    def __init__(self, initial_cash: float) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")

        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.position = 0
        self.trades: list[Trade] = []
        self.history: list[PortfolioSnapshot] = []

    def apply_fill(self, fill: Fill) -> Trade:
        if fill.side == "buy":
            cost = fill.quantity * fill.price
            if cost > self.cash:
                raise ValueError("insufficient cash for buy order")
            self.cash -= cost
            self.position += fill.quantity
        elif fill.side == "sell":
            if fill.quantity > self.position:
                raise ValueError("insufficient position for sell order")
            proceeds = fill.quantity * fill.price
            self.cash += proceeds
            self.position -= fill.quantity
        else:
            raise ValueError(f"unsupported fill side: {fill.side}")

        trade = Trade(
            timestamp=pd.Timestamp(fill.timestamp),
            side=fill.side,
            quantity=fill.quantity,
            price=float(fill.price),
            cash_after=self.cash,
            position_after=self.position,
        )
        self.trades.append(trade)
        return trade

    def mark_to_market(self, timestamp: pd.Timestamp, market_price: float) -> PortfolioSnapshot:
        holdings_value = self.position * market_price
        snapshot = PortfolioSnapshot(
            timestamp=pd.Timestamp(timestamp),
            cash=self.cash,
            position=self.position,
            market_price=float(market_price),
            holdings_value=holdings_value,
            total_value=self.cash + holdings_value,
        )
        self.history.append(snapshot)
        return snapshot

    @property
    def equity(self) -> float:
        if self.history:
            return self.history[-1].total_value
        return self.cash

    def history_frame(self) -> pd.DataFrame:
        if not self.history:
            return pd.DataFrame(
                columns=["timestamp", "cash", "position", "market_price", "holdings_value", "total_value"]
            ).set_index("timestamp")

        return pd.DataFrame(
            [
                {
                    "timestamp": snapshot.timestamp,
                    "cash": snapshot.cash,
                    "position": snapshot.position,
                    "market_price": snapshot.market_price,
                    "holdings_value": snapshot.holdings_value,
                    "total_value": snapshot.total_value,
                }
                for snapshot in self.history
            ]
        ).set_index("timestamp")

    def trades_frame(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame(
                columns=["timestamp", "side", "quantity", "price", "cash_after", "position_after"]
            ).set_index("timestamp")

        return pd.DataFrame(
            [
                {
                    "timestamp": trade.timestamp,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "price": trade.price,
                    "cash_after": trade.cash_after,
                    "position_after": trade.position_after,
                }
                for trade in self.trades
            ]
        ).set_index("timestamp")
