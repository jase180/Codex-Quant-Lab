import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.session_manifest import (
    SESSION_MANIFEST_SCHEMA_VERSION,
    SessionArtifact,
    SessionCommand,
    create_session_manifest,
    format_session_manifest_markdown,
    load_session_manifest,
    save_session_manifest,
    session_manifest_json_path,
    session_manifest_markdown_path,
)


class SessionManifestTest(unittest.TestCase):
    def test_create_manifest_normalizes_fields_and_keeps_stable_keys(self) -> None:
        manifest = create_session_manifest(
            session_id=" SPY-TREND-SESSION ",
            experiment_id=" EXP-SPY-TREND ",
            title=" SPY trend walkthrough ",
            hypothesis=" Trend filter may reduce drawdown. ",
            plan_path="artifacts/research/spy/research_plan.json",
            output_dir="artifacts/research/spy",
            data_sources=["data/cache/SPY.csv", "data/cache/SPY.csv"],
            strategy_paths=["data/strategies/spy_trend.json"],
            commands=[SessionCommand(label="Baseline", command="quant-lab run ...", status="planned")],
            key_artifacts=[
                SessionArtifact(
                    kind="experiment_conclusion",
                    path="artifacts/research/spy/experiment_conclusion.md",
                    role="main",
                )
            ],
            conclusion_path="artifacts/research/spy/experiment_conclusion.md",
            current_status="needs_decision",
            outstanding_next_steps=["Draft decision", "Draft decision"],
            warnings=["Evidence summary may be stale"],
            created_at_utc="2026-07-25T00:00:00Z",
        )

        self.assertEqual(SESSION_MANIFEST_SCHEMA_VERSION, manifest.schema_version)
        self.assertEqual("SPY-TREND-SESSION", manifest.session_id)
        self.assertEqual(["data/cache/SPY.csv"], manifest.data_sources)
        self.assertEqual(["Draft decision"], manifest.outstanding_next_steps)
        self.assertEqual(
            [
                "schema_version",
                "session_id",
                "experiment_id",
                "title",
                "hypothesis",
                "created_at_utc",
                "updated_at_utc",
                "plan_path",
                "output_dir",
                "data_sources",
                "strategy_paths",
                "commands",
                "key_artifacts",
                "conclusion_path",
                "decision_path",
                "current_status",
                "outstanding_next_steps",
                "warnings",
            ],
            list(manifest.to_dict()),
        )

    def test_save_and_load_manifest_round_trips_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "spy"
            manifest = create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="SPY trend walkthrough",
                hypothesis="Trend may reduce drawdown.",
                plan_path=output_dir / "research_plan.json",
                output_dir=output_dir,
                data_sources=[Path("data/cache/SPY.csv")],
                strategy_paths=[Path("data/strategies/spy_trend.json")],
                commands=[SessionCommand(label="Next", command="quant-lab research-plan next ...")],
                key_artifacts=[
                    SessionArtifact(kind="research_plan", path=str(output_dir / "research_plan.json"), role="plan")
                ],
                conclusion_path=output_dir / "experiment_conclusion.md",
                current_status="in_progress",
                created_at_utc="2026-07-25T00:00:00Z",
            )

            json_path, markdown_path = save_session_manifest(manifest)

            self.assertEqual(session_manifest_json_path(output_dir), Path(json_path))
            self.assertEqual(session_manifest_markdown_path(output_dir), Path(markdown_path))
            payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
            self.assertEqual("session_manifest.v1", payload["schema_version"])
            self.assertTrue(Path(json_path).read_text(encoding="utf-8").endswith("\n"))
            self.assertIn("Report role: workflow orientation.", Path(markdown_path).read_text(encoding="utf-8"))

            loaded = load_session_manifest(json_path)
            self.assertEqual(manifest.to_dict(), loaded.to_dict())

    def test_markdown_points_to_conclusion_without_replacing_it(self) -> None:
        manifest = create_session_manifest(
            session_id="session-001",
            experiment_id="EXP-001",
            title="SPY trend walkthrough",
            hypothesis="Trend may reduce drawdown.",
            plan_path="artifacts/research/spy/research_plan.json",
            output_dir="artifacts/research/spy",
            conclusion_path="artifacts/research/spy/experiment_conclusion.md",
            decision_path="experiment:EXP-001",
            current_status="complete",
            created_at_utc="2026-07-25T00:00:00Z",
        )

        markdown = format_session_manifest_markdown(manifest)

        self.assertIn("Session orientation", markdown)
        self.assertIn("Research conclusion: `artifacts/research/spy/experiment_conclusion.md`", markdown)
        self.assertIn("Machine conclusion: `artifacts/research/spy/experiment_conclusion.json`", markdown)
        self.assertNotIn("Current Conclusion", markdown)

    def test_validation_rejects_unknown_statuses(self) -> None:
        with self.assertRaisesRegex(ValueError, "current_status"):
            create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Bad status",
                hypothesis="Bad status should fail.",
                plan_path="research_plan.json",
                output_dir="artifacts/research/bad",
                current_status="definitely_done",
            )

        with self.assertRaisesRegex(ValueError, "session command status"):
            create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Bad command status",
                hypothesis="Bad command status should fail.",
                plan_path="research_plan.json",
                output_dir="artifacts/research/bad",
                commands=[SessionCommand(label="Bad", command="quant-lab run", status="ran_maybe")],
            )

        with self.assertRaisesRegex(ValueError, "session artifact role"):
            create_session_manifest(
                session_id="session-001",
                experiment_id="EXP-001",
                title="Bad artifact role",
                hypothesis="Bad artifact role should fail.",
                plan_path="research_plan.json",
                output_dir="artifacts/research/bad",
                key_artifacts=[SessionArtifact(kind="report", path="report.md", role="kind_of_main")],
            )


if __name__ == "__main__":
    unittest.main()
