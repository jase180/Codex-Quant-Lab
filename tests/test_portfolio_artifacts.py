from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.costs import COST_PRESETS  # noqa: E402
from quant_lab.portfolio_artifacts import save_portfolio_artifacts  # noqa: E402
from quant_lab.portfolio_backtest import StaticWeightPortfolioBacktester  # noqa: E402
from quant_lab.portfolio_data import load_multi_asset_dataset  # noqa: E402
from quant_lab.portfolio_spec import load_portfolio_spec  # noqa: E402


def write_ohlcv(path: Path, rows: list[tuple[str, float]]) -> None:
    lines = ["date,open,high,low,close,volume"]
    for date_value, close in rows:
        lines.append(f"{date_value},{close},{close + 1},{close - 1},{close},1000")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class PortfolioArtifactsTests(unittest.TestCase):
    def test_save_portfolio_artifacts_writes_expected_files_and_metadata(self) -> None:
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
                    ("2026-01-02", 200),
                    ("2026-01-05", 200),
                ],
            )
            portfolio_path = workspace / "portfolio.json"
            portfolio_path.write_text(
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
            portfolio = load_portfolio_spec(portfolio_path)
            dataset = load_multi_asset_dataset(portfolio)
            result = StaticWeightPortfolioBacktester(initial_cash=1000).run(portfolio, dataset)
            output_dir = workspace / "artifacts"

            saved = save_portfolio_artifacts(
                portfolio=portfolio,
                dataset=dataset,
                result=result,
                output_dir=output_dir,
                initial_cash=1000,
                cost_assumptions=COST_PRESETS["none"],
                command=["quant-lab", "portfolio-run"],
            )

            metadata = json.loads(Path(saved.artifact_paths["metadata"]).read_text(encoding="utf-8"))
            metrics = json.loads(Path(saved.artifact_paths["metrics"]).read_text(encoding="utf-8"))
            report = Path(saved.artifact_paths["report"]).read_text(encoding="utf-8")
            trades_csv = Path(saved.artifact_paths["trades"]).read_text(encoding="utf-8")

        self.assertEqual(metadata["metadata_schema_version"], "portfolio_metadata.v1")
        self.assertEqual(metadata["run_type"], "portfolio_run")
        self.assertEqual(metadata["portfolio_id"], "qqq_spy_static_60_40")
        self.assertEqual(metadata["command"], ["quant-lab", "portfolio-run"])
        self.assertEqual(len(metadata["symbols"]), 2)
        self.assertIn("file_sha256", metadata["portfolio_spec"])
        self.assertIn("portfolio_equity_curve.csv", metadata["artifacts"]["equity_curve"])
        self.assertAlmostEqual(metrics["ending_equity"], saved.metrics.ending_equity)
        self.assertIn("# QQQ SPY Static 60/40", report)
        self.assertIn("Rebalance decisions use close prices", report)
        self.assertIn("QQQ", trades_csv)

    def test_metadata_allows_in_memory_portfolio_without_spec_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_ohlcv(workspace / "QQQ.csv", [("2026-01-01", 100), ("2026-01-02", 100)])
            write_ohlcv(workspace / "SPY.csv", [("2026-01-01", 200), ("2026-01-02", 200)])
            portfolio = load_portfolio_spec(
                Path(__file__).resolve().parents[1]
                / "data"
                / "portfolios"
                / "qqq_spy_static_60_40.json"
            )
            portfolio = replace(
                portfolio,
                source_path=None,
                symbols=[
                    replace(portfolio.symbols[0], data="QQQ.csv"),
                    replace(portfolio.symbols[1], data="SPY.csv"),
                ],
                benchmark=replace(portfolio.benchmark, data="SPY.csv"),
            )
            dataset = load_multi_asset_dataset(portfolio, base_dir=workspace)
            result = StaticWeightPortfolioBacktester(initial_cash=1000).run(portfolio, dataset)

            saved = save_portfolio_artifacts(
                portfolio=portfolio,
                dataset=dataset,
                result=result,
                output_dir=workspace / "artifacts",
                initial_cash=1000,
                cost_assumptions=COST_PRESETS["none"],
            )

        self.assertIsNone(saved.metadata.portfolio_spec.path)
        self.assertIsNone(saved.metadata.portfolio_spec.file_sha256)


if __name__ == "__main__":
    unittest.main()
