from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.benchmarks import (  # noqa: E402
    append_benchmark_section,
    build_benchmark,
    buy_and_hold_equity_curve,
    buy_and_hold_metrics,
    cash_equity_curve,
    cash_metrics,
    excess_total_return,
)


class BenchmarkTests(unittest.TestCase):
    def test_buy_and_hold_equity_curve_uses_first_close(self) -> None:
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "close": 10.0},
                {"date": "2026-01-02", "close": 12.0},
                {"date": "2026-01-03", "close": 15.0},
            ]
        )

        curve = buy_and_hold_equity_curve(data, initial_cash=1_000)

        self.assertEqual(curve[0], {"date": "2026-01-01", "equity": 1_000.0})
        self.assertEqual(curve[-1], {"date": "2026-01-03", "equity": 1_500.0})

    def test_buy_and_hold_metrics(self) -> None:
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "close": 10.0},
                {"date": "2026-01-02", "close": 12.0},
                {"date": "2026-01-03", "close": 15.0},
            ]
        )

        metrics = buy_and_hold_metrics(data, initial_cash=1_000)

        self.assertEqual(metrics.ending_equity, 1_500.0)
        self.assertAlmostEqual(metrics.total_return, 0.5)

    def test_cash_equity_curve_stays_flat(self) -> None:
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "close": 10.0},
                {"date": "2026-01-02", "close": 12.0},
                {"date": "2026-01-03", "close": 15.0},
            ]
        )

        curve = cash_equity_curve(data, initial_cash=1_000)
        metrics = cash_metrics(data, initial_cash=1_000)

        self.assertEqual(curve[0], {"date": "2026-01-01", "equity": 1_000.0})
        self.assertEqual(curve[-1], {"date": "2026-01-03", "equity": 1_000.0})
        self.assertEqual(metrics.total_return, 0.0)
        self.assertEqual(metrics.max_drawdown, 0.0)

    def test_build_benchmark_selects_cash(self) -> None:
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "close": 10.0},
                {"date": "2026-01-02", "close": 12.0},
                {"date": "2026-01-03", "close": 15.0},
            ]
        )

        benchmark = build_benchmark(data, initial_cash=1_000, benchmark_name="cash")

        self.assertEqual(benchmark.name, "cash")
        self.assertEqual(benchmark.display_name, "Cash")
        self.assertEqual(benchmark.metrics.total_return, 0.0)

    def test_excess_total_return(self) -> None:
        self.assertAlmostEqual(excess_total_return(0.2, 0.15), 0.05)

    def test_append_benchmark_section(self) -> None:
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "close": 10.0},
                {"date": "2026-01-02", "close": 12.0},
                {"date": "2026-01-03", "close": 15.0},
            ]
        )
        metrics = buy_and_hold_metrics(data, initial_cash=1_000)

        report = append_benchmark_section(
            "# Strategy Report\n",
            metrics,
            strategy_total_return=0.25,
            benchmark_display_name="Buy And Hold",
        )

        self.assertIn("## Benchmark: Buy And Hold", report)
        self.assertIn("| Total Return | 50.00% |", report)
        self.assertIn("| Excess Total Return | -25.00% |", report)


if __name__ == "__main__":
    unittest.main()
