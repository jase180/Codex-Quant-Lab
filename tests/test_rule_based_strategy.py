from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backtester_core import BacktestEngine  # noqa: E402
from quant_lab import build_rule_based_strategy, indicator_values, parse_strategy  # noqa: E402


def _strategy_payload(
    *,
    indicators,
    entry_conditions,
    exit_conditions,
    exit_when="all",
):
    return {
        "schema_version": "v1",
        "strategy_id": "test_strategy",
        "name": "Test Strategy",
        "description": "Strategy fixture for executable rule tests.",
        "strategy_type": "rule_based",
        "position_mode": "long_only",
        "market": {"symbol": "TEST", "timeframe": "1d"},
        "indicators": indicators,
        "entry": {"when": "all", "conditions": entry_conditions},
        "exit": {"when": exit_when, "conditions": exit_conditions},
    }


class RuleBasedStrategyTests(unittest.TestCase):
    def test_indicator_values_are_incremental_and_close_based(self) -> None:
        self.assertEqual(indicator_values("sma", 3, [1, 2, 3, 4]), [None, None, 2.0, 3.0])
        self.assertEqual(indicator_values("ema", 3, [10, 20, 30]), [10.0, 15.0, 22.5])
        self.assertEqual(indicator_values("rsi", 2, [10, 11, 12]), [None, None, 100.0])

    def test_sma_crossover_spec_runs_as_backtest_strategy(self) -> None:
        spec = parse_strategy(
            _strategy_payload(
                indicators=[
                    {"id": "fast_sma", "kind": "sma", "inputs": {"source": "close", "length": 2}},
                    {"id": "slow_sma", "kind": "sma", "inputs": {"source": "close", "length": 3}},
                ],
                entry_conditions=[
                    {
                        "left": {"indicator": "fast_sma"},
                        "operator": "crosses_above",
                        "right": {"indicator": "slow_sma"},
                    }
                ],
                exit_conditions=[
                    {
                        "left": {"indicator": "fast_sma"},
                        "operator": "crosses_below",
                        "right": {"indicator": "slow_sma"},
                    }
                ],
            )
        )
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "open": 5, "high": 5, "low": 5, "close": 5, "volume": 100},
                {"date": "2026-01-02", "open": 4, "high": 4, "low": 4, "close": 4, "volume": 100},
                {"date": "2026-01-03", "open": 3, "high": 3, "low": 3, "close": 3, "volume": 100},
                {"date": "2026-01-04", "open": 4, "high": 4, "low": 4, "close": 4, "volume": 100},
                {"date": "2026-01-05", "open": 5, "high": 5, "low": 5, "close": 5, "volume": 100},
                {"date": "2026-01-06", "open": 6, "high": 6, "low": 6, "close": 6, "volume": 100},
            ]
        )

        result = BacktestEngine(initial_cash=1_000).run(
            data,
            build_rule_based_strategy(spec, order_quantity=2),
        )

        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades.index[0], pd.Timestamp("2026-01-06"))
        self.assertEqual(result.trades.iloc[0]["side"], "buy")
        self.assertEqual(result.trades.iloc[0]["quantity"], 2)
        self.assertEqual(result.trades.iloc[0]["price"], 6.0)
        self.assertEqual(result.final_position, 2)

    def test_final_bar_signal_is_not_filled(self) -> None:
        spec = parse_strategy(
            _strategy_payload(
                indicators=[
                    {"id": "sma_3", "kind": "sma", "inputs": {"source": "close", "length": 3}},
                ],
                entry_conditions=[
                    {
                        "left": {"price": "close"},
                        "operator": "gt",
                        "right": {"indicator": "sma_3"},
                    }
                ],
                exit_conditions=[
                    {
                        "left": {"price": "close"},
                        "operator": "lt",
                        "right": {"indicator": "sma_3"},
                    }
                ],
            )
        )
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 100},
                {"date": "2026-01-02", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 100},
                {"date": "2026-01-03", "open": 20, "high": 20, "low": 20, "close": 20, "volume": 100},
            ]
        )

        result = BacktestEngine(initial_cash=1_000).run(data, build_rule_based_strategy(spec))

        self.assertTrue(result.trades.empty)
        self.assertEqual(result.final_position, 0)
        self.assertEqual(result.final_cash, 1_000.0)


if __name__ == "__main__":
    unittest.main()
