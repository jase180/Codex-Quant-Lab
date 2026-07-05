import unittest

import pandas as pd

from backtester_core.engine import BacktestEngine
from backtester_core.data import iter_market_bars, validate_ohlcv_data
from backtester_core.execution import ExecutionModel, Fill, Order, TransactionCostModel
from backtester_core.portfolio import Portfolio
from backtester_core.strategy import Strategy


class BuyAndHoldStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__()
        self.has_bought = False

    def on_bar(self, bar):
        if not self.has_bought:
            self.has_bought = True
            return [self.buy(quantity=10)]
        return []


class NextDayRoundTripStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__()
        self.step = 0

    def on_bar(self, bar):
        self.step += 1
        if self.step == 1:
            return [self.buy(quantity=5)]
        if self.step == 2:
            return [self.sell(quantity=5)]
        return []


class LastBarBuyStrategy(Strategy):
    def on_bar(self, bar):
        if str(bar.timestamp.date()) == "2026-04-01":
            return [self.buy(quantity=1)]
        return []


class BacktesterCoreTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame(
            [
                {"date": "2026-03-30", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
                {"date": "2026-03-31", "open": 110, "high": 112, "low": 109, "close": 111, "volume": 1200},
                {"date": "2026-04-01", "open": 90, "high": 96, "low": 89, "close": 95, "volume": 1100},
            ]
        )

    def test_validate_ohlcv_uses_date_column(self):
        normalized = validate_ohlcv_data(self.data)
        self.assertIsInstance(normalized.index, pd.DatetimeIndex)
        self.assertListEqual(list(normalized.columns), ["open", "high", "low", "close", "volume"])

    def test_validate_ohlcv_requires_columns(self):
        with self.assertRaises(ValueError):
            validate_ohlcv_data(self.data.drop(columns=["volume"]))

    def test_portfolio_updates_for_buy_and_sell(self):
        portfolio = Portfolio(initial_cash=1_000)
        portfolio.apply_fill(Fill(side="buy", quantity=5, price=100.0, timestamp=pd.Timestamp("2026-03-30")))
        snapshot = portfolio.mark_to_market(pd.Timestamp("2026-03-30"), market_price=100.0)
        self.assertEqual(portfolio.cash, 500.0)
        self.assertEqual(portfolio.position, 5)
        self.assertEqual(snapshot.total_value, 1_000.0)

        portfolio.apply_fill(Fill(side="sell", quantity=2, price=110.0, timestamp=pd.Timestamp("2026-03-31")))
        self.assertEqual(portfolio.cash, 720.0)
        self.assertEqual(portfolio.position, 3)

    def test_portfolio_applies_commissions_to_cash(self):
        portfolio = Portfolio(initial_cash=1_000)
        portfolio.apply_fill(
            Fill(
                side="buy",
                quantity=5,
                price=100.0,
                commission=2.0,
                timestamp=pd.Timestamp("2026-03-30"),
            )
        )
        self.assertEqual(portfolio.cash, 498.0)
        self.assertEqual(portfolio.position, 5)

        trade = portfolio.apply_fill(
            Fill(
                side="sell",
                quantity=2,
                price=110.0,
                commission=1.0,
                timestamp=pd.Timestamp("2026-03-31"),
            )
        )

        self.assertEqual(portfolio.cash, 717.0)
        self.assertEqual(portfolio.position, 3)
        self.assertEqual(trade.commission, 1.0)

    def test_engine_does_not_fill_on_signal_bar(self):
        engine = BacktestEngine(initial_cash=5_000)
        result = engine.run(self.data, BuyAndHoldStrategy())

        first_day = result.portfolio_history.loc[pd.Timestamp("2026-03-30")]
        self.assertEqual(first_day["cash"], 5_000.0)
        self.assertEqual(first_day["position"], 0.0)
        self.assertEqual(len(result.trades), 1)

    def test_engine_fills_next_bar_open_with_fill_timestamp(self):
        engine = BacktestEngine(initial_cash=5_000)
        result = engine.run(self.data, BuyAndHoldStrategy())

        self.assertEqual(result.trades.index[0], pd.Timestamp("2026-03-31"))
        self.assertEqual(result.trades.iloc[0]["price"], 110.0)
        self.assertEqual(result.final_cash, 3_900.0)
        self.assertEqual(result.final_position, 10)
        self.assertEqual(result.final_equity, 4_850.0)
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(len(result.portfolio_history), 3)

    def test_engine_uses_next_open_for_gap_up_and_gap_down(self):
        engine = BacktestEngine(initial_cash=5_000)
        result = engine.run(self.data, NextDayRoundTripStrategy())

        self.assertEqual(list(result.trades.index), [pd.Timestamp("2026-03-31"), pd.Timestamp("2026-04-01")])
        self.assertEqual(list(result.trades["price"]), [110.0, 90.0])
        self.assertEqual(result.final_cash, 4_900.0)
        self.assertEqual(result.final_position, 0)
        self.assertEqual(result.final_equity, 4_900.0)
        self.assertAlmostEqual(result.total_return, -0.02)
        self.assertEqual(list(result.trades["side"]), ["buy", "sell"])

    def test_execution_model_resolves_cash_allocation_at_next_open(self):
        order = Order(side="buy", cash_allocation=0.5)
        bar = iter_market_bars(validate_ohlcv_data(self.data))[0]

        fill = ExecutionModel().execute(order, bar, available_cash=1_000)

        self.assertEqual(fill.side, "buy")
        self.assertEqual(fill.price, 100.0)
        self.assertAlmostEqual(fill.quantity, 5.0)

    def test_execution_model_applies_slippage_and_commission(self):
        order = Order(side="buy", quantity=10)
        bar = iter_market_bars(validate_ohlcv_data(self.data))[0]
        model = ExecutionModel(
            TransactionCostModel(
                commission_fixed=1.0,
                commission_rate=0.01,
                slippage_bps=50,
            )
        )

        fill = model.execute(order, bar)

        self.assertEqual(fill.side, "buy")
        self.assertAlmostEqual(fill.price, 100.5)
        self.assertAlmostEqual(fill.commission, 11.05)

    def test_cash_allocation_accounts_for_costs(self):
        order = Order(side="buy", cash_allocation=1.0)
        bar = iter_market_bars(validate_ohlcv_data(self.data))[0]
        model = ExecutionModel(
            TransactionCostModel(
                commission_fixed=2.0,
                commission_rate=0.01,
                slippage_bps=100,
            )
        )

        fill = model.execute(order, bar, available_cash=1_000)
        total_cash_required = (fill.quantity * fill.price) + fill.commission

        self.assertAlmostEqual(fill.price, 101.0)
        self.assertAlmostEqual(total_cash_required, 1_000.0)

    def test_equity_history_reconciles_cash_position_and_close(self):
        engine = BacktestEngine(initial_cash=5_000)
        result = engine.run(self.data, BuyAndHoldStrategy())

        second_day = result.portfolio_history.loc[pd.Timestamp("2026-03-31")]
        third_day = result.portfolio_history.loc[pd.Timestamp("2026-04-01")]

        self.assertEqual(second_day["cash"], 3_900.0)
        self.assertEqual(second_day["position"], 10.0)
        self.assertEqual(second_day["holdings_value"], 1_110.0)
        self.assertEqual(second_day["total_value"], 5_010.0)

        self.assertEqual(third_day["cash"], 3_900.0)
        self.assertEqual(third_day["position"], 10.0)
        self.assertEqual(third_day["holdings_value"], 950.0)
        self.assertEqual(third_day["total_value"], 4_850.0)

    def test_final_bar_signal_does_not_fill(self):
        engine = BacktestEngine(initial_cash=1_000)
        result = engine.run(self.data, LastBarBuyStrategy())

        self.assertTrue(result.trades.empty)
        self.assertEqual(result.final_cash, 1_000.0)
        self.assertEqual(result.final_position, 0)
        self.assertEqual(result.final_equity, 1_000.0)

    def test_engine_rejects_sell_without_position(self):
        class InvalidStrategy(Strategy):
            def on_bar(self, bar):
                if str(bar.timestamp.date()) == "2026-03-31":
                    return [self.sell(quantity=1)]
                return []

        engine = BacktestEngine(initial_cash=1_000)
        with self.assertRaises(ValueError):
            engine.run(self.data, InvalidStrategy())


if __name__ == "__main__":
    unittest.main()
