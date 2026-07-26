import tempfile
import unittest
from pathlib import Path

from quant_lab.agent_context import build_agent_context
from quant_lab.agent_provider import build_agent_prompt, suggest_with_openai_compatible_provider
from quant_lab.session_manifest import SessionCommand, create_session_manifest, save_session_manifest


def _context_fixture(tmpdir: str):
    output_dir = Path(tmpdir)
    plan_path = output_dir / "research_plan.json"
    plan_path.write_text("{}\n", encoding="utf-8")
    manifest = create_session_manifest(
        session_id="session-001",
        experiment_id="EXP-001",
        title="Provider test",
        hypothesis="Provider should return strict JSON.",
        plan_path=plan_path,
        output_dir=output_dir,
        commands=[SessionCommand(label="Recommended next step: run_trust", command="quant-lab summarize-run-trust --metadata run.json")],
        current_status="in_progress",
        outstanding_next_steps=["run_trust: Trust report is missing."],
        created_at_utc="2026-07-25T00:00:00Z",
    )
    manifest_path, _ = save_session_manifest(manifest)
    return build_agent_context(manifest_path)


class AgentProviderTest(unittest.TestCase):
    def test_openai_compatible_provider_returns_valid_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _context_fixture(tmpdir)
            seen = {}

            def fake_post(url, payload, timeout_seconds):
                seen["url"] = url
                seen["payload"] = payload
                seen["timeout"] = timeout_seconds
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"schema_version":"agent_recommendation.v1",'
                                    '"recommended_action":"run_trust",'
                                    '"reason":"Trust report is missing.",'
                                    '"next_command":"quant-lab summarize-run-trust --metadata run.json",'
                                    '"risks":["Sample is tiny."],'
                                    '"do_not_repeat":["Do not sweep first."],'
                                    '"confidence":"medium"}'
                                )
                            }
                        }
                    ]
                }

            result = suggest_with_openai_compatible_provider(
                context,
                base_url="http://localhost:11434/v1",
                model="qwen2.5:7b",
                timeout_seconds=12,
                http_post=fake_post,
            )

            self.assertIsNone(result.error)
            self.assertEqual("run_trust", result.recommendation.recommended_action)
            self.assertEqual("http://localhost:11434/v1/chat/completions", seen["url"])
            self.assertEqual("qwen2.5:7b", seen["payload"]["model"])
            self.assertEqual("json_schema", seen["payload"]["response_format"]["type"])
            self.assertEqual(
                "agent_recommendation",
                seen["payload"]["response_format"]["json_schema"]["name"],
            )
            self.assertEqual(12, seen["timeout"])

    def test_provider_accepts_json_inside_code_fence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _context_fixture(tmpdir)

            def fake_post(_url, _payload, _timeout_seconds):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": """```json
{"schema_version":"agent_recommendation.v1","recommended_action":"stop","reason":"Done.","next_command":null,"risks":[],"do_not_repeat":[],"confidence":"high"}
```"""
                            }
                        }
                    ]
                }

            result = suggest_with_openai_compatible_provider(context, base_url="http://local/v1", model="model", http_post=fake_post)

            self.assertIsNone(result.error)
            self.assertEqual("stop", result.recommendation.recommended_action)

    def test_provider_reports_invalid_json_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _context_fixture(tmpdir)

            def fake_post(_url, _payload, _timeout_seconds):
                return {"choices": [{"message": {"content": "not json"}}]}

            result = suggest_with_openai_compatible_provider(context, base_url="http://local/v1", model="model", http_post=fake_post)

            self.assertIsNone(result.recommendation)
            self.assertIn("not valid JSON", result.error)

    def test_provider_rejects_invalid_schema_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _context_fixture(tmpdir)

            def fake_post(_url, _payload, _timeout_seconds):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"schema_version":"agent_recommendation.v1",'
                                    '"recommended_action":"rewrite_code",'
                                    '"reason":"No.",'
                                    '"next_command":"quant-lab run",'
                                    '"risks":[],"do_not_repeat":[],"confidence":"medium"}'
                                )
                            }
                        }
                    ]
                }

            result = suggest_with_openai_compatible_provider(context, base_url="http://local/v1", model="model", http_post=fake_post)

            self.assertIsNone(result.recommendation)
            self.assertIn("recommended_action", result.error)

    def test_provider_preserves_raw_response_on_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _context_fixture(tmpdir)

            def fake_post(_url, _payload, _timeout_seconds):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"schema_version":"wrong",'
                                    '"recommended_action":"stop",'
                                    '"reason":"Done.",'
                                    '"next_command":null,'
                                    '"risks":[],"do_not_repeat":[],"confidence":"high"}'
                                )
                            }
                        }
                    ]
                }

            result = suggest_with_openai_compatible_provider(context, base_url="http://local/v1", model="model", http_post=fake_post)

            self.assertIsNone(result.recommendation)
            self.assertIn("schema_version", result.error)
            self.assertIn('"schema_version":"wrong"', result.raw_response)

    def test_prompt_contains_rules_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _context_fixture(tmpdir)

            prompt = build_agent_prompt(context)

            self.assertIn("return exactly one JSON object", prompt)
            self.assertIn("agent_recommendation.v1", prompt)
            self.assertIn("Provider test", prompt)
