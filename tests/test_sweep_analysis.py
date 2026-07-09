from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.sweep_analysis import analyze_parameter_stability, format_sweep_analysis_section  # noqa: E402


def _row(run_id: str, total_return: float, params: dict[str, int]) -> dict:
    return {
        "run_id": run_id,
        "params": json.dumps(params, sort_keys=True),
        "total_return": total_return,
        "excess_total_return": total_return - 0.10,
        "sharpe_ratio": 1.0,
        "trade_count": 12,
    }


class SweepAnalysisTests(unittest.TestCase):
    def test_analyze_parameter_stability_marks_supported_grid(self) -> None:
        rows = [
            _row("run_001", 0.20, {"fast": 5, "slow": 50}),
            _row("run_002", 0.19, {"fast": 10, "slow": 50}),
            _row("run_003", 0.18, {"fast": 5, "slow": 100}),
            _row("run_004", 0.05, {"fast": 10, "slow": 100}),
        ]

        assessment = analyze_parameter_stability(rows)

        self.assertEqual(assessment.assessment, "supported")
        self.assertEqual(assessment.neighbor_count, 2)
        self.assertEqual(assessment.strong_neighbor_count, 2)

    def test_analyze_parameter_stability_marks_isolated_winner(self) -> None:
        rows = [
            _row("run_001", 0.50, {"fast": 5, "slow": 50}),
            _row("run_002", 0.10, {"fast": 10, "slow": 50}),
            _row("run_003", 0.00, {"fast": 5, "slow": 100}),
            _row("run_004", 0.09, {"fast": 10, "slow": 100}),
        ]

        assessment = analyze_parameter_stability(rows)

        self.assertEqual(assessment.assessment, "isolated")
        self.assertEqual(assessment.neighbor_count, 2)
        self.assertEqual(assessment.strong_neighbor_count, 0)

    def test_analyze_parameter_stability_marks_half_supported_grid_as_mixed(self) -> None:
        rows = [
            _row("run_001", 0.40, {"fast": 5, "slow": 50}),
            _row("run_002", 0.35, {"fast": 10, "slow": 50}),
            _row("run_003", 0.10, {"fast": 5, "slow": 100}),
        ]

        assessment = analyze_parameter_stability(rows)

        self.assertEqual(assessment.assessment, "mixed")
        self.assertEqual(assessment.neighbor_count, 2)
        self.assertEqual(assessment.strong_neighbor_count, 1)

    def test_format_sweep_analysis_section_includes_top_runs_and_warning_language(self) -> None:
        rows = [
            _row("run_001", 0.50, {"fast": 5, "slow": 50}),
            _row("run_002", 0.10, {"fast": 10, "slow": 50}),
        ]

        section = format_sweep_analysis_section(rows)

        self.assertIn("## Top Runs", section)
        self.assertIn("## Parameter Stability", section)
        self.assertIn("`isolated`", section)
        self.assertIn("deterministic heuristic", section)


if __name__ == "__main__":
    unittest.main()
