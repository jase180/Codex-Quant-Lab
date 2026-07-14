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
from cli_fixtures import _write_index_fixture  # noqa: E402


class CliExperimentTests(unittest.TestCase):
    def test_new_experiment_writes_record_and_show_prints_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "experiments.jsonl"

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "new-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--title",
                        "QQQ SMA sweep",
                        "--hypothesis",
                        "Shorter moving averages may improve returns.",
                        "--tag",
                        "QQQ,sma",
                        "--strategy",
                        "data/strategies/sma.json",
                        "--data",
                        "data/cache/qqq.csv",
                        "--notes",
                        "Start broad.",
                    ]
                )

            payload = json.loads(registry_path.read_text(encoding="utf-8").strip())
            self.assertEqual(exit_code, 0)
            self.assertIn("Experiment created: EXP-001", stdout.getvalue())
            self.assertEqual(payload["experiment_schema_version"], "experiment.v1")
            self.assertEqual(payload["experiment_id"], "EXP-001")
            self.assertEqual(payload["status"], "planned")
            self.assertEqual(payload["tags"], ["qqq", "sma"])
            self.assertEqual(payload["linked_runs"], [])
            self.assertIsNone(payload["decision"])

            with contextlib.redirect_stdout(io.StringIO()) as show_stdout:
                show_exit_code = main(
                    [
                        "show-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--experiment-id",
                        "EXP-001",
                    ]
                )

            output = show_stdout.getvalue()
            self.assertEqual(show_exit_code, 0)
            self.assertIn("Experiment", output)
            self.assertIn("QQQ SMA sweep", output)
            self.assertIn("Shorter moving averages", output)
            self.assertIn("data/strategies/sma.json", output)

    def test_list_experiments_filters_and_prints_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "experiments.jsonl"
            for title, status, tag in [
                ("Trend idea", "planned", "trend"),
                ("Mean reversion idea", "running", "mean-reversion"),
            ]:
                with contextlib.redirect_stdout(io.StringIO()):
                    main(
                        [
                            "new-experiment",
                            "--experiments-path",
                            str(registry_path),
                            "--title",
                            title,
                            "--hypothesis",
                            f"Hypothesis for {title}.",
                            "--status",
                            status,
                            "--tag",
                            tag,
                        ]
                    )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "list-experiments",
                        "--experiments-path",
                        str(registry_path),
                        "--status",
                        "running",
                        "--csv",
                    ]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("id,status,created,title,tags", output)
            self.assertIn("EXP-002,running", output)
            self.assertIn("Mean reversion idea", output)
            self.assertNotIn("Trend idea", output)

    def test_list_experiments_handles_empty_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "missing.jsonl"

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["list-experiments", "--experiments-path", str(registry_path)])

            self.assertEqual(exit_code, 0)
            self.assertIn("No experiments found", stdout.getvalue())

    def test_update_experiment_changes_status_decision_notes_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "experiments.jsonl"
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "new-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--title",
                        "QQQ idea",
                        "--hypothesis",
                        "A valid hypothesis.",
                        "--tag",
                        "qqq",
                    ]
                )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "update-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--experiment-id",
                        "EXP-001",
                        "--status",
                        "completed",
                        "--decision",
                        "Reject until a stronger benchmark comparison appears.",
                        "--notes",
                        "Too few trades.",
                        "--tag",
                        "rejected",
                    ]
                )

            payload = json.loads(registry_path.read_text(encoding="utf-8").strip())
            self.assertEqual(exit_code, 0)
            self.assertIn("Experiment updated: EXP-001", stdout.getvalue())
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["decision"], "Reject until a stronger benchmark comparison appears.")
            self.assertEqual(payload["notes"], "Too few trades.")
            self.assertEqual(payload["tags"], ["qqq", "rejected"])

            with contextlib.redirect_stdout(io.StringIO()) as show_stdout:
                main(
                    [
                        "show-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--experiment-id",
                        "EXP-001",
                    ]
                )

            output = show_stdout.getvalue()
            self.assertIn("Status: completed", output)
            self.assertIn("Reject until", output)
            self.assertIn("Too few trades.", output)

    def test_update_experiment_rejects_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "experiments.jsonl"
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "new-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--title",
                        "QQQ idea",
                        "--hypothesis",
                        "A valid hypothesis.",
                    ]
                )

            with self.assertRaisesRegex(ValueError, "requires at least one"):
                main(
                    [
                        "update-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--experiment-id",
                        "EXP-001",
                    ]
                )

    def test_summarize_experiment_prints_linked_run_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            registry_path = temp_path / "experiments.jsonl"
            index_path = temp_path / "research_index.jsonl"
            _write_index_fixture(index_path)
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "new-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--experiment-id",
                        "EXP-002",
                        "--title",
                        "QQQ idea",
                        "--hypothesis",
                        "A valid hypothesis.",
                    ]
                )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "summarize-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--index-path",
                        str(index_path),
                        "--experiment-id",
                        "EXP-002",
                    ]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Experiment Evidence Summary", output)
            self.assertIn("Linked index rows: 1", output)
            self.assertIn("fast_strategy", output)
            self.assertIn("Best excess return", output)


if __name__ == "__main__":
    unittest.main()
