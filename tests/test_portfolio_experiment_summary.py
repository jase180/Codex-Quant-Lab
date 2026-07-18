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
                cost_preset="retail-liquid",
                benchmark_name="buy-and-hold-spy",
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
                cost_preset="retail-liquid",
                benchmark_name="buy-and-hold-spy",
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
        self.assertIn("## Evidence Label", summary)
        self.assertIn("Label: `mixed`", summary)
        self.assertIn("No portfolio data trust report was found beside linked metadata.", summary)
        self.assertIn("1 linked portfolio run(s) underperformed the benchmark.", summary)
        self.assertIn("Best excess return: qqq_50_spy_50 (2.00%)", summary)
        self.assertIn("Benchmark underperformers: 1 of 2 portfolio runs.", summary)
        self.assertIn("Runs with drawdown at or below -20.00%: 1.", summary)
        self.assertIn("Allocation variant count is reviewable: 2 linked runs.", summary)
        self.assertIn("Cost presets represented: `retail-liquid`.", summary)
        self.assertIn("Benchmarks represented: `buy-and-hold-spy`.", summary)
        self.assertIn("No portfolio cost-sensitivity evidence is visible in linked runs.", summary)
        self.assertIn("No portfolio benchmark-substitution evidence is visible in linked runs.", summary)
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
        self.assertIn("Label: `no_evidence`", summary)
        self.assertIn("No linked portfolio run evidence exists yet.", summary)
        self.assertIn("No linked portfolio runs", summary)

    def test_formats_promising_portfolio_evidence_when_trusted_and_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            run_a = temp_path / "portfolio_a"
            run_b = temp_path / "portfolio_b"
            run_a.mkdir()
            run_b.mkdir()
            (run_a / "portfolio_data_trust_report.md").write_text("# Trust\n", encoding="utf-8")
            experiment = create_experiment_record(
                experiment_id="EXP-001",
                title="QQQ SPY allocations",
                hypothesis="Allocation variants may beat SPY.",
                created_at_utc="2026-01-01T00:00:00Z",
            )
            records = [
                _portfolio_record(
                    experiment_id="EXP-001",
                    strategy_id="qqq_50_spy_50",
                    symbol="QQQ,SPY",
                    total_return=0.08,
                    excess_total_return=0.03,
                    benchmark_total_return=0.05,
                    max_drawdown=-0.12,
                    sharpe_ratio=0.8,
                    cost_preset="retail-liquid",
                    benchmark_name="buy-and-hold-spy",
                    metadata_path=str(run_a / "portfolio_metadata.json"),
                    output_dir=str(run_a),
                ),
                _portfolio_record(
                    experiment_id="EXP-001",
                    strategy_id="qqq_60_spy_40",
                    symbol="QQQ,SPY",
                    total_return=0.07,
                    excess_total_return=0.02,
                    benchmark_total_return=0.05,
                    max_drawdown=-0.10,
                    sharpe_ratio=0.7,
                    cost_preset="high-friction",
                    benchmark_name="buy-and-hold-qqq",
                    metadata_path=str(run_b / "portfolio_metadata.json"),
                    output_dir=str(run_b),
                ),
            ]

            summary = format_portfolio_experiment_summary(experiment, records)

        self.assertIn("Label: `promising`", summary)
        self.assertIn("Multiple linked portfolio runs beat the benchmark.", summary)
        self.assertIn("Portfolio data trust report found for linked evidence.", summary)
        self.assertIn("Best allocation clears the marginal edge check: 3.00% excess return.", summary)
        self.assertIn("Portfolio cost-sensitivity evidence is visible across linked runs.", summary)
        self.assertIn("Portfolio benchmark-substitution evidence is visible across linked runs.", summary)

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
    cost_preset: str = "retail-liquid",
    benchmark_name: str = "buy-and-hold-spy",
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
        "cost_preset": cost_preset,
        "benchmark_name": benchmark_name,
        "metadata_path": metadata_path,
        "output_dir": output_dir,
    }


if __name__ == "__main__":
    unittest.main()
