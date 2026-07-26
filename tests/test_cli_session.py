import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from quant_lab.cli import main
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


if __name__ == "__main__":
    unittest.main()
