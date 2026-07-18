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
from quant_lab.portfolio_inspection import (  # noqa: E402
    format_portfolio_run_summary,
    load_portfolio_run_summary,
)


class PortfolioInspectionTests(unittest.TestCase):
    def test_load_and_format_portfolio_run_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = _write_portfolio_artifacts(Path(temp_dir))

            summary = load_portfolio_run_summary(metadata_path)
            output = format_portfolio_run_summary(summary)

        self.assertEqual(summary["metadata"]["portfolio_id"], "qqq_spy_static_60_40")
        self.assertIn("Portfolio Run Summary", output)
        self.assertIn("qqq_spy_static_60_40", output)
        self.assertIn("Benchmark return: 5.00%", output)
        self.assertIn("Excess return: 1.00%", output)
        self.assertIn("QQQ: target=60.00%", output)
        self.assertIn("quality=none", output)
        self.assertIn("sha=abcdef123456", output)
        self.assertIn("portfolio_metrics.json", output)

    def test_show_portfolio_run_command_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = _write_portfolio_artifacts(Path(temp_dir))

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["show-portfolio-run", "--metadata", str(metadata_path)])

        self.assertEqual(exit_code, 0)
        self.assertIn("Portfolio Run Summary", stdout.getvalue())
        self.assertIn("QQQ SPY Static 60/40", stdout.getvalue())

    def test_load_portfolio_run_summary_rejects_missing_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.json"

            with self.assertRaises(FileNotFoundError):
                load_portfolio_run_summary(missing_path)

    def test_load_portfolio_run_summary_rejects_missing_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            metadata_path = temp_path / "portfolio_metadata.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "metadata_schema_version": "portfolio_metadata.v1",
                        "artifacts": {"metrics": str(temp_path / "missing_metrics.json")},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(FileNotFoundError):
                load_portfolio_run_summary(metadata_path)


def _write_portfolio_artifacts(temp_path: Path) -> Path:
    metrics_path = temp_path / "portfolio_metrics.json"
    metadata_path = temp_path / "portfolio_metadata.json"
    report_path = temp_path / "portfolio_report.md"
    metrics_path.write_text(
        json.dumps(
            {
                "ending_equity": 1060.0,
                "total_return": 0.06,
                "cagr": 1.2,
                "sharpe_ratio": 0.7,
                "max_drawdown": -0.02,
            }
        ),
        encoding="utf-8",
    )
    report_path.write_text("# Report\n", encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "metadata_schema_version": "portfolio_metadata.v1",
                "run_type": "portfolio_run",
                "created_at_utc": "2026-01-01T00:00:00Z",
                "portfolio_id": "qqq_spy_static_60_40",
                "name": "QQQ SPY Static 60/40",
                "alignment_policy": "intersection",
                "rebalance_frequency": "monthly",
                "initial_cash": 1000.0,
                "costs": {
                    "preset": "none",
                    "commission_fixed": 0,
                    "commission_rate": 0,
                    "slippage_bps": 0,
                },
                "environment": {"git_commit": "abc123"},
                "benchmark": {
                    "symbol": "SPY",
                    "total_return": 0.05,
                    "excess_total_return": 0.01,
                },
                "symbols": [
                    {
                        "symbol": "QQQ",
                        "target_weight": 0.6,
                        "aligned_row_count": 10,
                        "dropped_rows": 1,
                        "quality_severity": "none",
                        "file_sha256": "abcdef1234567890",
                    }
                ],
                "artifacts": {
                    "metadata": str(metadata_path),
                    "metrics": str(metrics_path),
                    "report": str(report_path),
                },
                "command": ["quant-lab", "portfolio-run"],
            }
        ),
        encoding="utf-8",
    )
    return metadata_path


if __name__ == "__main__":
    unittest.main()
