"""Core backtest engine."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .data import iter_market_bars, validate_ohlcv_data
from .execution import ExecutionModel
from .portfolio import Portfolio
from .strategy import Strategy


@dataclass(frozen=True)
class BacktestResult:
    """Backtest outputs for analysis and testing."""

    portfolio_history: pd.DataFrame
    trades: pd.DataFrame
    final_cash: float
    final_position: int
    final_equity: float
    total_return: float


class BacktestEngine:
    """Runs a strategy over daily OHLCV data.

    Signals generated on bar ``t`` are queued and filled on bar ``t+1`` at the
    next bar open. Portfolio history is recorded once per bar at that bar's
    close, after any queued fills for the day have been applied.
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        execution_model: ExecutionModel | None = None,
    ) -> None:
        self.initial_cash = float(initial_cash)
        self.execution_model = execution_model or ExecutionModel()

    def run(self, data: pd.DataFrame, strategy: Strategy) -> BacktestResult:
        normalized_data = validate_ohlcv_data(data)
        portfolio = Portfolio(initial_cash=self.initial_cash)
        strategy.bind(portfolio)
        strategy.on_start()
        pending_orders = []

        for bar in iter_market_bars(normalized_data):
            for order in pending_orders:
                fill = self.execution_model.execute(order, bar)
                portfolio.apply_fill(fill)

            portfolio.mark_to_market(timestamp=bar.timestamp, market_price=bar.close)
            pending_orders = strategy.on_bar(bar) or []

        strategy.on_finish()

        final_equity = portfolio.equity
        total_return = (final_equity - portfolio.initial_cash) / portfolio.initial_cash
        return BacktestResult(
            portfolio_history=portfolio.history_frame(),
            trades=portfolio.trades_frame(),
            final_cash=portfolio.cash,
            final_position=portfolio.position,
            final_equity=final_equity,
            total_return=total_return,
        )
