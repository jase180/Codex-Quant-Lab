from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR / "tests"))

from cli_fixtures import _read_jsonl  # noqa: E402
from quant_lab.cli import main  # noqa: E402


def write_ohlcv(path: Path, rows: list[tuple[str, float]]) -> None:
    lines = ["date,open,high,low,close,volume"]
    for date_value, close in rows:
        lines.append(f"{date_value},{close},{close + 1},{close - 1},{close},1000")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_portfolio(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "portfolio_plan.v1",
                "portfolio_id": "qqq_spy_static_60_40",
                "name": "QQQ SPY Static 60/40",
                "description": "Static two-symbol allocation.",
                "symbols": [
                    {"symbol": "QQQ", "data": "QQQ.csv", "target_weight": 0.60},
                    {"symbol": "SPY", "data": "SPY.csv", "target_weight": 0.40},
                ],
                "rebalance": {"frequency": "monthly"},
                "benchmark": {"symbol": "SPY", "data": "SPY.csv"},
            }
        ),
        encoding="utf-8",
    )


class CliPortfolioTests(unittest.TestCase):
    def test_portfolio_run_writes_artifacts_index_and_experiment_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            portfolio_path = workspace / "portfolio.json"
            output_dir = workspace / "artifacts"
            index_path = workspace / "research_index.jsonl"
            experiments_path = workspace / "experiments.jsonl"
            write_portfolio(portfolio_path)
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
                    ("2026-01-02", 200),
                    ("2026-01-05", 200),
                ],
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                create_exit_code = main(
                    [
                        "new-experiment",
                        "--experiments-path",
                        str(experiments_path),
                        "--experiment-id",
                        "EXP-001",
                        "--title",
                        "Portfolio smoke",
                        "--hypothesis",
                        "A static portfolio should create auditable artifacts.",
                    ]
                )
                exit_code = main(
                    [
                        "portfolio-run",
                        "--portfolio",
                        str(portfolio_path),
                        "--out",
                        str(output_dir),
                        "--initial-cash",
                        "1000",
                        "--index-path",
                        str(index_path),
                        "--experiments-path",
                        str(experiments_path),
                        "--experiment-id",
                        "EXP-001",
                    ]
                )

            metadata = json.loads((output_dir / "portfolio_metadata.json").read_text(encoding="utf-8"))
            index_rows = _read_jsonl(index_path)
            experiment_rows = _read_jsonl(experiments_path)
            metrics_exists = (output_dir / "portfolio_metrics.json").exists()
            benchmark_metrics_exists = (output_dir / "portfolio_benchmark_metrics.json").exists()
            report_exists = (output_dir / "portfolio_report.md").exists()

        self.assertEqual(create_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Portfolio run complete", stdout.getvalue())
        self.assertTrue(metrics_exists)
        self.assertTrue(benchmark_metrics_exists)
        self.assertTrue(report_exists)
        self.assertEqual(metadata["run_type"], "portfolio_run")
        self.assertEqual(metadata["benchmark"]["symbol"], "SPY")
        self.assertEqual(index_rows[0]["run_type"], "portfolio_run")
        self.assertEqual(index_rows[0]["strategy_id"], "qqq_spy_static_60_40")
        self.assertEqual(index_rows[0]["symbol"], "QQQ,SPY")
        self.assertEqual(index_rows[0]["experiment_id"], "EXP-001")
        self.assertEqual(index_rows[0]["metadata_path"], str(output_dir / "portfolio_metadata.json"))
        self.assertEqual(experiment_rows[0]["linked_runs"], [str(output_dir / "portfolio_metadata.json")])

    def test_list_runs_symbol_filter_matches_portfolio_component_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "research_index.jsonl"
            index_path.write_text(
                json.dumps(
                    {
                        "index_schema_version": "research_index.v1",
                        "created_at_utc": "2026-01-01T00:00:00Z",
                        "run_type": "portfolio_run",
                        "run_id": None,
                        "experiment_id": None,
                        "strategy_id": "qqq_spy_static_60_40",
                        "strategy_name": "QQQ SPY Static 60/40",
                        "symbol": "QQQ,SPY",
                        "timeframe": "1d",
                        "data_start": "2026-01-01",
                        "data_end": "2026-01-05",
                        "final_equity": 1060,
                        "total_return": 0.06,
                        "cagr": None,
                        "sharpe_ratio": None,
                        "max_drawdown": 0,
                        "trade_count": 2,
                        "benchmark_name": "buy-and-hold-spy",
                        "benchmark_total_return": 0,
                        "benchmark_max_drawdown": 0,
                        "excess_total_return": 0.06,
                        "sizing": "static-weights",
                        "initial_cash": 1000,
                        "quantity": 0,
                        "allocation": 1,
                        "cost_preset": "none",
                        "commission_fixed": 0,
                        "commission_rate": 0,
                        "slippage_bps": 0,
                        "output_dir": "artifacts/portfolio",
                        "metadata_path": "artifacts/portfolio/portfolio_metadata.json",
                        "git_commit": "abc",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["list-runs", "--index-path", str(index_path), "--symbol", "SPY"])

        self.assertEqual(exit_code, 0)
        self.assertIn("qqq_spy_static_60_40", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
