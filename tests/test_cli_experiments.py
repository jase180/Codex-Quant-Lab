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
from quant_lab.research_plan import create_research_plan, save_research_plan  # noqa: E402
from quant_lab.session_manifest import (  # noqa: E402
    SessionCommand,
    create_session_manifest,
    save_session_manifest,
)
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

    def test_decide_experiment_writes_structured_decision(self) -> None:
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
                        "decide-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--experiment-id",
                        "EXP-001",
                        "--outcome",
                        "continue",
                        "--rationale",
                        "The best sweep is promising but the validation set is too small.",
                        "--supporting-run",
                        "artifacts/sweep/run_004/run_metadata.json",
                        "--contradicting-run",
                        "artifacts/train_test/test_selected/run_metadata.json",
                        "--next-action",
                        "Run walk-forward windows before accepting or rejecting.",
                        "--tag",
                        "needs-walk-forward",
                    ]
                )

            payload = json.loads(registry_path.read_text(encoding="utf-8").strip())
            self.assertEqual(exit_code, 0)
            self.assertIn("Experiment decided: EXP-001", stdout.getvalue())
            self.assertEqual(payload["status"], "running")
            self.assertEqual(
                payload["decision"],
                "continue: The best sweep is promising but the validation set is too small.",
            )
            self.assertEqual(payload["decision_record"]["outcome"], "continue")
            self.assertEqual(
                payload["decision_record"]["supporting_run"],
                "artifacts/sweep/run_004/run_metadata.json",
            )
            self.assertEqual(
                payload["decision_record"]["contradicting_run"],
                "artifacts/train_test/test_selected/run_metadata.json",
            )
            self.assertEqual(
                payload["decision_record"]["next_action"],
                "Run walk-forward windows before accepting or rejecting.",
            )
            self.assertEqual(payload["tags"], ["qqq", "needs-walk-forward"])

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
            self.assertIn("Outcome: continue", output)
            self.assertIn("Supporting Run: artifacts/sweep/run_004/run_metadata.json", output)
            self.assertIn("Next Action: Run walk-forward windows", output)

    def test_link_run_adds_metadata_path_to_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            registry_path = temp_path / "experiments.jsonl"
            metadata_path = temp_path / "run_metadata.json"
            metadata_path.write_text('{"metadata_schema_version": "run_metadata.v1"}\n', encoding="utf-8")
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

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "link-run",
                        "--experiments-path",
                        str(registry_path),
                        "--experiment-id",
                        "EXP-001",
                        "--metadata",
                        str(metadata_path),
                        "--metadata",
                        str(metadata_path),
                    ]
                )

            payload = json.loads(registry_path.read_text(encoding="utf-8").strip())
            self.assertEqual(exit_code, 0)
            self.assertIn("Experiment linked: EXP-001", stdout.getvalue())
            self.assertEqual(payload["linked_runs"], [str(metadata_path)])

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

            self.assertIn(str(metadata_path), show_stdout.getvalue())

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

    def test_summarize_portfolio_experiment_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            registry_path = temp_path / "experiments.jsonl"
            index_path = temp_path / "research_index.jsonl"
            output_path = temp_path / "portfolio_summary.md"
            index_path.write_text(
                json.dumps(
                    {
                        "index_schema_version": "research_index.v1",
                        "created_at_utc": "2026-01-01T00:00:00Z",
                        "run_type": "portfolio_run",
                        "run_id": None,
                        "experiment_id": "EXP-001",
                        "strategy_id": "qqq_50_spy_50",
                        "strategy_name": "QQQ SPY 50/50",
                        "symbol": "QQQ,SPY",
                        "timeframe": "1d",
                        "data_start": "2026-01-01",
                        "data_end": "2026-01-31",
                        "final_equity": 1080,
                        "total_return": 0.08,
                        "cagr": None,
                        "sharpe_ratio": 0.8,
                        "max_drawdown": -0.12,
                        "trade_count": 4,
                        "benchmark_name": "buy-and-hold-spy",
                        "benchmark_total_return": 0.06,
                        "benchmark_max_drawdown": -0.1,
                        "excess_total_return": 0.02,
                        "sizing": "static-weights",
                        "initial_cash": 1000,
                        "quantity": 0,
                        "allocation": 1,
                        "cost_preset": "none",
                        "commission_fixed": 0,
                        "commission_rate": 0,
                        "slippage_bps": 0,
                        "output_dir": "artifacts/portfolio_a",
                        "metadata_path": "artifacts/portfolio_a/portfolio_metadata.json",
                        "git_commit": "abc",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "new-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--experiment-id",
                        "EXP-001",
                        "--title",
                        "Portfolio variants",
                        "--hypothesis",
                        "Allocation variants may beat SPY.",
                    ]
                )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "summarize-portfolio-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--index-path",
                        str(index_path),
                        "--experiment-id",
                        "EXP-001",
                        "--out",
                        str(output_path),
                    ]
                )

            markdown = output_path.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertIn("Portfolio experiment summary written:", stdout.getvalue())
            self.assertIn("# Portfolio Experiment Summary", markdown)
            self.assertIn("qqq_50_spy_50", markdown)

    def test_conclude_experiment_writes_canonical_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            registry_path = temp_path / "experiments.jsonl"
            index_path = temp_path / "research_index.jsonl"
            output_dir = temp_path / "conclusion"
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
                        "--strategy",
                        "data/strategies/qqq.json",
                        "--data",
                        "data/cache/qqq.csv",
                    ]
                )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "conclude-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--index-path",
                        str(index_path),
                        "--experiment-id",
                        "EXP-002",
                        "--out",
                        str(output_dir),
                    ]
                )

            conclusion_json = output_dir / "experiment_conclusion.json"
            conclusion_markdown = output_dir / "experiment_conclusion.md"
            agent_context = output_dir / "agent_context.md"
            payload = json.loads(conclusion_json.read_text(encoding="utf-8"))
            markdown = conclusion_markdown.read_text(encoding="utf-8")

            self.assertEqual(exit_code, 0)
            self.assertIn("Experiment conclusion written:", stdout.getvalue())
            self.assertTrue(conclusion_json.exists())
            self.assertTrue(conclusion_markdown.exists())
            self.assertTrue(agent_context.exists())
            self.assertEqual(payload["schema_version"], "experiment_conclusion.v1")
            self.assertEqual(payload["experiment_id"], "EXP-002")
            self.assertEqual(payload["confidence_label"], "weak")
            self.assertIn("artifacts/qqq_run/run_metadata.json", markdown)
            self.assertIn("experiment_conclusion.json", agent_context.read_text(encoding="utf-8"))

    def test_conclude_experiment_updates_existing_session_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            registry_path = temp_path / "experiments.jsonl"
            index_path = temp_path / "research_index.jsonl"
            output_dir = temp_path / "research" / "qqq"
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
                        "--strategy",
                        "data/strategies/qqq.json",
                        "--data",
                        "data/cache/qqq.csv",
                    ]
                )
            plan = create_research_plan(
                title="QQQ idea",
                hypothesis="A valid hypothesis.",
                strategy_path="data/strategies/qqq.json",
                data_path="data/cache/qqq.csv",
                symbol="QQQ",
                experiment_id="EXP-002",
                experiments_path=registry_path,
                index_path=index_path,
                output_dir=output_dir,
                created_at_utc="2026-07-25T00:00:00Z",
            )
            plan_path, _ = save_research_plan(plan)
            manifest = create_session_manifest(
                session_id="session-exp-002",
                experiment_id="EXP-002",
                title="QQQ idea",
                hypothesis="A valid hypothesis.",
                plan_path=plan_path,
                output_dir=output_dir,
                commands=[
                    SessionCommand(
                        label="Recommended next step: conclude_experiment",
                        command="quant-lab conclude-experiment ...",
                        status="suggested",
                    )
                ],
                current_status="needs_conclusion",
                outstanding_next_steps=["conclude_experiment: Write the canonical conclusion."],
                warnings=["Canonical conclusion is missing; run the recommended conclusion command before deciding."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            save_session_manifest(manifest)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "conclude-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--index-path",
                        str(index_path),
                        "--experiment-id",
                        "EXP-002",
                        "--out",
                        str(output_dir),
                    ]
                )

            payload = json.loads((output_dir / "session_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertIn("session_manifest:", stdout.getvalue())
            self.assertEqual("needs_decision", payload["current_status"])
            self.assertEqual(str(output_dir / "experiment_conclusion.md"), payload["conclusion_path"])
            self.assertEqual([], payload["warnings"])
            self.assertEqual("Recommended next step: draft_decision", payload["commands"][0]["label"])
            self.assertIn("quant-lab draft-decision", payload["commands"][0]["command"])
            artifact_paths = [artifact["path"] for artifact in payload["key_artifacts"]]
            self.assertIn(str(output_dir / "experiment_conclusion.md"), artifact_paths)
            self.assertIn(str(output_dir / "experiment_conclusion.json"), artifact_paths)

    def test_conclude_experiment_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            registry_path = temp_path / "experiments.jsonl"
            index_path = temp_path / "research_index.jsonl"
            output_dir = temp_path / "conclusion"
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
                main(
                    [
                        "conclude-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--index-path",
                        str(index_path),
                        "--experiment-id",
                        "EXP-002",
                        "--out",
                        str(output_dir),
                    ]
                )

            with self.assertRaisesRegex(FileExistsError, "pass --force"):
                main(
                    [
                        "conclude-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--index-path",
                        str(index_path),
                        "--experiment-id",
                        "EXP-002",
                        "--out",
                        str(output_dir),
                    ]
                )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "conclude-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--index-path",
                        str(index_path),
                        "--experiment-id",
                        "EXP-002",
                        "--out",
                        str(output_dir),
                        "--force",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("confidence:", stdout.getvalue())

    def test_draft_decision_prints_template_without_writing_registry(self) -> None:
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
            before = registry_path.read_text(encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "draft-decision",
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
            self.assertEqual(registry_path.read_text(encoding="utf-8"), before)
            self.assertIn("Experiment Decision Draft", output)
            self.assertIn("Suggested outcome:", output)
            self.assertIn("quant-lab decide-experiment", output)

    def test_decide_experiment_updates_existing_session_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            registry_path = temp_path / "experiments.jsonl"
            output_dir = temp_path / "research" / "qqq"
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
            plan = create_research_plan(
                title="QQQ idea",
                hypothesis="A valid hypothesis.",
                strategy_path="data/strategies/qqq.json",
                data_path="data/cache/qqq.csv",
                symbol="QQQ",
                experiment_id="EXP-002",
                experiments_path=registry_path,
                output_dir=output_dir,
                created_at_utc="2026-07-25T00:00:00Z",
            )
            plan_path, _ = save_research_plan(plan)
            manifest = create_session_manifest(
                session_id="session-exp-002",
                experiment_id="EXP-002",
                title="QQQ idea",
                hypothesis="A valid hypothesis.",
                plan_path=plan_path,
                output_dir=output_dir,
                commands=[
                    SessionCommand(
                        label="Recommended next step: draft_decision",
                        command="quant-lab draft-decision ...",
                        status="suggested",
                    )
                ],
                conclusion_path=output_dir / "experiment_conclusion.md",
                current_status="needs_decision",
                outstanding_next_steps=["draft_decision: Draft a conservative decision."],
                warnings=["Decision has not been recorded yet."],
                created_at_utc="2026-07-25T00:00:00Z",
            )
            manifest_path, _ = save_session_manifest(manifest)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "decide-experiment",
                        "--experiments-path",
                        str(registry_path),
                        "--experiment-id",
                        "EXP-002",
                        "--outcome",
                        "reject",
                        "--rationale",
                        "Evidence did not beat benchmark.",
                        "--session-manifest",
                        manifest_path,
                    ]
                )

            payload = json.loads((output_dir / "session_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertIn("session_manifest:", stdout.getvalue())
            self.assertEqual("complete", payload["current_status"])
            self.assertEqual("experiment:EXP-002", payload["decision_path"])
            self.assertEqual([], payload["commands"])
            self.assertEqual([], payload["outstanding_next_steps"])
            self.assertEqual([], payload["warnings"])
            artifact_paths = [artifact["path"] for artifact in payload["key_artifacts"]]
            self.assertIn("experiment:EXP-002", artifact_paths)


if __name__ == "__main__":
    unittest.main()
