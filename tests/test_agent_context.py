import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.agent_context import (
    AGENT_CONTEXT_SCHEMA_VERSION,
    agent_context_to_json,
    build_agent_context,
    format_agent_context_markdown,
    save_agent_context,
)
from quant_lab.cli import main
from quant_lab.session_manifest import SessionArtifact, SessionCommand, create_session_manifest, save_session_manifest


class AgentContextTest(unittest.TestCase):
    def test_build_agent_context_embeds_manifest_plan_and_key_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "research" / "spy"
            output_dir.mkdir(parents=True)
            plan_path = output_dir / "research_plan.json"
            report_path = output_dir / "baseline" / "run_metadata.json"
            missing_path = output_dir / "missing.md"
            plan_path.write_text('{"plan": true}\n', encoding="utf-8")
            report_path.parent.mkdir()
            report_path.write_text('{"total_return": 0.01}\n', encoding="utf-8")

            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="SPY trend walkthrough",
                hypothesis="Trend may reduce drawdown.",
                plan_path=plan_path,
                output_dir=output_dir,
                commands=[SessionCommand(label="Trust", command=f"quant-lab summarize-run-trust --metadata {report_path}")],
                key_artifacts=[
                    SessionArtifact(kind="run_metadata", path=str(report_path), role="raw_audit"),
                    SessionArtifact(kind="missing_note", path=str(missing_path), role="supporting"),
                ],
                current_status="in_progress",
                warnings=["Baseline trust report is missing."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            context = build_agent_context(manifest_path, generated_at_utc="2026-07-25T01:00:00Z")

            self.assertEqual(AGENT_CONTEXT_SCHEMA_VERSION, context.schema_version)
            self.assertEqual("session-001", context.manifest["session_id"])
            self.assertIn("Baseline trust report is missing.", context.warnings)
            self.assertTrue(any(file.kind == "research_plan" and file.included for file in context.files))
            self.assertTrue(any(file.kind == "run_metadata" and file.included for file in context.files))
            self.assertTrue(any(file.kind == "missing_note" and not file.exists for file in context.files))
            self.assertIn("quant-lab summarize-run-trust", context.next_commands[0])

    def test_agent_context_truncates_large_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            plan_path = output_dir / "research_plan.json"
            plan_path.write_text("abcdef\n", encoding="utf-8")
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Short context",
                hypothesis="Truncation should be explicit.",
                plan_path=plan_path,
                output_dir=output_dir,
                current_status="planned",
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            context = build_agent_context(manifest_path, max_chars_per_file=3)

            plan_file = next(file for file in context.files if file.kind == "research_plan")
            self.assertEqual("abc", plan_file.content)
            self.assertIn("truncated", plan_file.note)

    def test_save_agent_context_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            plan_path = output_dir / "research_plan.json"
            plan_path.write_text("{}\n", encoding="utf-8")
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Write context",
                hypothesis="Context files should be durable.",
                plan_path=plan_path,
                output_dir=output_dir,
                current_status="planned",
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)
            context = build_agent_context(manifest_path)

            json_path, markdown_path = save_agent_context(context)

            payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
            markdown = Path(markdown_path).read_text(encoding="utf-8")
            self.assertEqual("agent_context.v1", payload["schema_version"])
            self.assertIn("bounded advisor input", markdown)

    def test_agent_context_json_and_markdown_formatters_are_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            plan_path = output_dir / "research_plan.json"
            plan_path.write_text("{}\n", encoding="utf-8")
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Format context",
                hypothesis="Formatting should be stable.",
                plan_path=plan_path,
                output_dir=output_dir,
                current_status="planned",
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)
            context = build_agent_context(manifest_path)

            self.assertEqual("agent_context.v1", json.loads(agent_context_to_json(context))["schema_version"])
            self.assertIn("## Operating Rules", format_agent_context_markdown(context))

    def test_cli_agent_context_writes_files_and_prints_next_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            plan_path = output_dir / "research_plan.json"
            plan_path.write_text("{}\n", encoding="utf-8")
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="CLI context",
                hypothesis="CLI should write context.",
                plan_path=plan_path,
                output_dir=output_dir,
                commands=[SessionCommand(label="Next", command="quant-lab research-plan next --plan research_plan.json")],
                current_status="planned",
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["agent", "context", "--manifest", manifest_path])

            output = stdout.getvalue()
            self.assertEqual(0, exit_code)
            self.assertTrue((output_dir / "agent_context_bundle.json").exists())
            self.assertTrue((output_dir / "agent_context_bundle.md").exists())
            self.assertIn("next_command:", output)

    def test_cli_agent_context_json_output_is_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            plan_path = output_dir / "research_plan.json"
            plan_path.write_text("{}\n", encoding="utf-8")
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="CLI JSON context",
                hypothesis="CLI JSON should be parseable.",
                plan_path=plan_path,
                output_dir=output_dir,
                current_status="planned",
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["agent", "context", "--manifest", manifest_path, "--json"])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual("agent_context.v1", payload["schema_version"])
