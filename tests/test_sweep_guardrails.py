from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from quant_lab.summary_rows import SWEEP_SUMMARY_FIELDNAMES
from quant_lab.sweep_guardrails import load_sweep_summary_rows, summarize_sweep_guardrails


class SweepGuardrailTests(unittest.TestCase):
    def test_summarize_sweep_guardrails_writes_warnings_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_path = Path(temp_dir) / "summary.csv"
            _write_summary(
                summary_path,
                [
                    _row("run_001", total_return=0.10, benchmark_total_return=0.20, trade_count=1, fast=5),
                    _row("run_002", total_return=0.05, benchmark_total_return=0.20, trade_count=1, fast=10),
                ],
            )

            report = summarize_sweep_guardrails(
                summary_path=summary_path,
                max_rows=1,
                min_trades=5,
            )

            markdown = Path(report.report_path).read_text(encoding="utf-8")
            self.assertEqual(report.row_count, 2)
            self.assertEqual(report.best_run_id, "run_001")
            self.assertTrue(any("Large parameter grid" in warning for warning in report.warnings))
            self.assertTrue(any("Best run did not beat" in warning for warning in report.warnings))
            self.assertTrue(any("Best run has only 1 trade" in warning for warning in report.warnings))
            self.assertIn("# Sweep Guardrails", markdown)
            self.assertIn("`run_001`", markdown)

    def test_summarize_sweep_guardrails_accepts_supported_small_sweep(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_path = Path(temp_dir) / "summary.csv"
            _write_summary(
                summary_path,
                [
                    _row("run_001", total_return=0.30, benchmark_total_return=0.10, trade_count=12, fast=5),
                    _row("run_002", total_return=0.28, benchmark_total_return=0.10, trade_count=11, fast=10),
                ],
            )

            report = summarize_sweep_guardrails(summary_path=summary_path)

            self.assertEqual(report.warnings, [])

    def test_load_sweep_summary_rows_requires_known_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_path = Path(temp_dir) / "summary.csv"
            summary_path.write_text("run_id,total_return\nrun_001,0.1\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing required columns"):
                load_sweep_summary_rows(summary_path)


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
    trade_count: int,
    fast: int,
) -> dict:
    return {
        "run_id": run_id,
        "strategy_id": "test_strategy",
        "params": f'{{"fast": {fast}}}',
        "final_equity": 1000 * (1 + total_return),
        "total_return": total_return,
        "cagr": "",
        "sharpe_ratio": 1.0,
        "max_drawdown": -0.05,
        "trade_count": trade_count,
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
