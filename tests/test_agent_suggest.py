import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.agent_suggest import suggest_from_manifest
from quant_lab.cli import main
from quant_lab.session_manifest import SessionCommand, create_session_manifest, save_session_manifest


class AgentSuggestTest(unittest.TestCase):
    def test_suggest_maps_manifest_next_step_to_valid_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Smoke workflow",
                hypothesis="Smoke should recommend trust.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                commands=[
                    SessionCommand(
                        label="Recommended next step: run_trust",
                        command="quant-lab summarize-run-trust --metadata artifacts\\run\\run_metadata.json",
                    )
                ],
                current_status="in_progress",
                outstanding_next_steps=["run_trust: A baseline exists; write a data trust report."],
                warnings=["Baseline run metadata exists, but run_trust_report.md is missing beside artifacts\\run\\run_metadata.json."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            recommendation = suggest_from_manifest(manifest_path)

            self.assertEqual("run_trust", recommendation.recommended_action)
            self.assertIn("baseline exists", recommendation.reason)
            self.assertEqual("quant-lab summarize-run-trust --metadata artifacts/run/run_metadata.json", recommendation.next_command)
            self.assertIn("artifacts/run/run_metadata.json", recommendation.risks[0])

    def test_suggest_returns_stop_for_complete_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Done",
                hypothesis="A decision exists.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                current_status="complete",
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            recommendation = suggest_from_manifest(manifest_path)

            self.assertEqual("stop", recommendation.recommended_action)
            self.assertIsNone(recommendation.next_command)
            self.assertEqual("high", recommendation.confidence)

    def test_suggest_returns_needs_review_when_next_step_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Unknown",
                hypothesis="Unknown step should stop automation.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                current_status="in_progress",
                outstanding_next_steps=["invent_strategy: Try a new thing."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            recommendation = suggest_from_manifest(manifest_path)

            self.assertEqual("needs_review", recommendation.recommended_action)
            self.assertIsNone(recommendation.next_command)
            self.assertEqual("low", recommendation.confidence)

    def test_cli_agent_suggest_writes_artifacts_and_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="CLI suggest",
                hypothesis="CLI should write recommendation.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                commands=[SessionCommand(label="Recommended next step: sweep", command="quant-lab sweep --strategy s --data d --out o")],
                current_status="in_progress",
                outstanding_next_steps=["sweep: A trust report exists; run one parameter sweep."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["agent", "suggest", "--manifest", manifest_path])

            output = stdout.getvalue()
            self.assertEqual(0, exit_code)
            self.assertTrue((output_dir / "agent_recommendation.json").exists())
            self.assertTrue((output_dir / "agent_recommendation.md").exists())
            self.assertIn("action: sweep", output)
            self.assertIn("next_command:", output)

    def test_cli_agent_suggest_json_output_is_pure_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="CLI JSON suggest",
                hypothesis="CLI JSON should be parseable.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                current_status="complete",
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["agent", "suggest", "--manifest", manifest_path, "--json"])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual("agent_recommendation.v1", payload["schema_version"])
            self.assertEqual("stop", payload["recommended_action"])
