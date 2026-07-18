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
    def test_list_portfolio_templates_command_prints_templates(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["list-portfolio-templates"])

        self.assertEqual(exit_code, 0)
        self.assertIn("qqq-spy-60-40", stdout.getvalue())

    def test_new_portfolio_command_writes_valid_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "qqq_spy_static_60_40.json"

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "new-portfolio",
                        "--template",
                        "qqq-spy-60-40",
                        "--out",
                        str(output_path),
                    ]
                )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertIn("Portfolio template written", stdout.getvalue())
            self.assertEqual(payload["portfolio_id"], "qqq_spy_static_60_40")
            self.assertEqual([symbol["symbol"] for symbol in payload["symbols"]], ["QQQ", "SPY"])

            with self.assertRaises(FileExistsError):
                main(
                    [
                        "new-portfolio",
                        "--template",
                        "qqq-spy-60-40",
                        "--out",
                        str(output_path),
                    ]
                )

    def test_portfolio_variants_command_writes_weight_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            portfolio_path = workspace / "portfolio.json"
            output_dir = workspace / "variants"
            write_portfolio(portfolio_path)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "portfolio-variants",
                        "--portfolio",
                        str(portfolio_path),
                        "--weights",
                        "QQQ=0.5,SPY=0.5",
                        "--weights",
                        "QQQ=0.7,SPY=0.3",
                        "--rebalance",
                        "none",
                        "--rebalance",
                        "quarterly",
                        "--out",
                        str(output_dir),
                    ]
                )

            first_path = output_dir / "qqq_spy_static_60_40_qqq_5000bp_spy_5000bp_rebalance_none.json"
            second_path = output_dir / "qqq_spy_static_60_40_qqq_7000bp_spy_3000bp_rebalance_quarterly.json"
            first_payload = json.loads(first_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertTrue(first_path.exists())
            self.assertTrue(second_path.exists())
            self.assertIn("Portfolio variants written: 4", stdout.getvalue())
            self.assertEqual(first_payload["symbols"][0]["target_weight"], 0.5)
            self.assertEqual(first_payload["symbols"][1]["target_weight"], 0.5)
            self.assertEqual(first_payload["rebalance"]["frequency"], "none")

    def test_portfolio_candidates_command_writes_capped_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            data_dir = workspace / "data"
            output_dir = workspace / "candidates"
            data_dir.mkdir()
            write_ohlcv(data_dir / "QQQ.csv", [("2026-01-01", 100)])
            write_ohlcv(data_dir / "SPY.csv", [("2026-01-01", 100)])
            write_ohlcv(data_dir / "TLT.csv", [("2026-01-01", 100)])

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "portfolio-candidates",
                        "--symbols",
                        "QQQ,SPY,TLT",
                        "--step",
                        "0.25",
                        "--data-dir",
                        str(data_dir),
                        "--out",
                        str(output_dir),
                        "--max-candidates",
                        "2",
                        "--benchmark-symbol",
                        "SPY",
                    ]
                )

            written_files = sorted(output_dir.glob("*.json"))
            payload = json.loads(written_files[0].read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(written_files), 2)
            self.assertIn("Portfolio candidates written: 2", stdout.getvalue())
            self.assertIn("skipped_candidates: 1", stdout.getvalue())
            self.assertEqual(payload["benchmark"]["symbol"], "SPY")

    def test_portfolio_batch_plan_command_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            portfolios_dir = workspace / "candidates"
            output_dir = workspace / "batch"
            portfolios_dir.mkdir()
            write_portfolio(portfolios_dir / "candidate.json")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "portfolio-batch",
                        "plan",
                        "--portfolios",
                        str(portfolios_dir),
                        "--out",
                        str(output_dir),
                        "--initial-cash",
                        "25000",
                        "--cost-preset",
                        "retail-liquid",
                    ]
                )

            manifest_path = output_dir / "portfolio_batch_manifest.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertIn("Portfolio batch manifest written", stdout.getvalue())
            self.assertIn("planned_runs: 1", stdout.getvalue())
            self.assertEqual(payload["item_count"], 1)
            self.assertEqual(payload["items"][0]["status"], "planned")
            self.assertIn("--initial-cash", payload["items"][0]["command"])
            self.assertIn("25000.0", payload["items"][0]["command"])

    def test_portfolio_batch_run_command_executes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            data_dir = workspace / "data"
            portfolios_dir = workspace / "candidates"
            output_dir = workspace / "batch"
            index_path = workspace / "research_index.jsonl"
            experiments_path = workspace / "experiments.jsonl"
            data_dir.mkdir()
            portfolios_dir.mkdir()
            write_ohlcv(data_dir / "QQQ.csv", [("2026-01-01", 100), ("2026-01-02", 110), ("2026-01-05", 120)])
            write_ohlcv(data_dir / "SPY.csv", [("2026-01-01", 100), ("2026-01-02", 100), ("2026-01-05", 100)])
            _write_absolute_portfolio(
                portfolios_dir / "candidate.json",
                qqq_data=data_dir / "QQQ.csv",
                spy_data=data_dir / "SPY.csv",
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
                        "Portfolio batch smoke",
                        "--hypothesis",
                        "Batch runner should execute planned portfolio runs.",
                    ]
                )
                plan_exit_code = main(
                    [
                        "portfolio-batch",
                        "plan",
                        "--portfolios",
                        str(portfolios_dir),
                        "--out",
                        str(output_dir),
                        "--index-path",
                        str(index_path),
                        "--experiments-path",
                        str(experiments_path),
                    ]
                )
                run_exit_code = main(
                    [
                        "portfolio-batch",
                        "run",
                        "--manifest",
                        str(output_dir / "portfolio_batch_manifest.json"),
                        "--experiment-id",
                        "EXP-001",
                    ]
                )
                summarize_exit_code = main(
                    [
                        "portfolio-batch",
                        "summarize",
                        "--manifest",
                        str(output_dir / "portfolio_batch_manifest.json"),
                    ]
                )

            result_payload = json.loads((output_dir / "portfolio_batch_result.json").read_text(encoding="utf-8"))
            self.assertEqual(create_exit_code, 0)
            self.assertEqual(plan_exit_code, 0)
            self.assertEqual(run_exit_code, 0)
            self.assertEqual(summarize_exit_code, 0)
            self.assertIn("Portfolio batch result written", stdout.getvalue())
            self.assertIn("Portfolio batch summary written", stdout.getvalue())
            self.assertEqual(result_payload["completed_count"], 1)
            self.assertTrue((output_dir / "runs" / "candidate" / "portfolio_metadata.json").exists())
            self.assertTrue((output_dir / "portfolio_batch_summary.md").exists())

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


def _write_absolute_portfolio(path: Path, *, qqq_data: Path, spy_data: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "portfolio_plan.v1",
                "portfolio_id": "candidate",
                "name": "Candidate",
                "description": "Static two-symbol allocation.",
                "symbols": [
                    {"symbol": "QQQ", "data": str(qqq_data), "target_weight": 0.60},
                    {"symbol": "SPY", "data": str(spy_data), "target_weight": 0.40},
                ],
                "rebalance": {"frequency": "monthly"},
                "benchmark": {"symbol": "SPY", "data": str(spy_data)},
            }
        )
        + "\n",
        encoding="utf-8",
    )
