import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.agent_recommendation import (
    AGENT_RECOMMENDATION_SCHEMA_VERSION,
    agent_recommendation_to_json,
    create_agent_recommendation,
    format_agent_recommendation_markdown,
    load_agent_recommendation,
    save_agent_recommendation,
)
from quant_lab.cli import main


class AgentRecommendationTest(unittest.TestCase):
    def test_create_recommendation_normalizes_and_validates(self) -> None:
        recommendation = create_agent_recommendation(
            recommended_action=" run_trust ",
            reason=" A baseline exists, but trust is missing. ",
            next_command="quant-lab summarize-run-trust --metadata artifacts/run/run_metadata.json",
            risks=[" Weak sample. ", "Weak sample."],
            do_not_repeat=["Sweep before trust."],
            confidence="MEDIUM",
            created_at_utc="2026-07-25T00:00:00Z",
        )

        self.assertEqual(AGENT_RECOMMENDATION_SCHEMA_VERSION, recommendation.schema_version)
        self.assertEqual("run_trust", recommendation.recommended_action)
        self.assertEqual("medium", recommendation.confidence)
        self.assertEqual(["Weak sample."], recommendation.risks)

    def test_command_is_required_for_runnable_actions(self) -> None:
        with self.assertRaisesRegex(ValueError, "next_command is required"):
            create_agent_recommendation(
                recommended_action="sweep",
                reason="A trust report exists; sweep is next.",
            )

    def test_stop_action_does_not_require_command(self) -> None:
        recommendation = create_agent_recommendation(
            recommended_action="stop",
            reason="The experiment already has a recorded decision.",
            confidence="high",
        )

        self.assertIsNone(recommendation.next_command)

    def test_rejects_unknown_action_confidence_and_non_quant_lab_command(self) -> None:
        with self.assertRaisesRegex(ValueError, "recommended_action"):
            create_agent_recommendation(
                recommended_action="rewrite_code",
                reason="Bad idea.",
                next_command="quant-lab run",
            )
        with self.assertRaisesRegex(ValueError, "confidence"):
            create_agent_recommendation(
                recommended_action="stop",
                reason="No action needed.",
                confidence="certain",
            )
        with self.assertRaisesRegex(ValueError, "next_command"):
            create_agent_recommendation(
                recommended_action="run_trust",
                reason="Need trust report.",
                next_command="python script.py",
            )

    def test_rejects_known_action_command_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match recommended_action"):
            create_agent_recommendation(
                recommended_action="summarize",
                reason="Need trust report.",
                next_command="quant-lab summarize-run-trust --metadata artifacts/run/run_metadata.json",
            )

    def test_load_recommendation_rejects_unknown_fields_and_missing_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agent_recommendation.json"
            payload = {
                "schema_version": "agent_recommendation.v1",
                "recommended_action": "stop",
                "reason": "Done.",
                "risks": [],
                "do_not_repeat": [],
                "confidence": "high",
                "extra": "nope",
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unknown agent recommendation"):
                load_agent_recommendation(path)

            payload.pop("extra")
            payload.pop("risks")
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing agent recommendation"):
                load_agent_recommendation(path)

    def test_save_and_format_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            recommendation = create_agent_recommendation(
                recommended_action="run_trust",
                reason="A baseline exists; verify data before widening.",
                next_command="quant-lab summarize-run-trust --metadata artifacts/run/run_metadata.json",
                risks=["Baseline sample is tiny."],
                do_not_repeat=["Do not sweep before trust."],
                confidence="medium",
                created_at_utc="2026-07-25T00:00:00Z",
            )

            json_path, markdown_path = save_agent_recommendation(recommendation, tmpdir)

            self.assertEqual("agent_recommendation.v1", json.loads(Path(json_path).read_text(encoding="utf-8"))["schema_version"])
            self.assertIn("bounded advisor output", Path(markdown_path).read_text(encoding="utf-8"))
            self.assertIn("## Next Command", format_agent_recommendation_markdown(recommendation))
            self.assertEqual("agent_recommendation.v1", json.loads(agent_recommendation_to_json(recommendation))["schema_version"])

    def test_cli_validate_recommendation_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agent_recommendation.json"
            recommendation = create_agent_recommendation(
                recommended_action="run_trust",
                reason="Trust report is missing.",
                next_command="quant-lab summarize-run-trust --metadata artifacts/run/run_metadata.json",
                confidence="medium",
            )
            path.write_text(json.dumps(recommendation.to_dict()), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["agent", "validate-recommendation", "--recommendation", str(path)])

            output = stdout.getvalue()
            self.assertEqual(0, exit_code)
            self.assertIn("Agent recommendation: valid", output)
            self.assertIn("action: run_trust", output)

    def test_cli_validate_recommendation_can_write_normalized_artifacts_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "input.json"
            out_dir = root / "out"
            recommendation = create_agent_recommendation(
                recommended_action="stop",
                reason="Decision already exists.",
                confidence="high",
            )
            path.write_text(json.dumps(recommendation.to_dict()), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "agent",
                        "validate-recommendation",
                        "--recommendation",
                        str(path),
                        "--out-dir",
                        str(out_dir),
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code)
            self.assertTrue((out_dir / "agent_recommendation.json").exists())
            self.assertTrue((out_dir / "agent_recommendation.md").exists())
            self.assertEqual("stop", payload["recommended_action"])
