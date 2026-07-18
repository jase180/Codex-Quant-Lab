from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.portfolio_experiment_summary import (  # noqa: E402
    format_portfolio_experiment_summary,
    save_portfolio_experiment_summary,
)
from quant_lab.research_registry import create_experiment_record, link_runs_to_experiment  # noqa: E402


class PortfolioExperimentSummaryTests(unittest.TestCase):
    def test_formats_portfolio_experiment_summary(self) -> None:
        experiment = link_runs_to_experiment(
            create_experiment_record(
                experiment_id="EXP-001",
                title="QQQ SPY allocations",
                hypothesis="Allocation variants may beat SPY.",
                status="running",
                created_at_utc="2026-01-01T00:00:00Z",
            ),
            ["artifacts/portfolio_a/portfolio_metadata.json"],
        )
        records = [
            _portfolio_record(
                experiment_id="EXP-001",
                strategy_id="qqq_50_spy_50",
                symbol="QQQ,SPY",
                total_return=0.08,
                excess_total_return=0.02,
                benchmark_total_return=0.06,
                max_drawdown=-0.12,
                sharpe_ratio=0.8,
                metadata_path="artifacts/portfolio_a/portfolio_metadata.json",
                output_dir="artifacts/portfolio_a",
            ),
            _portfolio_record(
                experiment_id="EXP-001",
                strategy_id="qqq_70_spy_30",
                symbol="QQQ,SPY",
                total_return=0.03,
                excess_total_return=-0.04,
                benchmark_total_return=0.07,
                max_drawdown=-0.24,
                sharpe_ratio=0.2,
                metadata_path="artifacts/portfolio_b/portfolio_metadata.json",
                output_dir="artifacts/portfolio_b",
            ),
            {
                "experiment_id": "EXP-001",
                "run_type": "run",
                "strategy_id": "single_symbol_run",
                "excess_total_return": 0.99,
            },
        ]

        summary = format_portfolio_experiment_summary(experiment, records)

        self.assertIn("# Portfolio Experiment Summary", summary)
        self.assertIn("Linked portfolio index rows: 2", summary)
        self.assertIn("Best excess return: qqq_50_spy_50 (2.00%)", summary)
        self.assertIn("Benchmark underperformers: 1 of 2 portfolio runs.", summary)
        self.assertIn("Runs with drawdown at or below -20%: 1.", summary)
        self.assertIn("## Top By Excess Return", summary)
        self.assertIn("## Worst Drawdowns", summary)
        self.assertIn("`artifacts/portfolio_a/portfolio_metadata.json`", summary)
        self.assertNotIn("single_symbol_run", summary)

    def test_formats_summary_without_portfolio_evidence(self) -> None:
        experiment = create_experiment_record(
            experiment_id="EXP-001",
            title="QQQ SPY allocations",
            hypothesis="Allocation variants may beat SPY.",
            created_at_utc="2026-01-01T00:00:00Z",
        )

        summary = format_portfolio_experiment_summary(experiment, [])

        self.assertIn("Linked portfolio index rows: 0", summary)
        self.assertIn("No linked portfolio runs", summary)

    def test_save_portfolio_experiment_summary_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "portfolio_summary.md"

            saved_path = save_portfolio_experiment_summary("# Summary", path)

            self.assertEqual(saved_path, str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), "# Summary\n")


def _portfolio_record(
    *,
    experiment_id: str,
    strategy_id: str,
    symbol: str,
    total_return: float,
    excess_total_return: float,
    benchmark_total_return: float,
    max_drawdown: float,
    sharpe_ratio: float,
    metadata_path: str,
    output_dir: str,
) -> dict:
    return {
        "experiment_id": experiment_id,
        "created_at_utc": "2026-01-02T00:00:00Z",
        "run_type": "portfolio_run",
        "strategy_id": strategy_id,
        "symbol": symbol,
        "total_return": total_return,
        "excess_total_return": excess_total_return,
        "benchmark_total_return": benchmark_total_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "cost_preset": "retail-liquid",
        "metadata_path": metadata_path,
        "output_dir": output_dir,
    }


if __name__ == "__main__":
    unittest.main()
