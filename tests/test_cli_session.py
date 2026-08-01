import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from quant_lab.cli import main
from quant_lab.research_plan import create_research_plan, save_research_plan
from quant_lab.session_manifest import (
    SessionArtifact,
    SessionCommand,
    create_session_manifest,
    save_session_manifest,
)


class CliSessionTest(unittest.TestCase):
    def test_session_status_prints_compact_resume_orientation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "spy"
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="SPY trend walkthrough",
                hypothesis="Trend may reduce drawdown.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                commands=[
                    SessionCommand(
                        label="Check next step",
                        command=f"quant-lab research-plan next --plan {output_dir / 'research_plan.json'}",
                        status="suggested",
                    )
                ],
                key_artifacts=[
                    SessionArtifact(
                        kind="experiment_conclusion",
                        path=str(output_dir / "experiment_conclusion.md"),
                        role="main",
                    )
                ],
                conclusion_path=output_dir / "experiment_conclusion.md",
                decision_path="experiment:EXP-001",
                current_status="needs_decision",
                outstanding_next_steps=["Record the decision after reading the conclusion."],
                warnings=["Evidence summary may be stale."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["session", "status", "--manifest", manifest_path])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Session: session-001", output)
            self.assertIn("status: needs_decision", output)
            self.assertIn("experiment: EXP-001", output)
            self.assertIn("read_first:", output)
            self.assertIn("experiment_conclusion.md", output)
            self.assertNotIn("\\", output)
            self.assertIn("next: Record the decision", output)
            self.assertIn("warning: Evidence summary may be stale.", output)

    def test_session_replay_plan_prints_pending_commands_without_running_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "spy"
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="SPY trend walkthrough",
                hypothesis="Trend may reduce drawdown.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                commands=[
                    SessionCommand(
                        label="Baseline already done",
                        command=f"quant-lab run --out {output_dir / 'baseline'}",
                        status="executed",
                    ),
                    SessionCommand(
                        label="Check next step",
                        command=f"quant-lab research-plan next --plan {output_dir / 'research_plan.json'}",
                        status="suggested",
                    ),
                ],
                conclusion_path=output_dir / "experiment_conclusion.md",
                current_status="in_progress",
                outstanding_next_steps=["Review the suggested command before running it."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["session", "replay-plan", "--manifest", manifest_path])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("This command does not run them.", output)
            self.assertIn("Check next step", output)
            self.assertIn("quant-lab research-plan next", output)
            self.assertNotIn("Baseline already done", output)
            self.assertNotIn("\\", output)

    def test_session_replay_plan_can_include_executed_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "spy"
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="SPY trend walkthrough",
                hypothesis="Trend may reduce drawdown.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                commands=[
                    SessionCommand(
                        label="Baseline already done",
                        command=f"quant-lab run --out {output_dir / 'baseline'}",
                        status="executed",
                    )
                ],
                current_status="complete",
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["session", "replay-plan", "--manifest", manifest_path, "--include-executed"])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Baseline already done", output)

    def test_session_refresh_writes_manifest_from_research_plan_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            output_dir = temp_path / "research" / "spy"
            index_path = temp_path / "research_index.jsonl"
            experiments_path = temp_path / "experiments.jsonl"
            plan = create_research_plan(
                title="SPY trend walkthrough",
                hypothesis="Trend may reduce drawdown.",
                strategy_path="data/strategies/spy_trend.json",
                data_path="data/cache/SPY.csv",
                symbol="SPY",
                experiment_id="EXP-001",
                experiments_path=experiments_path,
                index_path=index_path,
                output_dir=output_dir,
                created_at_utc="2026-07-25T00:00:00Z",
            )
            plan_path, _ = save_research_plan(plan)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["session", "refresh", "--plan", plan_path])

            manifest_path = output_dir / "session_manifest.json"
            markdown_path = output_dir / "session_manifest.md"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            output = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertTrue(markdown_path.exists())
            self.assertEqual("session_manifest.v1", payload["schema_version"])
            self.assertEqual("session-exp-001", payload["session_id"])
            self.assertEqual("planned", payload["current_status"])
            self.assertEqual(["data/cache/SPY.csv"], payload["data_sources"])
            self.assertEqual(["data/strategies/spy_trend.json"], payload["strategy_paths"])
            self.assertEqual("Recommended next step: baseline", payload["commands"][0]["label"])
            self.assertIn("quant-lab run", payload["commands"][0]["command"])
            self.assertIn(f"Session manifest refreshed: {manifest_path}", output)
            self.assertIn("status: planned", output)

    def test_session_refresh_detects_existing_conclusion_and_next_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            output_dir = temp_path / "research" / "spy"
            index_path = temp_path / "research_index.jsonl"
            experiments_path = temp_path / "experiments.jsonl"
            plan = create_research_plan(
                title="SPY trend walkthrough",
                hypothesis="Trend may reduce drawdown.",
                strategy_path="data/strategies/spy_trend.json",
                data_path="data/cache/SPY.csv",
                symbol="SPY",
                experiment_id="EXP-001",
                experiments_path=experiments_path,
                index_path=index_path,
                output_dir=output_dir,
                created_at_utc="2026-07-25T00:00:00Z",
            )
            plan_path, _ = save_research_plan(plan)
            (output_dir / "evidence_summary.md").write_text("summary\n", encoding="utf-8")
            (output_dir / "experiment_conclusion.md").write_text("# Conclusion\n", encoding="utf-8")
            (output_dir / "experiment_conclusion.json").write_text("{}\n", encoding="utf-8")
            index_path.write_text(
                "\n".join(
                    [
                        json.dumps({"run_type": "run", "experiment_id": "EXP-001"}),
                        json.dumps({"run_type": "sweep_run", "experiment_id": "EXP-001"}),
                        json.dumps({"run_type": "test_selected_run", "experiment_id": "EXP-001"}),
                        json.dumps({"run_type": "cost_sensitivity_run", "experiment_id": "EXP-001"}),
                        json.dumps({"run_type": "date_sensitivity_run", "experiment_id": "EXP-001"}),
                        json.dumps({"run_type": "benchmark_sensitivity_run", "experiment_id": "EXP-001"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(["session", "refresh", "--plan", plan_path])

            payload = json.loads((output_dir / "session_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual("needs_decision", payload["current_status"])
            self.assertEqual(str(output_dir / "experiment_conclusion.md"), payload["conclusion_path"])
            self.assertIn("draft_decision", payload["outstanding_next_steps"][0])
            artifact_paths = [artifact["path"] for artifact in payload["key_artifacts"]]
            self.assertIn(str(output_dir / "experiment_conclusion.md"), artifact_paths)

    def test_session_refresh_warns_about_stale_conclusion_and_missing_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            output_dir = temp_path / "research" / "spy"
            index_path = temp_path / "research_index.jsonl"
            experiments_path = temp_path / "experiments.jsonl"
            missing_metadata_path = output_dir / "baseline" / "run_metadata.json"
            plan = create_research_plan(
                title="SPY trend walkthrough",
                hypothesis="Trend may reduce drawdown.",
                strategy_path="data/strategies/spy_trend.json",
                data_path="data/cache/SPY.csv",
                symbol="SPY",
                experiment_id="EXP-001",
                experiments_path=experiments_path,
                index_path=index_path,
                output_dir=output_dir,
                created_at_utc="2026-07-25T00:00:00Z",
            )
            plan_path, _ = save_research_plan(plan)
            (output_dir / "experiment_conclusion.md").write_text("# Old conclusion\n", encoding="utf-8")
            (output_dir / "experiment_conclusion.json").write_text("{}\n", encoding="utf-8")
            (output_dir / "evidence_summary.md").write_text("newer summary\n", encoding="utf-8")
            os.utime(output_dir / "experiment_conclusion.md", (100, 100))
            os.utime(output_dir / "evidence_summary.md", (200, 200))
            index_path.write_text(
                json.dumps(
                    {
                        "run_type": "run",
                        "experiment_id": "EXP-001",
                        "metadata_path": str(missing_metadata_path),
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(["session", "refresh", "--plan", plan_path])

            payload = json.loads((output_dir / "session_manifest.json").read_text(encoding="utf-8"))
            warnings = "\n".join(payload["warnings"])
            self.assertEqual(exit_code, 0)
            self.assertIn("evidence_summary.md is newer than experiment_conclusion.md", warnings)
            self.assertIn(f"Linked run metadata is missing: {missing_metadata_path}", warnings)


if __name__ == "__main__":
    unittest.main()
