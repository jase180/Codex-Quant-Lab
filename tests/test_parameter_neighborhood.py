from __future__ import annotations

import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.cli import main
from quant_lab.parameter_neighborhood import summarize_parameter_neighborhood
from quant_lab.summary_rows import SWEEP_SUMMARY_FIELDNAMES


class ParameterNeighborhoodTests(unittest.TestCase):
    def test_supported_neighborhood_requires_neighbors_to_beat_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_path = Path(temp_dir) / "summary.csv"
            _write_summary(
                summary_path,
                [
                    _row("run_001", total_return=0.30, benchmark_total_return=0.10, params={"fast": 5, "slow": 50}),
                    _row("run_002", total_return=0.25, benchmark_total_return=0.10, params={"fast": 10, "slow": 50}),
                    _row("run_003", total_return=0.22, benchmark_total_return=0.10, params={"fast": 5, "slow": 100}),
                    _row("run_004", total_return=0.05, benchmark_total_return=0.10, params={"fast": 10, "slow": 100}),
                ],
            )

            result = summarize_parameter_neighborhood(summary_path=summary_path)

            self.assertEqual(result.assessment, "supported")
            self.assertEqual({row["parameter"] for row in result.rows}, {"fast", "slow"})
            self.assertEqual({row["assessment"] for row in result.rows}, {"supported"})
            markdown = Path(result.report_path).read_text(encoding="utf-8")
            self.assertIn("# Parameter Neighborhood Report", markdown)
            self.assertIn("nearby numeric values also beat the benchmark", markdown)

    def test_isolated_winner_when_neighbors_do_not_beat_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_path = Path(temp_dir) / "summary.csv"
            _write_summary(
                summary_path,
                [
                    _row("run_001", total_return=0.30, benchmark_total_return=0.10, params={"fast": 5}),
                    _row("run_002", total_return=0.05, benchmark_total_return=0.10, params={"fast": 10}),
                    _row("run_003", total_return=0.00, benchmark_total_return=0.10, params={"fast": 20}),
                ],
            )

            result = summarize_parameter_neighborhood(summary_path=summary_path)

            self.assertEqual(result.assessment, "isolated")
            self.assertEqual(result.rows[0]["assessment"], "isolated")
            self.assertEqual(result.rows[0]["benchmark_beating_neighbors"], 0)

    def test_skips_non_numeric_and_counts_missing_parameter_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_path = Path(temp_dir) / "summary.csv"
            _write_summary(
                summary_path,
                [
                    _row(
                        "run_001",
                        total_return=0.30,
                        benchmark_total_return=0.10,
                        params={"fast": 5, "mode": "trend"},
                    ),
                    _row(
                        "run_002",
                        total_return=0.25,
                        benchmark_total_return=0.10,
                        params={"fast": 10, "mode": "trend"},
                    ),
                    _row(
                        "run_003",
                        total_return=0.20,
                        benchmark_total_return=0.10,
                        params={"fast": 20},
                    ),
                ],
            )

            result = summarize_parameter_neighborhood(summary_path=summary_path)

            self.assertEqual(result.skipped_parameters, ["mode"])
            self.assertEqual(result.incompatible_row_count, 1)
            self.assertEqual(len(result.rows), 1)
            self.assertEqual(result.rows[0]["parameter"], "fast")

    def test_parameter_neighborhood_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            summary_path = temp_path / "summary.csv"
            output_dir = temp_path / "neighborhood"
            _write_summary(
                summary_path,
                [
                    _row("run_001", total_return=0.30, benchmark_total_return=0.10, params={"fast": 5}),
                    _row("run_002", total_return=0.25, benchmark_total_return=0.10, params={"fast": 10}),
                ],
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "robustness",
                        "parameter-neighborhood",
                        "--summary",
                        str(summary_path),
                        "--out",
                        str(output_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("Parameter neighborhood report written", stdout.getvalue())
            self.assertTrue((output_dir / "parameter_neighborhood_summary.csv").exists())
            self.assertTrue((output_dir / "parameter_neighborhood_report.md").exists())


def _write_summary(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SWEEP_SUMMARY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _row(
    run_id: str,
    *,
    total_return: float,
    benchmark_total_return: float,
    params: dict,
) -> dict:
    return {
        "run_id": run_id,
        "strategy_id": "test_strategy",
        "params": json.dumps(params, sort_keys=True),
        "final_equity": 1000 * (1 + total_return),
        "total_return": total_return,
        "cagr": "",
        "sharpe_ratio": 1.0,
        "max_drawdown": -0.05,
        "trade_count": 12,
        "sizing": "fixed-shares",
        "quantity": 1,
        "allocation": 1,
        "cost_preset": "none",
        "commission_fixed": 0,
        "commission_rate": 0,
        "slippage_bps": 0,
        "benchmark_name": "buy-and-hold",
        "benchmark_final_equity": 1000 * (1 + benchmark_total_return),
        "benchmark_total_return": benchmark_total_return,
        "benchmark_cagr": "",
        "benchmark_sharpe_ratio": 1.0,
        "benchmark_max_drawdown": -0.04,
        "excess_total_return": total_return - benchmark_total_return,
        "output_dir": f"runs/{run_id}",
    }


if __name__ == "__main__":
    unittest.main()
