from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.evidence_labels import label_portfolio_evidence, label_strategy_evidence  # noqa: E402


class EvidenceLabelTests(unittest.TestCase):
    def test_labels_no_evidence(self) -> None:
        label = label_strategy_evidence([])

        self.assertEqual(label.label, "no_evidence")
        self.assertIn("No linked run evidence exists yet.", label.reasons)

    def test_labels_rejected_when_no_run_beats_benchmark(self) -> None:
        label = label_strategy_evidence(
            [
                {"run_type": "run", "excess_total_return": -0.01, "trade_count": 10},
                {"run_type": "sweep_run", "excess_total_return": 0.0, "trade_count": 10},
            ]
        )

        self.assertEqual(label.label, "rejected")
        self.assertIn("No linked run beat the benchmark on excess return.", label.reasons)

    def test_labels_weak_for_positive_unvalidated_evidence(self) -> None:
        label = label_strategy_evidence(
            [{"run_type": "sweep_run", "excess_total_return": 0.12, "trade_count": 12}]
        )

        self.assertEqual(label.label, "weak")
        self.assertIn("No train/test or walk-forward validation run is linked yet.", label.reasons)

    def test_labels_rejected_when_validation_underperforms(self) -> None:
        label = label_strategy_evidence(
            [
                {"run_type": "sweep_run", "excess_total_return": 0.12, "trade_count": 10},
                {"run_type": "test_selected_run", "excess_total_return": -0.02, "trade_count": 10},
            ]
        )

        self.assertEqual(label.label, "rejected")
        self.assertIn("Validation evidence did not beat the benchmark.", label.reasons)

    def test_labels_mixed_when_validation_is_positive_but_some_evidence_fails(self) -> None:
        label = label_strategy_evidence(
            [
                {"run_type": "sweep_run", "excess_total_return": -0.04, "trade_count": 10},
                {"run_type": "walk_forward_test_run", "excess_total_return": 0.05, "trade_count": 10},
            ]
        )

        self.assertEqual(label.label, "mixed")
        self.assertIn("At least one linked run underperformed the benchmark.", label.reasons)

    def test_labels_weak_when_validation_is_positive_but_trade_counts_are_thin(self) -> None:
        label = label_strategy_evidence(
            [
                {"run_type": "sweep_run", "excess_total_return": 0.08, "trade_count": 2},
                {"run_type": "test_selected_run", "excess_total_return": 0.03, "trade_count": 3},
            ]
        )

        self.assertEqual(label.label, "weak")
        self.assertIn("Validation is positive, but thin trade counts make the evidence fragile.", label.reasons)

    def test_labels_promising_when_validation_and_linked_evidence_are_positive(self) -> None:
        label = label_strategy_evidence(
            [
                {"run_type": "sweep_run", "excess_total_return": 0.08, "trade_count": 8},
                {"run_type": "walk_forward_test_run", "excess_total_return": 0.04, "trade_count": 7},
            ]
        )

        self.assertEqual(label.label, "promising")
        self.assertIn("Validation evidence beat the benchmark.", label.reasons)

    def test_labels_no_portfolio_evidence(self) -> None:
        label = label_portfolio_evidence([])

        self.assertEqual(label.label, "no_evidence")
        self.assertIn("No linked portfolio run evidence exists yet.", label.reasons)

    def test_labels_portfolio_rejected_when_no_allocation_beats_benchmark(self) -> None:
        label = label_portfolio_evidence(
            [
                {"excess_total_return": -0.01, "max_drawdown": -0.1},
                {"excess_total_return": 0.0, "max_drawdown": -0.1},
            ]
        )

        self.assertEqual(label.label, "rejected")
        self.assertIn("No linked portfolio run beat the benchmark on excess return.", label.reasons)

    def test_labels_portfolio_mixed_when_some_allocation_underperforms(self) -> None:
        label = label_portfolio_evidence(
            [
                {"excess_total_return": 0.03, "max_drawdown": -0.1},
                {"excess_total_return": -0.01, "max_drawdown": -0.24},
            ]
        )

        self.assertEqual(label.label, "mixed")
        self.assertIn("1 linked portfolio run(s) underperformed the benchmark.", label.reasons)

    def test_labels_portfolio_promising_when_clean_and_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "portfolio_a"
            run_dir.mkdir()
            (run_dir / "portfolio_data_trust_report.md").write_text("# Trust\n", encoding="utf-8")

            label = label_portfolio_evidence(
                [
                    {
                        "excess_total_return": 0.03,
                        "max_drawdown": -0.1,
                        "metadata_path": str(run_dir / "portfolio_metadata.json"),
                    },
                    {
                        "excess_total_return": 0.02,
                        "max_drawdown": -0.12,
                        "metadata_path": str(Path(temp_dir) / "portfolio_b" / "portfolio_metadata.json"),
                    },
                ]
            )

        self.assertEqual(label.label, "promising")
        self.assertIn("Multiple linked portfolio runs beat the benchmark.", label.reasons)


if __name__ == "__main__":
    unittest.main()
