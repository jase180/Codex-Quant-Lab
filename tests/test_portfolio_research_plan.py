from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.portfolio_research_plan import (  # noqa: E402
    DEFAULT_PORTFOLIO_RECOMMENDED_STEPS,
    PORTFOLIO_RESEARCH_PLAN_SCHEMA_VERSION,
    build_compare_portfolio_runs_command,
    build_portfolio_data_trust_command,
    build_portfolio_batch_plan_command_from_plan,
    build_portfolio_baseline_command_from_plan,
    build_portfolio_summarize_command_from_plan,
    build_portfolio_variants_command_from_plan,
    create_portfolio_research_plan,
    load_portfolio_research_plan,
    recommend_portfolio_next_step,
    render_portfolio_research_plan_markdown,
    save_portfolio_research_plan,
)


class PortfolioResearchPlanTests(unittest.TestCase):
    def test_create_portfolio_research_plan_normalizes_fields(self) -> None:
        plan = create_portfolio_research_plan(
            title="  QQQ SPY check  ",
            hypothesis="  A 60/40 allocation may beat SPY.  ",
            portfolio_path="data/portfolios/qqq_spy_static_60_40.json",
            experiment_id=" EXP-001 ",
            output_dir="artifacts/research/qqq_spy_static_60_40",
            tags=["QQQ,SPY", "portfolio"],
            created_at_utc="2026-07-18T00:00:00Z",
        )

        self.assertEqual(plan.schema_version, PORTFOLIO_RESEARCH_PLAN_SCHEMA_VERSION)
        self.assertEqual(plan.title, "QQQ SPY check")
        self.assertEqual(plan.hypothesis, "A 60/40 allocation may beat SPY.")
        self.assertEqual(plan.experiment_id, "EXP-001")
        self.assertEqual(plan.tags, ["qqq", "spy", "portfolio"])
        self.assertEqual(plan.recommended_steps, list(DEFAULT_PORTFOLIO_RECOMMENDED_STEPS))

    def test_save_portfolio_research_plan_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "research" / "portfolio"
            plan = create_portfolio_research_plan(
                title="QQQ SPY check",
                hypothesis="A 60/40 allocation may beat SPY.",
                portfolio_path="data/portfolios/qqq_spy_static_60_40.json",
                experiment_id="EXP-001",
                output_dir=output_dir,
                tags=["portfolio"],
                created_at_utc="2026-07-18T00:00:00Z",
            )

            json_path, markdown_path = save_portfolio_research_plan(plan)

            payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "portfolio_research_plan.v1")
            self.assertEqual(payload["portfolio_path"], "data/portfolios/qqq_spy_static_60_40.json")
            self.assertEqual(payload["recommended_steps"][0], "baseline")
            self.assertTrue(Path(json_path).read_text(encoding="utf-8").endswith("\n"))

            markdown = Path(markdown_path).read_text(encoding="utf-8")
            self.assertIn("# QQQ SPY check", markdown)
            self.assertIn("- Portfolio: `data/portfolios/qqq_spy_static_60_40.json`", markdown)
            self.assertIn("This plan organizes portfolio research.", markdown)

    def test_load_portfolio_research_plan_round_trips_saved_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = create_portfolio_research_plan(
                title="QQQ SPY check",
                hypothesis="A 60/40 allocation may beat SPY.",
                portfolio_path="data/portfolios/qqq_spy_static_60_40.json",
                experiment_id="EXP-001",
                output_dir=Path(temp_dir),
                created_at_utc="2026-07-18T00:00:00Z",
            )
            json_path, _ = save_portfolio_research_plan(plan)

            loaded = load_portfolio_research_plan(json_path)

            self.assertEqual(loaded, plan)

    def test_recommend_portfolio_next_step_follows_portfolio_run_count(self) -> None:
        plan = create_portfolio_research_plan(
            title="QQQ SPY check",
            hypothesis="A 60/40 allocation may beat SPY.",
            portfolio_path="data/portfolios/qqq_spy_static_60_40.json",
            experiment_id="EXP-001",
            output_dir="artifacts/research/qqq_spy_static_60_40",
            created_at_utc="2026-07-18T00:00:00Z",
        )

        baseline = recommend_portfolio_next_step(plan, [])
        inspect = recommend_portfolio_next_step(
            plan,
            [{"run_type": "portfolio_run", "metadata_path": "baseline/portfolio_metadata.json"}],
            data_trust_report_exists=True,
        )
        data_trust = recommend_portfolio_next_step(
            plan,
            [{"run_type": "portfolio_run", "metadata_path": "baseline/portfolio_metadata.json"}],
        )
        summarize = recommend_portfolio_next_step(
            plan,
            [
                {"run_type": "portfolio_run", "metadata_path": "baseline/portfolio_metadata.json"},
                {"run_type": "portfolio_run", "metadata_path": "variant/portfolio_metadata.json"},
            ],
            data_trust_report_exists=True,
        )
        robust_records = [
            {
                "run_type": "portfolio_run",
                "metadata_path": "baseline/portfolio_metadata.json",
                "cost_preset": "retail-liquid",
                "benchmark_name": "buy-and-hold-spy",
            },
            {
                "run_type": "portfolio_run",
                "metadata_path": "variant/portfolio_metadata.json",
                "cost_preset": "high-friction",
                "benchmark_name": "buy-and-hold-qqq",
            },
        ]
        robustness_review = recommend_portfolio_next_step(
            plan,
            [
                {
                    "run_type": "portfolio_run",
                    "metadata_path": "baseline/portfolio_metadata.json",
                    "cost_preset": "retail-liquid",
                    "benchmark_name": "buy-and-hold-spy",
                },
                {
                    "run_type": "portfolio_run",
                    "metadata_path": "variant/portfolio_metadata.json",
                    "cost_preset": "retail-liquid",
                    "benchmark_name": "buy-and-hold-spy",
                },
            ],
            summary_exists=True,
            data_trust_report_exists=True,
        )
        variants = recommend_portfolio_next_step(
            plan,
            robust_records,
            summary_exists=True,
            data_trust_report_exists=True,
        )
        compare = recommend_portfolio_next_step(
            plan,
            robust_records,
            summary_exists=True,
            variants_exist=True,
            data_trust_report_exists=True,
        )
        batch_plan = recommend_portfolio_next_step(
            plan,
            robust_records,
            summary_exists=True,
            variants_exist=True,
            candidate_specs_exist=True,
            data_trust_report_exists=True,
        )
        batch_run = recommend_portfolio_next_step(
            plan,
            robust_records,
            summary_exists=True,
            variants_exist=True,
            candidate_specs_exist=True,
            batch_manifest_exists=True,
            data_trust_report_exists=True,
        )
        batch_summarize = recommend_portfolio_next_step(
            plan,
            robust_records,
            summary_exists=True,
            variants_exist=True,
            candidate_specs_exist=True,
            batch_manifest_exists=True,
            batch_result_exists=True,
            data_trust_report_exists=True,
        )
        done = recommend_portfolio_next_step(plan, [], experiment_has_decision=True)

        self.assertEqual(baseline.step, "baseline")
        self.assertIn("quant-lab portfolio-run", baseline.command or "")
        self.assertEqual(inspect.step, "inspect")
        self.assertIn("show-portfolio-run", inspect.command or "")
        self.assertEqual(data_trust.step, "data_trust")
        self.assertIn("summarize-portfolio-data-trust", data_trust.command or "")
        self.assertEqual(summarize.step, "summarize")
        self.assertIn("summarize-portfolio-experiment", summarize.command or "")
        self.assertEqual(robustness_review.step, "portfolio_robustness_review")
        self.assertIn("portfolio-run", robustness_review.command or "")
        self.assertEqual(variants.step, "variants")
        self.assertIn("portfolio-variants", variants.command or "")
        self.assertEqual(compare.step, "compare")
        self.assertIn("compare-portfolio-runs", compare.command or "")
        self.assertEqual(batch_plan.step, "batch_plan")
        self.assertIn("portfolio-batch plan", batch_plan.command or "")
        self.assertEqual(batch_run.step, "batch_run")
        self.assertIn("portfolio-batch run", batch_run.command or "")
        self.assertEqual(batch_summarize.step, "batch_summarize")
        self.assertIn("portfolio-batch summarize", batch_summarize.command or "")
        self.assertEqual(done.step, "done")
        self.assertIsNone(done.command)

    def test_command_builders_quote_paths(self) -> None:
        plan = create_portfolio_research_plan(
            title="QQQ SPY check",
            hypothesis="A 60/40 allocation may beat SPY.",
            portfolio_path="data/portfolios/qqq_spy_static_60_40.json",
            experiment_id="EXP-001",
            output_dir="artifacts/research/qqq spy",
            created_at_utc="2026-07-18T00:00:00Z",
        )

        baseline_command = build_portfolio_baseline_command_from_plan(plan)
        compare_command = build_compare_portfolio_runs_command(["first path/metadata.json", "second/metadata.json"])
        data_trust_command = build_portfolio_data_trust_command("first path/portfolio_metadata.json")
        summarize_command = build_portfolio_summarize_command_from_plan(plan)
        variants_command = build_portfolio_variants_command_from_plan(plan)
        batch_plan_command = build_portfolio_batch_plan_command_from_plan(plan)

        self.assertIn("'artifacts/research/qqq spy/baseline'", baseline_command)
        self.assertIn("'first path/metadata.json'", compare_command)
        self.assertIn("'first path/portfolio_metadata.json'", data_trust_command)
        self.assertIn("'artifacts/research/qqq spy/portfolio_summary.md'", summarize_command)
        self.assertIn("portfolio-variants", variants_command)
        self.assertIn("'artifacts/research/qqq spy/portfolio_batch'", batch_plan_command)

    def test_render_portfolio_research_plan_markdown_handles_empty_tags(self) -> None:
        plan = create_portfolio_research_plan(
            title="QQQ SPY check",
            hypothesis="A 60/40 allocation may beat SPY.",
            portfolio_path="data/portfolios/qqq_spy_static_60_40.json",
            experiment_id="EXP-001",
            output_dir="artifacts/research/qqq_spy_static_60_40",
            created_at_utc="2026-07-18T00:00:00Z",
        )

        markdown = render_portfolio_research_plan_markdown(plan)

        self.assertIn("## Tags\n\n- none", markdown)


if __name__ == "__main__":
    unittest.main()
