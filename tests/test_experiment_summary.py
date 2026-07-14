from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.experiment_summary import format_experiment_evidence_summary  # noqa: E402
from quant_lab.research_registry import create_experiment_record  # noqa: E402


class ExperimentSummaryTests(unittest.TestCase):
    def test_formats_experiment_with_linked_run_evidence(self) -> None:
        experiment = create_experiment_record(
            experiment_id="EXP-001",
            title="QQQ idea",
            hypothesis="A valid hypothesis.",
            status="running",
            created_at_utc="2026-01-01T00:00:00Z",
        )
        records = [
            {
                "experiment_id": "EXP-001",
                "created_at_utc": "2026-01-02T00:00:00Z",
                "run_type": "sweep_run",
                "run_id": "run_001",
                "total_return": 0.1,
                "excess_total_return": 0.04,
                "sharpe_ratio": 1.2,
                "trade_count": 5,
                "output_dir": "artifacts/run_001",
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
        self.assertIn("Linked index rows: 1", summary)
        self.assertIn("Best total return: sweep_run/run_001 (10.00%)", summary)
        self.assertIn("Best excess return: sweep_run/run_001 (4.00%)", summary)
        self.assertIn("artifacts/run_001", summary)
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
        self.assertIn("No linked runs found", summary)


if __name__ == "__main__":
    unittest.main()
