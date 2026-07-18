from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.experiment_summary import format_experiment_decision_draft, format_experiment_evidence_summary  # noqa: E402
from quant_lab.research_registry import create_experiment_record, link_runs_to_experiment  # noqa: E402


class ExperimentSummaryTests(unittest.TestCase):
    def test_formats_experiment_with_linked_run_evidence(self) -> None:
        experiment = link_runs_to_experiment(
            create_experiment_record(
                experiment_id="EXP-001",
                title="QQQ idea",
                hypothesis="A valid hypothesis.",
                status="running",
                created_at_utc="2026-01-01T00:00:00Z",
            ),
            ["artifacts/run_001/run_metadata.json", "artifacts/manual/run_metadata.json"],
        )
        records = [
            {
                "experiment_id": "EXP-001",
                "created_at_utc": "2026-01-02T00:00:00Z",
                "run_type": "sweep_run",
                "run_id": "run_001",
                "metadata_path": "artifacts/run_001/run_metadata.json",
                "total_return": 0.1,
                "excess_total_return": 0.04,
                "max_drawdown": -0.08,
                "sharpe_ratio": 1.2,
                "trade_count": 5,
                "output_dir": "artifacts/run_001",
            },
            {
                "experiment_id": None,
                "created_at_utc": "2026-01-04T00:00:00Z",
                "run_type": "run",
                "run_id": None,
                "metadata_path": "artifacts/manual/run_metadata.json",
                "total_return": -0.02,
                "excess_total_return": -0.12,
                "max_drawdown": -0.2,
                "sharpe_ratio": -0.4,
                "trade_count": 2,
                "output_dir": "artifacts/manual",
            },
            {
                "experiment_id": "EXP-999",
                "created_at_utc": "2026-01-03T00:00:00Z",
                "run_type": "run",
                "run_id": None,
                "total_return": 0.9,
                "excess_total_return": 0.8,
            },
        ]

        summary = format_experiment_evidence_summary(experiment, records)

        self.assertIn("Experiment Evidence Summary", summary)
        self.assertIn("Registry linked metadata paths: 2", summary)
        self.assertIn("Linked index rows: 2", summary)
        self.assertIn("Linked paths missing from index: 0", summary)
        self.assertIn("Evidence Label", summary)
        self.assertIn("Label: weak", summary)
        self.assertIn("No train/test or walk-forward validation run is linked yet.", summary)
        self.assertIn("Supporting Evidence", summary)
        self.assertIn("Contradicting Evidence", summary)
        self.assertIn("sweep_run/run_001: excess 4.00%", summary)
        self.assertIn("run/-: excess -12.00%", summary)
        self.assertIn("Run Type Breakdown", summary)
        self.assertIn("Top Evidence By Excess Return", summary)
        self.assertIn("Weakest Evidence By Excess Return", summary)
        self.assertIn("Strongest excess evidence: sweep_run/run_001 (4.00%)", summary)
        self.assertIn("Weakest excess evidence: run/- (-12.00%)", summary)
        self.assertIn("Worst drawdown: run/- (-20.00%)", summary)
        self.assertIn("Best total return: sweep_run/run_001 (10.00%)", summary)
        self.assertIn("Best excess return: sweep_run/run_001 (4.00%)", summary)
        self.assertIn("artifacts/run_001", summary)
        self.assertIn("artifacts/manual", summary)
        self.assertNotIn("EXP-999", summary)

    def test_formats_experiment_without_evidence(self) -> None:
        experiment = create_experiment_record(
            experiment_id="EXP-001",
            title="QQQ idea",
            hypothesis="A valid hypothesis.",
            created_at_utc="2026-01-01T00:00:00Z",
        )

        summary = format_experiment_evidence_summary(experiment, [])

        self.assertIn("Linked index rows: 0", summary)
        self.assertIn("Label: no_evidence", summary)
        self.assertIn("No linked run evidence exists yet.", summary)
        self.assertIn("Supporting Evidence", summary)
        self.assertIn("Contradicting Evidence", summary)
        self.assertIn("No linked runs found", summary)

    def test_formats_experiment_with_promising_validation_label(self) -> None:
        experiment = create_experiment_record(
            experiment_id="EXP-001",
            title="QQQ idea",
            hypothesis="A valid hypothesis.",
            created_at_utc="2026-01-01T00:00:00Z",
        )
        records = [
            {
                "experiment_id": "EXP-001",
                "created_at_utc": "2026-01-02T00:00:00Z",
                "run_type": "sweep_run",
                "run_id": "run_004",
                "metadata_path": "artifacts/sweep/run_004/run_metadata.json",
                "total_return": 0.1,
                "excess_total_return": 0.08,
                "trade_count": 8,
            },
            {
                "experiment_id": "EXP-001",
                "created_at_utc": "2026-01-03T00:00:00Z",
                "run_type": "walk_forward_test_run",
                "run_id": "window_001_test_selected",
                "metadata_path": "artifacts/walk_forward/window_001/test_selected/run_metadata.json",
                "total_return": 0.06,
                "excess_total_return": 0.04,
                "trade_count": 7,
            },
        ]

        summary = format_experiment_evidence_summary(experiment, records)

        self.assertIn("Label: promising", summary)
        self.assertIn("Validation evidence beat the benchmark.", summary)
        self.assertIn("walk_forward_test_run/window_001_test_selected: excess 4.00%", summary)

    def test_drafts_continue_decision_without_validation_evidence(self) -> None:
        experiment = create_experiment_record(
            experiment_id="EXP-001",
            title="QQQ idea",
            hypothesis="A valid hypothesis.",
            created_at_utc="2026-01-01T00:00:00Z",
        )
        records = [
            {
                "experiment_id": "EXP-001",
                "created_at_utc": "2026-01-02T00:00:00Z",
                "run_type": "sweep_run",
                "run_id": "run_001",
                "metadata_path": "artifacts/sweep/run_001/run_metadata.json",
                "excess_total_return": 0.12,
            }
        ]

        draft = format_experiment_decision_draft(experiment, records)

        self.assertIn("Experiment Decision Draft", draft)
        self.assertIn("Suggested outcome: continue", draft)
        self.assertIn("no train/test or walk-forward validation run is linked yet", draft)
        self.assertIn("Evidence Label", draft)
        self.assertIn("Label: weak", draft)
        self.assertIn("Uncertainty", draft)
        self.assertIn("There is no out-of-sample validation linked to this experiment.", draft)
        self.assertIn("What Would Change My Mind", draft)
        self.assertIn("Add a train/test or walk-forward validation run that also beats the benchmark.", draft)
        self.assertIn("--supporting-run \"artifacts/sweep/run_001/run_metadata.json\"", draft)

    def test_drafts_reject_when_validation_underperforms(self) -> None:
        experiment = create_experiment_record(
            experiment_id="EXP-001",
            title="QQQ idea",
            hypothesis="A valid hypothesis.",
            created_at_utc="2026-01-01T00:00:00Z",
        )
        records = [
            {
                "experiment_id": "EXP-001",
                "created_at_utc": "2026-01-02T00:00:00Z",
                "run_type": "sweep_run",
                "run_id": "run_004",
                "metadata_path": "artifacts/sweep/run_004/run_metadata.json",
                "excess_total_return": 0.15,
            },
            {
                "experiment_id": "EXP-001",
                "created_at_utc": "2026-01-03T00:00:00Z",
                "run_type": "test_selected_run",
                "run_id": "test_selected",
                "metadata_path": "artifacts/test/run_metadata.json",
                "excess_total_return": -0.03,
            },
        ]

        draft = format_experiment_decision_draft(experiment, records)

        self.assertIn("Suggested outcome: reject", draft)
        self.assertIn("Validation evidence did not beat the benchmark", draft)
        self.assertIn("Label: rejected", draft)
        self.assertIn("A better sweep result alone should not override failed validation evidence.", draft)
        self.assertIn("Do not keep widening this branch just because one exploratory run looked good.", draft)
        self.assertIn("--contradicting-run \"artifacts/test/run_metadata.json\"", draft)

    def test_drafts_accept_when_validation_and_all_linked_evidence_are_positive(self) -> None:
        experiment = create_experiment_record(
            experiment_id="EXP-001",
            title="QQQ idea",
            hypothesis="A valid hypothesis.",
            created_at_utc="2026-01-01T00:00:00Z",
        )
        records = [
            {
                "experiment_id": "EXP-001",
                "created_at_utc": "2026-01-02T00:00:00Z",
                "run_type": "sweep_run",
                "run_id": "run_004",
                "metadata_path": "artifacts/sweep/run_004/run_metadata.json",
                "excess_total_return": 0.08,
                "trade_count": 8,
            },
            {
                "experiment_id": "EXP-001",
                "created_at_utc": "2026-01-03T00:00:00Z",
                "run_type": "walk_forward_test_run",
                "run_id": "window_001_test_selected",
                "metadata_path": "artifacts/walk_forward/window_001/test_selected/run_metadata.json",
                "excess_total_return": 0.04,
                "trade_count": 7,
            },
        ]

        draft = format_experiment_decision_draft(experiment, records)

        self.assertIn("Suggested outcome: accept", draft)
        self.assertIn("Linked evidence and validation evidence both show positive excess return", draft)
        self.assertIn("Label: promising", draft)
        self.assertIn("Promising is not proof.", draft)
        self.assertIn("Run robustness checks across dates, costs, and symbols.", draft)
        self.assertIn("--next-action \"Promote this idea to stricter validation or paper-trading research.\"", draft)


if __name__ == "__main__":
    unittest.main()
