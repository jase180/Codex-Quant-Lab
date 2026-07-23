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


class CliPortfolioResearchPlanTests(unittest.TestCase):
    def test_portfolio_plan_init_writes_plan_and_prints_baseline_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_dir = temp_path / "research" / "qqq_spy"
            experiments_path = temp_path / "experiments.jsonl"
            index_path = temp_path / "research_index.jsonl"

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "portfolio-plan",
                        "init",
                        "--title",
                        "QQQ SPY allocation check",
                        "--hypothesis",
                        "A 60/40 QQQ/SPY allocation may beat SPY.",
                        "--portfolio",
                        "data/portfolios/qqq_spy_static_60_40.json",
                        "--tag",
                        "QQQ,SPY",
                        "--out",
                        str(output_dir),
                        "--experiments-path",
                        str(experiments_path),
                        "--index-path",
                        str(index_path),
                        "--cost-preset",
                        "retail-liquid",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "portfolio_research_plan.json").exists())
            self.assertTrue((output_dir / "portfolio_research_plan.md").exists())
            plan = json.loads((output_dir / "portfolio_research_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["schema_version"], "portfolio_research_plan.v1")
            self.assertEqual(plan["experiment_id"], "EXP-001")
            self.assertEqual(plan["portfolio_path"], "data/portfolios/qqq_spy_static_60_40.json")
            self.assertEqual(plan["tags"], ["qqq", "spy"])
            self.assertEqual(plan["cost_preset"], "retail-liquid")

            experiment = json.loads(experiments_path.read_text(encoding="utf-8").strip())
            self.assertEqual(experiment["experiment_id"], "EXP-001")
            self.assertEqual(experiment["title"], "QQQ SPY allocation check")
            self.assertEqual(experiment["strategy_path"], "data/portfolios/qqq_spy_static_60_40.json")

            output = stdout.getvalue()
            self.assertIn("Portfolio research plan created:", output)
            self.assertIn("experiment_id: EXP-001", output)
            self.assertIn("next_command:", output)
            self.assertIn("quant-lab portfolio-run", output)
            self.assertIn("--portfolio data/portfolios/qqq_spy_static_60_40.json", output)
            self.assertIn(str(output_dir / "baseline"), output)
            self.assertIn("--experiment-id EXP-001", output)
            self.assertIn("--cost-preset retail-liquid", output)

    def test_portfolio_plan_next_recommends_baseline_when_no_runs_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, _ = self._create_plan_fixture(Path(temp_dir))

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    ["portfolio-plan", "next", "--plan", str(output_dir / "portfolio_research_plan.json")]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: baseline", output)
            self.assertIn("No portfolio run", output)
            self.assertIn("quant-lab portfolio-run", output)

    def test_portfolio_plan_next_recommends_data_trust_after_one_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, index_path = self._create_plan_fixture(Path(temp_dir))
            self._write_index_records(
                index_path,
                [
                    {
                        "run_type": "portfolio_run",
                        "experiment_id": "EXP-001",
                        "metadata_path": "baseline/portfolio_metadata.json",
                    }
                ],
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    ["portfolio-plan", "next", "--plan", str(output_dir / "portfolio_research_plan.json")]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: data_trust", output)
            self.assertIn("quant-lab summarize-portfolio-data-trust", output)
            self.assertIn("--metadata baseline/portfolio_metadata.json", output)

    def test_portfolio_plan_next_recommends_inspect_after_data_trust_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, index_path = self._create_plan_fixture(Path(temp_dir))
            baseline_dir = output_dir / "baseline"
            baseline_dir.mkdir()
            metadata_path = baseline_dir / "portfolio_metadata.json"
            metadata_path.write_text("{}\n", encoding="utf-8")
            (baseline_dir / "portfolio_data_trust_report.md").write_text("# Trust\n", encoding="utf-8")
            self._write_index_records(
                index_path,
                [
                    {
                        "run_type": "portfolio_run",
                        "experiment_id": "EXP-001",
                        "metadata_path": str(metadata_path),
                    }
                ],
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    ["portfolio-plan", "next", "--plan", str(output_dir / "portfolio_research_plan.json")]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: inspect", output)
            self.assertIn("quant-lab show-portfolio-run", output)

    def test_portfolio_plan_next_recommends_summary_after_two_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, index_path = self._create_plan_fixture(Path(temp_dir))
            self._write_two_portfolio_run_records(index_path, output_dir, trust_report_exists=True)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    ["portfolio-plan", "next", "--plan", str(output_dir / "portfolio_research_plan.json")]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: summarize", output)
            self.assertIn("quant-lab summarize-portfolio-experiment", output)
            self.assertIn("--out", output)
            self.assertIn(str(output_dir / "portfolio_summary.md"), output)

    def test_portfolio_plan_next_recommends_robustness_review_after_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, index_path = self._create_plan_fixture(Path(temp_dir))
            (output_dir / "portfolio_summary.md").write_text("# Summary\n", encoding="utf-8")
            self._write_two_portfolio_run_records(index_path, output_dir, trust_report_exists=True)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    ["portfolio-plan", "next", "--plan", str(output_dir / "portfolio_research_plan.json")]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: portfolio_robustness_review", output)
            self.assertIn("linked runs do not yet show both cost and benchmark robustness", output)
            self.assertIn("quant-lab portfolio-run", output)
            self.assertIn("--cost-preset retail-conservative", output)

    def test_portfolio_plan_next_recommends_variants_after_robustness_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, index_path = self._create_plan_fixture(Path(temp_dir))
            (output_dir / "portfolio_summary.md").write_text("# Summary\n", encoding="utf-8")
            self._write_two_portfolio_run_records(
                index_path,
                output_dir,
                trust_report_exists=True,
                second_cost_preset="high-friction",
                second_benchmark_name="buy-and-hold-qqq",
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    ["portfolio-plan", "next", "--plan", str(output_dir / "portfolio_research_plan.json")]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: variants", output)
            self.assertIn("quant-lab portfolio-variants", output)
            self.assertIn("--weights QQQ=0.6,SPY=0.4", output)
            self.assertIn(str(output_dir / "portfolio_variants"), output)

    def test_portfolio_plan_next_recommends_batch_plan_when_candidates_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, index_path = self._create_plan_ready_for_batch(Path(temp_dir))
            variants_dir = output_dir / "portfolio_variants"
            variants_dir.mkdir()
            (variants_dir / "candidate.json").write_text('{"schema_version": "portfolio_plan.v1"}\n', encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    ["portfolio-plan", "next", "--plan", str(output_dir / "portfolio_research_plan.json")]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: batch_plan", output)
            self.assertIn("quant-lab portfolio-batch plan", output)
            self.assertIn(str(output_dir / "portfolio_variants"), output)
            self.assertIn(str(output_dir / "portfolio_batch"), output)
            self.assertTrue(index_path.exists())

    def test_portfolio_plan_next_recommends_batch_run_when_manifest_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, _ = self._create_plan_ready_for_batch(Path(temp_dir))
            variants_dir = output_dir / "portfolio_variants"
            batch_dir = output_dir / "portfolio_batch"
            variants_dir.mkdir()
            batch_dir.mkdir()
            (variants_dir / "candidate.json").write_text('{"schema_version": "portfolio_plan.v1"}\n', encoding="utf-8")
            (batch_dir / "portfolio_batch_manifest.json").write_text("{}\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    ["portfolio-plan", "next", "--plan", str(output_dir / "portfolio_research_plan.json")]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: batch_run", output)
            self.assertIn("quant-lab portfolio-batch run", output)
            self.assertIn("--experiment-id EXP-001", output)

    def test_portfolio_plan_next_recommends_batch_summarize_when_result_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, _ = self._create_plan_ready_for_batch(Path(temp_dir))
            variants_dir = output_dir / "portfolio_variants"
            batch_dir = output_dir / "portfolio_batch"
            variants_dir.mkdir()
            batch_dir.mkdir()
            (variants_dir / "candidate.json").write_text('{"schema_version": "portfolio_plan.v1"}\n', encoding="utf-8")
            (batch_dir / "portfolio_batch_manifest.json").write_text("{}\n", encoding="utf-8")
            (batch_dir / "portfolio_batch_result.json").write_text("{}\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    ["portfolio-plan", "next", "--plan", str(output_dir / "portfolio_research_plan.json")]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: batch_summarize", output)
            self.assertIn("quant-lab portfolio-batch summarize", output)

    def _create_plan_fixture(self, temp_path: Path) -> tuple[Path, Path, Path]:
        output_dir = temp_path / "research" / "qqq_spy"
        experiments_path = temp_path / "experiments.jsonl"
        index_path = temp_path / "research_index.jsonl"
        with contextlib.redirect_stdout(io.StringIO()):
            main(
                [
                    "portfolio-plan",
                    "init",
                    "--title",
                    "QQQ SPY allocation check",
                    "--hypothesis",
                    "A 60/40 QQQ/SPY allocation may beat SPY.",
                    "--portfolio",
                    "data/portfolios/qqq_spy_static_60_40.json",
                    "--out",
                    str(output_dir),
                    "--experiments-path",
                    str(experiments_path),
                    "--index-path",
                    str(index_path),
                    "--cost-preset",
                    "retail-liquid",
                ]
            )
        return output_dir, experiments_path, index_path

    def _create_plan_ready_for_batch(self, temp_path: Path) -> tuple[Path, Path, Path]:
        output_dir, experiments_path, index_path = self._create_plan_fixture(temp_path)
        (output_dir / "portfolio_summary.md").write_text("# Summary\n", encoding="utf-8")
        self._write_two_portfolio_run_records(
            index_path,
            output_dir,
            trust_report_exists=True,
            second_cost_preset="high-friction",
            second_benchmark_name="buy-and-hold-qqq",
        )
        return output_dir, experiments_path, index_path

    def _write_two_portfolio_run_records(
        self,
        index_path: Path,
        output_dir: Path,
        *,
        trust_report_exists: bool,
        second_cost_preset: str = "retail-liquid",
        second_benchmark_name: str = "buy-and-hold-spy",
    ) -> None:
        baseline_metadata = output_dir / "baseline" / "portfolio_metadata.json"
        variant_metadata = output_dir / "variant" / "portfolio_metadata.json"
        baseline_metadata.parent.mkdir()
        variant_metadata.parent.mkdir()
        baseline_metadata.write_text("{}\n", encoding="utf-8")
        variant_metadata.write_text("{}\n", encoding="utf-8")
        if trust_report_exists:
            (baseline_metadata.parent / "portfolio_data_trust_report.md").write_text("# Trust\n", encoding="utf-8")
        self._write_index_records(
            index_path,
            [
                {
                    "run_type": "portfolio_run",
                    "experiment_id": "EXP-001",
                    "metadata_path": str(baseline_metadata),
                    "cost_preset": "retail-liquid",
                    "benchmark_name": "buy-and-hold-spy",
                },
                {
                    "run_type": "portfolio_run",
                    "experiment_id": "EXP-001",
                    "metadata_path": str(variant_metadata),
                    "cost_preset": second_cost_preset,
                    "benchmark_name": second_benchmark_name,
                },
            ],
        )

    def _write_index_records(self, index_path: Path, records: list[dict]) -> None:
        index_path.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
