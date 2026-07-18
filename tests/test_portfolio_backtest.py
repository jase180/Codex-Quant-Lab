from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backtester_core.execution import ExecutionModel, TransactionCostModel  # noqa: E402
from quant_lab.portfolio_backtest import StaticWeightPortfolioBacktester  # noqa: E402
from quant_lab.portfolio_data import MultiAssetDataSet  # noqa: E402
from quant_lab.portfolio_spec import parse_portfolio_spec  # noqa: E402


def portfolio_spec(frequency: str = "monthly"):
    return parse_portfolio_spec(
        {
            "schema_version": "portfolio_plan.v1",
            "portfolio_id": "qqq_spy_static_60_40",
            "name": "QQQ SPY Static 60/40",
            "description": "Static two-symbol allocation.",
            "symbols": [
                {"symbol": "QQQ", "data": "QQQ.csv", "target_weight": 0.60},
                {"symbol": "SPY", "data": "SPY.csv", "target_weight": 0.40},
            ],
            "rebalance": {"frequency": frequency},
            "benchmark": {"symbol": "SPY", "data": "SPY.csv"},
        }
    )


def market_data(closes: list[float]) -> pd.DataFrame:
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    return pd.DataFrame(
        {
            "open": closes,
            "high": [close + 1 for close in closes],
            "low": [close - 1 for close in closes],
            "close": closes,
            "volume": [1000, 1000, 1000],
        },
        index=dates,
    )


def dataset() -> MultiAssetDataSet:
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    return MultiAssetDataSet(
        symbols={
            "QQQ": market_data([100, 110, 120]),
            "SPY": market_data([200, 200, 200]),
        },
        calendar=pd.DatetimeIndex(dates),
        alignment_policy="intersection",
        data_quality={},
        fingerprints={},
        dropped_rows_by_symbol={"QQQ": 0, "SPY": 0},
    )


def dataset_starting_after_month_start() -> MultiAssetDataSet:
    dates = pd.to_datetime(["2026-01-02", "2026-01-05"])
    return MultiAssetDataSet(
        symbols={
            "QQQ": market_data([100, 110, 120]).loc[dates],
            "SPY": market_data([200, 200, 200]).loc[dates],
        },
        calendar=pd.DatetimeIndex(dates),
        alignment_policy="intersection",
        data_quality={},
        fingerprints={},
        dropped_rows_by_symbol={"QQQ": 0, "SPY": 0},
    )


class PortfolioBacktestTests(unittest.TestCase):
    def test_static_weight_portfolio_fills_rebalance_at_next_open(self) -> None:
        result = StaticWeightPortfolioBacktester(initial_cash=1000).run(portfolio_spec(), dataset())

        self.assertEqual(len(result.equity_curve), 3)
        self.assertEqual(result.equity_curve.iloc[0].total_value, 1000)
        self.assertEqual(result.trades.index[0].date().isoformat(), "2026-01-02")
        self.assertEqual(set(result.trades["symbol"]), {"QQQ", "SPY"})
        self.assertAlmostEqual(result.positions.loc[(pd.Timestamp("2026-01-02"), "QQQ")].shares, 6.0)
        self.assertAlmostEqual(result.positions.loc[(pd.Timestamp("2026-01-02"), "SPY")].shares, 1.7)
        self.assertAlmostEqual(result.final_equity, 1060.0)
        self.assertAlmostEqual(result.total_return, 0.06)

    def test_frequency_none_does_not_enter_positions(self) -> None:
        result = StaticWeightPortfolioBacktester(initial_cash=1000).run(
            portfolio_spec(frequency="none"),
            dataset(),
        )

        self.assertTrue(result.trades.empty)
        self.assertEqual(result.final_cash, 1000)
        self.assertEqual(result.final_equity, 1000)

    def test_first_available_session_can_trigger_initial_rebalance(self) -> None:
        result = StaticWeightPortfolioBacktester(initial_cash=1000).run(
            portfolio_spec(),
            dataset_starting_after_month_start(),
        )

        self.assertEqual(result.trades.index[0].date().isoformat(), "2026-01-05")
        self.assertFalse(result.trades.empty)

    def test_final_bar_rebalance_signal_does_not_fill(self) -> None:
        data = dataset()
        data = MultiAssetDataSet(
            symbols={
                "QQQ": data.symbols["QQQ"].loc[[pd.Timestamp("2026-01-05")]],
                "SPY": data.symbols["SPY"].loc[[pd.Timestamp("2026-01-05")]],
            },
            calendar=pd.DatetimeIndex([pd.Timestamp("2026-01-05")]),
            alignment_policy="intersection",
            data_quality={},
            fingerprints={},
            dropped_rows_by_symbol={"QQQ": 0, "SPY": 0},
        )

        result = StaticWeightPortfolioBacktester(initial_cash=1000).run(portfolio_spec(), data)

        self.assertTrue(result.trades.empty)
        self.assertEqual(result.final_equity, 1000)

    def test_transaction_costs_reduce_affordable_buy_quantity(self) -> None:
        execution_model = ExecutionModel(
            TransactionCostModel(
                commission_fixed=1.0,
                commission_rate=0.0,
                slippage_bps=0.0,
            )
        )

        result = StaticWeightPortfolioBacktester(
            initial_cash=1000,
            execution_model=execution_model,
        ).run(portfolio_spec(), dataset())

        self.assertAlmostEqual(result.trades["commission"].sum(), 2.0)
        self.assertLess(result.final_equity, 1060.0)
        self.assertGreaterEqual(result.final_cash, -1e-9)

    def test_rejects_dataset_missing_spec_symbol(self) -> None:
        data = dataset()
        data = MultiAssetDataSet(
            symbols={"QQQ": data.symbols["QQQ"]},
            calendar=data.calendar,
            alignment_policy="intersection",
            data_quality={},
            fingerprints={},
            dropped_rows_by_symbol={"QQQ": 0},
        )

        with self.assertRaisesRegex(ValueError, "dataset is missing portfolio symbols"):
            StaticWeightPortfolioBacktester(initial_cash=1000).run(portfolio_spec(), data)


if __name__ == "__main__":
    unittest.main()
