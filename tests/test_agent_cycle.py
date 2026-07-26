import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.agent_cycle import run_agent_cycle
from quant_lab.cli import main
from quant_lab.session_manifest import SessionCommand, create_session_manifest, save_session_manifest


def _manifest_fixture(tmpdir: str) -> str:
    output_dir = Path(tmpdir)
    plan_path = output_dir / "research_plan.json"
    plan_path.write_text("{}\n", encoding="utf-8")
    manifest = create_session_manifest(
        session_id="session-001",
        experiment_id="EXP-001",
        title="Cycle test",
        hypothesis="Cycle should propose but not execute the next command.",
        plan_path=plan_path,
        output_dir=output_dir,
        commands=[
            SessionCommand(
                label="Recommended next step: run_trust",
                command="quant-lab summarize-run-trust --metadata artifacts\\run\\run_metadata.json",
            )
        ],
        current_status="in_progress",
        outstanding_next_steps=["run_trust: A baseline exists; write a data trust report."],
        warnings=["Baseline run metadata exists, but trust report is missing."],
        created_at_utc="2026-07-25T00:00:00Z",
    )
    manifest_path, _ = save_session_manifest(manifest)
    return manifest_path


class AgentCycleTest(unittest.TestCase):
    def test_cycle_dry_run_writes_context_recommendation_and_cycle_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = _manifest_fixture(tmpdir)

            result = run_agent_cycle(manifest_path, dry_run=True)

            output_dir = Path(tmpdir) / "agent_cycle"
            self.assertEqual("agent_cycle.v1", result.schema_version)
            self.assertTrue(result.dry_run)
            self.assertEqual("run_trust", result.recommended_action)
            self.assertIn("summarize-run-trust", result.proposed_command)
            self.assertTrue((output_dir / "agent_context_bundle.json").exists())
            self.assertTrue((output_dir / "agent_recommendation.json").exists())
            self.assertTrue((output_dir / "agent_cycle.json").exists())
            self.assertTrue((output_dir / "agent_cycle.md").exists())
            payload = json.loads((output_dir / "agent_cycle.json").read_text(encoding="utf-8"))
            self.assertEqual((output_dir / "agent_cycle.json").as_posix(), payload["cycle_json_path"])
            self.assertEqual((output_dir / "agent_cycle.md").as_posix(), payload["cycle_markdown_path"])

    def test_cycle_rejects_non_dry_run_for_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = _manifest_fixture(tmpdir)

            with self.assertRaisesRegex(ValueError, "dry-run only"):
                run_agent_cycle(manifest_path, dry_run=False)

    def test_cli_cycle_json_output_is_pure_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = _manifest_fixture(tmpdir)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["agent", "cycle", "--manifest", manifest_path, "--dry-run", "--json"])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual("agent_cycle.v1", payload["schema_version"])
            self.assertEqual("run_trust", payload["recommended_action"])
            self.assertTrue(payload["dry_run"])

    def test_cli_cycle_without_dry_run_returns_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = _manifest_fixture(tmpdir)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["agent", "cycle", "--manifest", manifest_path])

            self.assertEqual(2, exit_code)
            self.assertIn("dry-run only", stdout.getvalue())
