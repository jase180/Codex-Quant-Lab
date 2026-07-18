from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.cli import main  # noqa: E402

from cli_fixtures import _read_jsonl, _strategy_payload, _write_ohlcv_fixture  # noqa: E402


class CliRobustnessTests(unittest.TestCase):
    def test_cost_sensitivity_runs_requested_presets_and_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "robustness" / "costs"
            index_path = temp_path / "research_index.jsonl"
            experiments_path = temp_path / "experiments.jsonl"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "new-experiment",
                        "--experiments-path",
                        str(experiments_path),
                        "--experiment-id",
                        "EXP-001",
                        "--title",
                        "Cost sensitivity check",
                        "--hypothesis",
                        "A valid hypothesis.",
                    ]
                )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "robustness",
                        "cost-sensitivity",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--initial-cash",
                        "1000",
                        "--quantity",
                        "3",
                        "--cost-preset",
                        "none",
                        "--cost-preset",
                        "retail-liquid",
                        "--index-path",
                        str(index_path),
                        "--experiments-path",
                        str(experiments_path),
                        "--experiment-id",
                        "EXP-001",
                    ]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Cost sensitivity complete: 2 runs", output)
            self.assertIn("cost_sensitivity_summary.csv", output)
            self.assertIn("cost_sensitivity_report.md", output)
            self.assertTrue((output_dir / "cost_001_none" / "run_metadata.json").exists())
            self.assertTrue((output_dir / "cost_002_retail_liquid" / "run_metadata.json").exists())

            summary = (output_dir / "cost_sensitivity_summary.csv").read_text(encoding="utf-8")
            self.assertIn("cost_001_none", summary)
            self.assertIn("retail-liquid", summary)
            self.assertIn("metadata_path", summary)

            report = (output_dir / "cost_sensitivity_report.md").read_text(encoding="utf-8")
            self.assertIn("# Cost Sensitivity Report", report)
            self.assertIn("## Verdict", report)
            self.assertIn("Inspect child run reports", report)

            index_rows = _read_jsonl(index_path)
            self.assertEqual(len(index_rows), 2)
            self.assertEqual({row["run_type"] for row in index_rows}, {"cost_sensitivity_run"})
            self.assertEqual({row["cost_preset"] for row in index_rows}, {"none", "retail-liquid"})

            experiment_rows = _read_jsonl(experiments_path)
            self.assertEqual(len(experiment_rows[0]["linked_runs"]), 2)

    def test_list_runs_can_filter_cost_sensitivity_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            index_path = temp_path / "research_index.jsonl"
            index_path.write_text(
                json.dumps(
                    {
                        "index_schema_version": "research_index.v1",
                        "created_at_utc": "2026-01-01T00:00:00Z",
                        "run_type": "cost_sensitivity_run",
                        "run_id": "cost_001_none",
                        "experiment_id": "EXP-001",
                        "strategy_id": "cli_smoke",
                        "strategy_name": "CLI Smoke",
                        "symbol": "QQQ",
                        "timeframe": "1d",
                        "data_start": "2026-01-01",
                        "data_end": "2026-01-31",
                        "final_equity": 1000,
                        "total_return": 0,
                        "cagr": None,
                        "sharpe_ratio": None,
                        "max_drawdown": 0,
                        "trade_count": 0,
                        "benchmark_name": "buy-and-hold",
                        "benchmark_total_return": 0,
                        "benchmark_max_drawdown": 0,
                        "excess_total_return": 0,
                        "sizing": "fixed-shares",
                        "initial_cash": 1000,
                        "quantity": 1,
                        "allocation": 1,
                        "cost_preset": "none",
                        "commission_fixed": 0,
                        "commission_rate": 0,
                        "slippage_bps": 0,
                        "output_dir": "artifacts/robustness/cost_001_none",
                        "metadata_path": "artifacts/robustness/cost_001_none/run_metadata.json",
                        "git_commit": "unknown",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "list-runs",
                        "--index-path",
                        str(index_path),
                        "--run-type",
                        "cost_sensitivity_run",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("cost_sensitivity_run", stdout.getvalue())

    def test_date_sensitivity_runs_requested_windows_and_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "robustness" / "dates"
            index_path = temp_path / "research_index.jsonl"
            experiments_path = temp_path / "experiments.jsonl"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "new-experiment",
                        "--experiments-path",
                        str(experiments_path),
                        "--experiment-id",
                        "EXP-001",
                        "--title",
                        "Date sensitivity check",
                        "--hypothesis",
                        "A valid hypothesis.",
                    ]
                )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "robustness",
                        "date-sensitivity",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--initial-cash",
                        "1000",
                        "--quantity",
                        "3",
                        "--cost-preset",
                        "retail-liquid",
                        "--window",
                        "2026-01-01,2026-01-02",
                        "--window",
                        "2026-01-03,2026-01-04",
                        "--index-path",
                        str(index_path),
                        "--experiments-path",
                        str(experiments_path),
                        "--experiment-id",
                        "EXP-001",
                    ]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Date sensitivity complete: 2 runs", output)
            self.assertIn("date_sensitivity_summary.csv", output)
            self.assertIn("date_sensitivity_report.md", output)
            self.assertTrue((output_dir / "window_001" / "run_metadata.json").exists())
            self.assertTrue((output_dir / "window_002" / "run_metadata.json").exists())

            summary = (output_dir / "date_sensitivity_summary.csv").read_text(encoding="utf-8")
            self.assertIn("window_start", summary)
            self.assertIn("2026-01-01", summary)
            self.assertIn("metadata_path", summary)

            report = (output_dir / "date_sensitivity_report.md").read_text(encoding="utf-8")
            self.assertIn("# Date Sensitivity Report", report)
            self.assertIn("Do not move window dates after seeing the results.", report)

            index_rows = _read_jsonl(index_path)
            self.assertEqual(len(index_rows), 2)
            self.assertEqual({row["run_type"] for row in index_rows}, {"date_sensitivity_run"})

            metadata = json.loads((output_dir / "window_001" / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["parameters"]["window_start"], "2026-01-01")

            experiment_rows = _read_jsonl(experiments_path)
            self.assertEqual(len(experiment_rows[0]["linked_runs"]), 2)

    def test_date_sensitivity_rejects_invalid_window_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with self.assertRaisesRegex(ValueError, "start must be on or before end"):
                main(
                    [
                        "robustness",
                        "date-sensitivity",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(temp_path / "out"),
                        "--window",
                        "2026-01-04,2026-01-01",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
