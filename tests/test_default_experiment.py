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
from quant_lab.strategy_templates import build_strategy_template, write_strategy_template  # noqa: E402


class DefaultExperimentWorkflowTests(unittest.TestCase):
    def test_experiment_run_default_writes_main_workflow_artifacts_and_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_path = _write_trending_data(temp_path / "SPY.csv")
            strategy_path = Path(
                write_strategy_template(
                    build_strategy_template(
                        "sma-long-cash",
                        symbol="SPY",
                        length=3,
                        strategy_id="spy_sma_3_long_cash",
                        name="SPY 3-day SMA Long/Cash",
                    ),
                    temp_path / "strategy.json",
                )
            )
            output_dir = temp_path / "research" / "default_spy"
            experiments_path = temp_path / "experiments.jsonl"
            index_path = temp_path / "research_index.jsonl"

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "experiment",
                        "run-default",
                        "--title",
                        "SPY default workflow smoke",
                        "--hypothesis",
                        "A tiny SMA fixture should exercise the default workflow.",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--symbol",
                        "SPY",
                        "--out",
                        str(output_dir),
                        "--experiments-path",
                        str(experiments_path),
                        "--index-path",
                        str(index_path),
                        "--param",
                        "sma_3.inputs.length=2,3",
                        "--train-end",
                        "2026-01-20",
                        "--test-start",
                        "2026-01-21",
                        "--date-window",
                        "2026-01-01,2026-01-20",
                        "--date-window",
                        "2026-01-21,2026-02-15",
                        "--cost-sensitivity-preset",
                        "none",
                        "--cost-sensitivity-preset",
                        "retail-liquid",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "research_plan.json").exists())
            self.assertTrue((output_dir / "baseline" / "run_metadata.json").exists())
            self.assertTrue((output_dir / "baseline" / "run_trust_report.md").exists())
            self.assertTrue((output_dir / "sweep_001" / "summary.csv").exists())
            self.assertTrue((output_dir / "sweep_001" / "sweep_guardrails.md").exists())
            self.assertTrue((output_dir / "train_test_001" / "test_summary" / "summary.csv").exists())
            self.assertTrue((output_dir / "cost_sensitivity_001" / "cost_sensitivity_report.md").exists())
            self.assertTrue((output_dir / "date_sensitivity_001" / "date_sensitivity_report.md").exists())
            self.assertTrue((output_dir / "evidence_summary.md").exists())
            self.assertTrue((output_dir / "experiment_conclusion.md").exists())
            self.assertTrue((output_dir / "default_workflow_summary.md").exists())

            experiment = json.loads(experiments_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(experiment["status"], "completed")
            self.assertIn(experiment["decision_record"]["outcome"], {"continue", "reject"})
            self.assertIn("Default experiment complete: EXP-001", stdout.getvalue())
            self.assertIn("read_first:", stdout.getvalue())


def _write_trending_data(path: Path) -> Path:
    rows = ["date,open,high,low,close,volume"]
    for index, date in enumerate(_business_dates(), start=1):
        close = 100 + index
        rows.append(f"{date},{close - 0.5},{close + 1},{close - 1},{close},1000")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _business_dates() -> list[str]:
    return [
        "2026-01-01",
        "2026-01-02",
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
        "2026-01-08",
        "2026-01-09",
        "2026-01-12",
        "2026-01-13",
        "2026-01-14",
        "2026-01-15",
        "2026-01-16",
        "2026-01-19",
        "2026-01-20",
        "2026-01-21",
        "2026-01-22",
        "2026-01-23",
        "2026-01-26",
        "2026-01-27",
        "2026-01-28",
        "2026-01-29",
        "2026-01-30",
        "2026-02-02",
        "2026-02-03",
        "2026-02-04",
        "2026-02-05",
        "2026-02-06",
        "2026-02-09",
        "2026-02-10",
        "2026-02-11",
        "2026-02-12",
        "2026-02-13",
    ]


if __name__ == "__main__":
    unittest.main()
