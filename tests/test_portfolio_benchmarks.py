from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.portfolio_backtest import StaticWeightPortfolioBacktester  # noqa: E402
from quant_lab.portfolio_benchmarks import (  # noqa: E402
    PortfolioBenchmarkError,
    build_portfolio_benchmark_comparison,
)
from quant_lab.portfolio_data import load_multi_asset_dataset  # noqa: E402
from quant_lab.portfolio_spec import load_portfolio_spec  # noqa: E402


def write_ohlcv(path: Path, rows: list[tuple[str, float]]) -> None:
    lines = ["date,open,high,low,close,volume"]
    for date_value, close in rows:
        lines.append(f"{date_value},{close},{close + 1},{close - 1},{close},1000")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_portfolio(path: Path) -> None:
    path.write_text(
        """{
  "schema_version": "portfolio_plan.v1",
  "portfolio_id": "qqq_spy_static_60_40",
  "name": "QQQ SPY Static 60/40",
  "description": "Static two-symbol allocation.",
  "symbols": [
    {"symbol": "QQQ", "data": "QQQ.csv", "target_weight": 0.60},
    {"symbol": "SPY", "data": "SPY.csv", "target_weight": 0.40}
  ],
  "rebalance": {"frequency": "monthly"},
  "benchmark": {"symbol": "SPY", "data": "SPY.csv"}
}
""",
        encoding="utf-8",
    )


class PortfolioBenchmarkTests(unittest.TestCase):
    def test_build_portfolio_benchmark_uses_aligned_portfolio_dates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_ohlcv(
                workspace / "QQQ.csv",
                [
                    ("2026-01-01", 100),
                    ("2026-01-02", 110),
                    ("2026-01-05", 120),
                ],
            )
            write_ohlcv(
                workspace / "SPY.csv",
                [
                    ("2026-01-01", 200),
                    ("2026-01-02", 210),
                    ("2026-01-05", 220),
                ],
            )
            portfolio_path = workspace / "portfolio.json"
            write_portfolio(portfolio_path)
            portfolio = load_portfolio_spec(portfolio_path)
            dataset = load_multi_asset_dataset(portfolio)
            result = StaticWeightPortfolioBacktester(initial_cash=1000).run(portfolio, dataset)

            benchmark = build_portfolio_benchmark_comparison(
                portfolio=portfolio,
                dataset=dataset,
                result=result,
                initial_cash=1000,
            )

        self.assertEqual([point["date"] for point in benchmark.curve], ["2026-01-01", "2026-01-02", "2026-01-05"])
        self.assertAlmostEqual(benchmark.metrics.ending_equity, 1100.0)
        self.assertAlmostEqual(benchmark.metrics.total_return, 0.10)
        self.assertAlmostEqual(benchmark.excess_total_return, result.total_return - 0.10)
        self.assertTrue(benchmark.file_sha256)

    def test_build_portfolio_benchmark_rejects_missing_aligned_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_ohlcv(
                workspace / "QQQ.csv",
                [
                    ("2026-01-01", 100),
                    ("2026-01-02", 110),
                ],
            )
            write_ohlcv(
                workspace / "SPY.csv",
                [
                    ("2026-01-01", 200),
                    ("2026-01-02", 210),
                ],
            )
            portfolio_path = workspace / "portfolio.json"
            write_portfolio(portfolio_path)
            portfolio = load_portfolio_spec(portfolio_path)
            dataset = load_multi_asset_dataset(portfolio)
            result = StaticWeightPortfolioBacktester(initial_cash=1000).run(portfolio, dataset)

            write_ohlcv(workspace / "SPY.csv", [("2026-01-01", 200)])

            with self.assertRaisesRegex(PortfolioBenchmarkError, "first missing date is 2026-01-02"):
                build_portfolio_benchmark_comparison(
                    portfolio=portfolio,
                    dataset=dataset,
                    result=result,
                    initial_cash=1000,
                )


if __name__ == "__main__":
    unittest.main()
