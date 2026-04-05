from __future__ import annotations

import json
import math
import statistics
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from metrics_reporting import (  # noqa: E402
    build_equity_curve,
    build_markdown_report,
    build_metrics_summary,
    calculate_cagr,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_total_return,
    daily_returns_from_equity,
    save_run_artifacts,
    validate_equity_curve,
)


class MetricsReportingTests(unittest.TestCase):
    def test_daily_returns_from_equity(self) -> None:
        returns = daily_returns_from_equity([100.0, 110.0, 99.0])
        self.assertAlmostEqual(returns[0], 0.1)
        self.assertAlmostEqual(returns[1], -0.1)

    def test_total_return(self) -> None:
        total_return = calculate_total_return([100.0, 110.0, 105.0, 120.0])
        self.assertAlmostEqual(total_return, 0.2)

    def test_max_drawdown(self) -> None:
        max_drawdown = calculate_max_drawdown([100.0, 110.0, 105.0, 120.0])
        self.assertAlmostEqual(max_drawdown, (105.0 / 110.0) - 1.0)

    def test_cagr(self) -> None:
        equity_values = [100.0 + day for day in range(253)]
        expected = (equity_values[-1] / equity_values[0]) ** (252 / 252) - 1.0
        self.assertAlmostEqual(calculate_cagr(equity_values), expected)

    def test_sharpe_ratio(self) -> None:
        equity_values = [100.0, 110.0, 100.0, 120.0]
        daily_returns = [(110.0 / 100.0) - 1.0, (100.0 / 110.0) - 1.0, (120.0 / 100.0) - 1.0]
        expected = (statistics.mean(daily_returns) / statistics.stdev(daily_returns)) * math.sqrt(252)
        self.assertAlmostEqual(calculate_sharpe_ratio(equity_values), expected)

    def test_duplicate_dates_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate date detected"):
            build_equity_curve(
                dates=["2026-03-30", "2026-03-30"],
                equity_values=[100000.0, 101000.0],
            )

    def test_unordered_dates_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            build_equity_curve(
                dates=["2026-03-31", "2026-03-30"],
                equity_values=[101000.0, 100000.0],
            )

    def test_validate_equity_curve_rejects_duplicate_dates_in_summary_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate date detected"):
            validate_equity_curve(
                [
                    {"date": "2026-03-30", "equity": 100000.0},
                    {"date": "2026-03-30", "equity": 101000.0},
                ]
            )

    def test_short_sample_summary_uses_explicit_caveats(self) -> None:
        equity_curve = build_equity_curve(
            dates=["2026-03-30", "2026-03-31"],
            equity_values=[100000.0, 101000.0],
        )

        metrics = build_metrics_summary(equity_curve)
        report = build_markdown_report("Short Sample", metrics, equity_curve)

        self.assertIsNone(metrics.sharpe_ratio)
        self.assertIsNotNone(metrics.cagr)
        self.assertTrue(any("Sharpe ratio omitted" in caveat for caveat in metrics.caveats))
        self.assertIn("fewer than 252 trading days", report)
        self.assertIn("| Sharpe Ratio | N/A |", report)

    def test_sharpe_requires_three_equity_observations(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least 3 equity observations"):
            calculate_sharpe_ratio([100.0, 101.0])

    def test_build_metrics_summary_and_report(self) -> None:
        equity_curve = build_equity_curve(
            dates=["2026-03-30", "2026-03-31", "2026-04-01", "2026-04-02"],
            equity_values=[100000.0, 101500.0, 100750.0, 103000.0],
        )
        metrics = build_metrics_summary(equity_curve)
        report = build_markdown_report("Sample Run", metrics, equity_curve)

        self.assertEqual(metrics.starting_equity, 100000.0)
        self.assertEqual(metrics.ending_equity, 103000.0)
        self.assertIn("# Sample Run", report)
        self.assertIn("| Total Return |", report)
        self.assertIn("| 2026-04-02 | 103000.00 |", report)
        self.assertIn("CAGR is annualized from fewer than 252 trading days", report)

    def test_save_run_artifacts(self) -> None:
        equity_curve = build_equity_curve(
            dates=["2026-03-30", "2026-03-31"],
            equity_values=[100000.0, 101000.0],
        )
        metrics = build_metrics_summary(equity_curve)
        report = build_markdown_report("Artifact Run", metrics, equity_curve)

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_paths = save_run_artifacts(temp_dir, metrics, equity_curve, report)
            metrics_payload = json.loads(Path(artifact_paths["metrics"]).read_text(encoding="utf-8"))
            saved_report = Path(artifact_paths["report"]).read_text(encoding="utf-8")
            saved_curve = Path(artifact_paths["equity_curve"]).read_text(encoding="utf-8")

        self.assertEqual(metrics_payload["ending_equity"], 101000.0)
        self.assertIn("# Artifact Run", saved_report)
        self.assertIn("2026-03-31,101000.0", saved_curve)

    def test_artifacts_are_deterministic_for_same_input(self) -> None:
        equity_curve = build_equity_curve(
            dates=["2026-03-30", "2026-03-31", "2026-04-01"],
            equity_values=[100000.0, 101000.0, 102500.0],
        )
        metrics = build_metrics_summary(equity_curve)
        report = build_markdown_report("Deterministic Run", metrics, equity_curve)

        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first_paths = save_run_artifacts(first_dir, metrics, equity_curve, report)
            second_paths = save_run_artifacts(second_dir, metrics, equity_curve, report)

            first_metrics = Path(first_paths["metrics"]).read_text(encoding="utf-8")
            second_metrics = Path(second_paths["metrics"]).read_text(encoding="utf-8")
            first_curve = Path(first_paths["equity_curve"]).read_text(encoding="utf-8")
            second_curve = Path(second_paths["equity_curve"]).read_text(encoding="utf-8")
            first_report = Path(first_paths["report"]).read_text(encoding="utf-8")
            second_report = Path(second_paths["report"]).read_text(encoding="utf-8")

        self.assertEqual(first_metrics, second_metrics)
        self.assertEqual(first_curve, second_curve)
        self.assertEqual(first_report, second_report)

    def test_known_fixture_is_deterministic(self) -> None:
        equity_curve = build_equity_curve(
            dates=["2026-03-30", "2026-03-31", "2026-04-01", "2026-04-02"],
            equity_values=[100000.0, 101500.0, 100750.0, 103000.0],
        )

        metrics = build_metrics_summary(equity_curve)
        daily_returns = [0.015, (100750.0 / 101500.0) - 1.0, (103000.0 / 100750.0) - 1.0]
        expected_sharpe = (statistics.mean(daily_returns) / statistics.stdev(daily_returns)) * math.sqrt(252)

        self.assertAlmostEqual(metrics.total_return, 0.03)
        self.assertAlmostEqual(metrics.max_drawdown, (100750.0 / 101500.0) - 1.0)
        self.assertAlmostEqual(metrics.cagr, (103000.0 / 100000.0) ** (252 / 3) - 1.0)
        self.assertAlmostEqual(metrics.sharpe_ratio, expected_sharpe)


if __name__ == "__main__":
    unittest.main()
