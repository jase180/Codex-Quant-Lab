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

    def test_suggest_prefers_next_research_prompt_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            plan_path = output_dir / "research_plan.json"
            conclusion_md = output_dir / "experiment_conclusion.md"
            conclusion_json = output_dir / "experiment_conclusion.json"
            plan_path.write_text("{}\n", encoding="utf-8")
            conclusion_md.write_text("# Experiment Conclusion\n", encoding="utf-8")
            conclusion_json.write_text(
                json.dumps(
                    {
                        "schema_version": "experiment_conclusion.v1",
                        "next_research_prompt": {
                            "known_result": "This branch failed buy-and-hold.",
                            "what_failed": ["Train/test selected run trailed the benchmark."],
                            "constraints": ["Do not widen this SMA branch."],
                            "next_experiment_should": ["Reformulate the hypothesis before more tests."],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Prompt suggest",
                hypothesis="Suggestion should use conclusion prompt.",
                plan_path=plan_path,
                output_dir=output_dir,
                commands=[SessionCommand(label="Recommended next step: draft_decision", command="quant-lab draft-decision --experiment-id EXP-001 --out decision.md")],
                conclusion_path=conclusion_md,
                current_status="needs_decision",
                outstanding_next_steps=["draft_decision: Evidence is ready for a decision."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            recommendation = suggest_from_manifest(manifest_path)

            self.assertEqual("decide", recommendation.recommended_action)
            self.assertIn("Next research prompt says: Reformulate the hypothesis", recommendation.reason)
            self.assertIn("Next research prompt warning: Train/test selected run trailed the benchmark.", recommendation.risks)
            self.assertIn("Do not widen this SMA branch.", recommendation.do_not_repeat)

    def test_suggest_can_recommend_research_design_without_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            plan_path = output_dir / "research_plan.json"
            conclusion_md = output_dir / "experiment_conclusion.md"
            conclusion_json = output_dir / "experiment_conclusion.json"
            plan_path.write_text("{}\n", encoding="utf-8")
            conclusion_md.write_text("# Experiment Conclusion\n", encoding="utf-8")
            conclusion_json.write_text(
                json.dumps(
                    {
                        "schema_version": "experiment_conclusion.v1",
                        "next_research_prompt": {
                            "known_result": "The prior branch failed.",
                            "what_failed": ["Benchmark underperformance was not explained."],
                            "constraints": ["Do not rerun the same strategy unchanged."],
                            "next_experiment_should": ["Design one revised hypothesis with success criteria."],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Research design",
                hypothesis="A rejected branch needs a revised hypothesis.",
                plan_path=plan_path,
                output_dir=output_dir,
                conclusion_path=conclusion_md,
                current_status="in_progress",
                outstanding_next_steps=["reformulate_hypothesis: Choose one bounded next experiment from the rejected conclusion."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            recommendation = suggest_from_manifest(manifest_path)

            self.assertEqual("research_design", recommendation.recommended_action)
            self.assertIsNone(recommendation.next_command)
            self.assertIn("Design one revised hypothesis", recommendation.reason)
            self.assertIn("Do not rerun the same strategy unchanged.", recommendation.do_not_repeat)

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

    def test_suggest_can_use_openai_compatible_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Model suggest",
                hypothesis="Model should return valid schema.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                current_status="in_progress",
                outstanding_next_steps=["unknown_step: Human should inspect this unusual session."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            (output_dir / "research_plan.json").write_text("{}\n", encoding="utf-8")
            manifest_path, _ = save_session_manifest(manifest)

            def fake_post(_url, _payload, _timeout_seconds):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"schema_version":"agent_recommendation.v1",'
                                    '"recommended_action":"needs_review",'
                                    '"reason":"Human should inspect this unusual complete session.",'
                                    '"next_command":null,'
                                    '"risks":["Model saw an unusual state."],'
                                    '"do_not_repeat":["Do not run commands automatically."],'
                                    '"confidence":"low"}'
                                )
                            }
                        }
                    ]
                }

            recommendation = suggest_from_manifest(
                manifest_path,
                provider="openai-compatible",
                base_url="http://local/v1",
                model="fake",
                http_post=fake_post,
            )

            self.assertEqual("needs_review", recommendation.recommended_action)
            self.assertIn("unusual", recommendation.reason)

    def test_suggest_does_not_call_provider_for_complete_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Complete model suggest",
                hypothesis="Complete sessions should stop without model input.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                current_status="complete",
                created_at_utc="2026-07-25T00:00:00Z",
            )
            (output_dir / "research_plan.json").write_text("{}\n", encoding="utf-8")
            manifest_path, _ = save_session_manifest(manifest)

            def fake_post(_url, _payload, _timeout_seconds):
                raise AssertionError("provider should not be called for a complete session")

            recommendation = suggest_from_manifest(
                manifest_path,
                provider="openai-compatible",
                base_url="http://local/v1",
                model="fake",
                http_post=fake_post,
            )

            self.assertEqual("stop", recommendation.recommended_action)
            self.assertEqual("high", recommendation.confidence)

    def test_suggest_falls_back_when_provider_output_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Fallback suggest",
                hypothesis="Invalid model output should fallback.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                commands=[SessionCommand(label="Recommended next step: run_trust", command="quant-lab summarize-run-trust --metadata run.json")],
                current_status="in_progress",
                outstanding_next_steps=["run_trust: Trust report is missing."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            (output_dir / "research_plan.json").write_text("{}\n", encoding="utf-8")
            manifest_path, _ = save_session_manifest(manifest)

            def fake_post(_url, _payload, _timeout_seconds):
                return {"choices": [{"message": {"content": "not json"}}]}

            recommendation = suggest_from_manifest(
                manifest_path,
                provider="openai-compatible",
                base_url="http://local/v1",
                model="fake",
                http_post=fake_post,
            )

            self.assertEqual("run_trust", recommendation.recommended_action)
            self.assertEqual("low", recommendation.confidence)
            self.assertTrue(any("Model provider failed" in risk for risk in recommendation.risks))
