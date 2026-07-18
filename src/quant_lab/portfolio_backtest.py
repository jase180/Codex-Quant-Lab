"""Static-weight portfolio backtesting for multi-asset research."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from backtester_core.data import MarketBar
from backtester_core.execution import ExecutionModel, Order, TransactionCostModel
from quant_lab.portfolio_data import MultiAssetDataSet
from quant_lab.portfolio_spec import PortfolioSpec

FLOAT_TOLERANCE = 1e-9


@dataclass(frozen=True)
class PortfolioRebalanceOrder:
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float


@dataclass(frozen=True)
class PortfolioBacktestResult:
    equity_curve: pd.DataFrame
    positions: pd.DataFrame
    trades: pd.DataFrame
    allocation_drift: pd.DataFrame
    final_cash: float
    final_equity: float
    total_return: float


class StaticWeightPortfolioBacktester:
    """Backtest a static-weight portfolio on aligned daily OHLCV data.

    Rebalance decisions are made from close prices on bar ``t``. The resulting
    market orders are queued and filled at each symbol's open on bar ``t+1``.
    This mirrors the single-symbol engine's timing rule and avoids pretending
    that a close-based allocation decision could trade at the same close.
    """

    def __init__(
        self,
        *,
        initial_cash: float = 100_000.0,
        execution_model: ExecutionModel | None = None,
    ) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.initial_cash = float(initial_cash)
        self.execution_model = execution_model or ExecutionModel()

    def run(self, portfolio: PortfolioSpec, dataset: MultiAssetDataSet) -> PortfolioBacktestResult:
        _validate_dataset_matches_spec(portfolio, dataset)

        cash = self.initial_cash
        shares_by_symbol = {symbol.symbol: 0.0 for symbol in portfolio.symbols}
        target_weights = {symbol.symbol: symbol.target_weight for symbol in portfolio.symbols}
        pending_orders: list[PortfolioRebalanceOrder] = []
        equity_rows: list[dict] = []
        position_rows: list[dict] = []
        trade_rows: list[dict] = []
        drift_rows: list[dict] = []
        previous_timestamp: pd.Timestamp | None = None

        for timestamp in dataset.calendar:
            cash = _execute_orders(
                pending_orders,
                timestamp,
                dataset,
                shares_by_symbol,
                cash,
                trade_rows,
                self.execution_model,
            )
            pending_orders = []

            close_prices = _prices_at(dataset, timestamp, "close")
            holdings_value = _holdings_value(shares_by_symbol, close_prices)
            total_value = cash + holdings_value
            equity_rows.append(
                {
                    "timestamp": timestamp,
                    "cash": cash,
                    "holdings_value": holdings_value,
                    "total_value": total_value,
                }
            )
            _append_position_rows(
                position_rows,
                drift_rows,
                timestamp,
                shares_by_symbol,
                close_prices,
                total_value,
                target_weights,
            )

            if _should_rebalance(timestamp, previous_timestamp, portfolio.rebalance.frequency):
                pending_orders = _build_rebalance_orders(
                    shares_by_symbol,
                    close_prices,
                    total_value,
                    target_weights,
                )
            previous_timestamp = timestamp

        equity_curve = pd.DataFrame(equity_rows).set_index("timestamp")
        positions = pd.DataFrame(position_rows).set_index(["timestamp", "symbol"])
        allocation_drift = pd.DataFrame(drift_rows).set_index(["timestamp", "symbol"])
        trades = _trades_frame(trade_rows)
        final_equity = float(equity_curve.iloc[-1].total_value)

        return PortfolioBacktestResult(
            equity_curve=equity_curve,
            positions=positions,
            trades=trades,
            allocation_drift=allocation_drift,
            final_cash=float(cash),
            final_equity=final_equity,
            total_return=(final_equity - self.initial_cash) / self.initial_cash,
        )


def _validate_dataset_matches_spec(portfolio: PortfolioSpec, dataset: MultiAssetDataSet) -> None:
    spec_symbols = {symbol.symbol for symbol in portfolio.symbols}
    dataset_symbols = set(dataset.symbols.keys())
    missing = sorted(spec_symbols - dataset_symbols)
    if missing:
        raise ValueError(f"dataset is missing portfolio symbols: {missing}")
    if dataset.calendar.empty:
        raise ValueError("dataset calendar must not be empty")


def _execute_orders(
    orders: list[PortfolioRebalanceOrder],
    timestamp: pd.Timestamp,
    dataset: MultiAssetDataSet,
    shares_by_symbol: dict[str, float],
    cash: float,
    trade_rows: list[dict],
    execution_model: ExecutionModel,
) -> float:
    # Sells run first so rebalance cash is available before buys are attempted.
    for order in sorted(orders, key=lambda item: 0 if item.side == "sell" else 1):
        if order.quantity <= FLOAT_TOLERANCE:
            continue

        bar = _market_bar_at(dataset, order.symbol, timestamp)
        executable_order = Order(side=order.side, quantity=order.quantity)
        fill = execution_model.execute(executable_order, bar)
        if fill.side == "sell":
            quantity = min(fill.quantity, shares_by_symbol[order.symbol])
            proceeds = quantity * fill.price
            commission = execution_model.cost_model.commission_for(quantity, fill.price)
            cash += proceeds - commission
            shares_by_symbol[order.symbol] -= quantity
        else:
            quantity = _affordable_quantity(
                fill.quantity,
                fill.price,
                cash,
                execution_model.cost_model,
            )
            if quantity <= FLOAT_TOLERANCE:
                continue
            commission = execution_model.cost_model.commission_for(quantity, fill.price)
            cash -= (quantity * fill.price) + commission
            shares_by_symbol[order.symbol] += quantity

        trade_rows.append(
            {
                "timestamp": timestamp,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": quantity,
                "price": fill.price,
                "commission": commission,
                "cash_after": cash,
                "position_after": shares_by_symbol[order.symbol],
            }
        )

    return cash


def _affordable_quantity(
    requested_quantity: float,
    price: float,
    available_cash: float,
    cost_model: TransactionCostModel,
) -> float:
    fixed_commission = cost_model.commission_fixed
    if available_cash <= fixed_commission:
        return 0.0

    max_quantity = (available_cash - fixed_commission) / (
        price * (1 + cost_model.commission_rate)
    )
    return min(requested_quantity, max_quantity)


def _build_rebalance_orders(
    shares_by_symbol: dict[str, float],
    close_prices: dict[str, float],
    total_value: float,
    target_weights: dict[str, float],
) -> list[PortfolioRebalanceOrder]:
    orders: list[PortfolioRebalanceOrder] = []
    for symbol, target_weight in target_weights.items():
        current_value = shares_by_symbol[symbol] * close_prices[symbol]
        target_value = total_value * target_weight
        value_delta = target_value - current_value
        if abs(value_delta) <= FLOAT_TOLERANCE:
            continue

        side = "buy" if value_delta > 0 else "sell"
        quantity = abs(value_delta) / close_prices[symbol]
        orders.append(PortfolioRebalanceOrder(symbol=symbol, side=side, quantity=quantity))
    return orders


def _should_rebalance(
    timestamp: pd.Timestamp,
    previous_timestamp: pd.Timestamp | None,
    frequency: str,
) -> bool:
    if frequency == "none":
        return False
    # The first aligned bar is the first chance to make a portfolio decision,
    # even if that date is not the literal first calendar day of the period.
    if previous_timestamp is None:
        return True
    if frequency == "monthly":
        return timestamp.to_period("M") != previous_timestamp.to_period("M")
    if frequency == "quarterly":
        return timestamp.to_period("Q") != previous_timestamp.to_period("Q")
    if frequency == "annually":
        return timestamp.to_period("Y") != previous_timestamp.to_period("Y")
    raise ValueError(f"unsupported rebalance frequency: {frequency}")


def _append_position_rows(
    position_rows: list[dict],
    drift_rows: list[dict],
    timestamp: pd.Timestamp,
    shares_by_symbol: dict[str, float],
    close_prices: dict[str, float],
    total_value: float,
    target_weights: dict[str, float],
) -> None:
    for symbol, shares in shares_by_symbol.items():
        market_value = shares * close_prices[symbol]
        actual_weight = market_value / total_value if total_value else 0.0
        target_weight = target_weights[symbol]
        position_rows.append(
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "shares": shares,
                "close": close_prices[symbol],
                "market_value": market_value,
                "actual_weight": actual_weight,
                "target_weight": target_weight,
            }
        )
        drift_rows.append(
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "target_weight": target_weight,
                "actual_weight": actual_weight,
                "drift": actual_weight - target_weight,
            }
        )


def _prices_at(dataset: MultiAssetDataSet, timestamp: pd.Timestamp, field: str) -> dict[str, float]:
    return {
        symbol: float(data.loc[timestamp, field])
        for symbol, data in dataset.symbols.items()
    }


def _market_bar_at(dataset: MultiAssetDataSet, symbol: str, timestamp: pd.Timestamp) -> MarketBar:
    row = dataset.symbols[symbol].loc[timestamp]
    return MarketBar(
        timestamp=timestamp,
        open=float(row.open),
        high=float(row.high),
        low=float(row.low),
        close=float(row.close),
        volume=float(row.volume),
    )


def _holdings_value(shares_by_symbol: dict[str, float], prices: dict[str, float]) -> float:
    return sum(shares_by_symbol[symbol] * prices[symbol] for symbol in shares_by_symbol)


def _trades_frame(trade_rows: list[dict]) -> pd.DataFrame:
    columns = [
        "timestamp",
        "symbol",
        "side",
        "quantity",
        "price",
        "commission",
        "cash_after",
        "position_after",
    ]
    if not trade_rows:
        return pd.DataFrame(columns=columns).set_index("timestamp")
    return pd.DataFrame(trade_rows).set_index("timestamp")
