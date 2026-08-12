import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.experiment_conclusion import (
    AGENT_INSTRUCTIONS,
    EXPERIMENT_CONCLUSION_SCHEMA_VERSION,
    MARKDOWN_SECTION_ORDER,
    build_experiment_conclusion,
    format_agent_context,
    format_experiment_conclusion_markdown,
)
from quant_lab.research_plan import InvestmentObjective, SuccessCriterion
from quant_lab.research_registry import EXPERIMENT_SCHEMA_VERSION, ExperimentRecord


def _experiment(linked_runs=None, tags=None):
    return ExperimentRecord(
        experiment_schema_version=EXPERIMENT_SCHEMA_VERSION,
        experiment_id="EXP-001",
        created_at_utc="2026-07-25T00:00:00Z",
        title="SPY trend trust check",
        hypothesis="A simple SPY trend rule may reduce drawdown without trailing buy-and-hold too much.",
        status="running",
        tags=list(tags or ["spy", "trend"]),
        strategy_path="data/strategies/spy_trend.json",
        data_path="data/cache/SPY.csv",
        linked_runs=list(linked_runs or []),
        decision=None,
        decision_record=None,
        notes=None,
    )


def _index_record(
    *,
    run_id,
    run_type,
    excess_total_return,
    metadata_path,
    experiment_id="EXP-001",
    trade_count=12,
    created_at_utc="2026-07-25T00:00:00Z",
):
    return {
        "experiment_id": experiment_id,
        "created_at_utc": created_at_utc,
        "run_id": run_id,
        "run_type": run_type,
        "excess_total_return": excess_total_return,
        "trade_count": trade_count,
        "metadata_path": metadata_path,
        "output_dir": metadata_path.rsplit("/", 1)[0],
    }


class ExperimentConclusionTest(unittest.TestCase):
    def test_builds_no_evidence_conclusion_with_agent_instructions(self):
        conclusion = build_experiment_conclusion(
            _experiment(),
            [],
            generated_at_utc="2026-07-25T12:00:00Z",
            generator_version="test",
        )

        self.assertEqual(EXPERIMENT_CONCLUSION_SCHEMA_VERSION, conclusion.schema_version)
        self.assertEqual("no_evidence", conclusion.confidence_label)
        self.assertIn("No linked evidence exists yet", conclusion.current_conclusion)
        self.assertEqual("Run the first baseline.", conclusion.next_useful_tests[0].test)
        self.assertIn("Read experiment_conclusion.json before scanning raw artifacts.", conclusion.agent_instructions)

    def test_to_dict_uses_stable_top_level_keys(self):
        conclusion = build_experiment_conclusion(
            _experiment(),
            [],
            generated_at_utc="2026-07-25T12:00:00Z",
        )

        self.assertEqual(
            [
                "schema_version",
                "experiment_id",
                "generated_at_utc",
                "generator",
                "experiment",
                "research_system_status",
                "strategy_hypothesis_status",
                "thesis_status",
                "confidence_label",
                "current_conclusion",
                "supporting_evidence",
                "contradicting_evidence",
                "robustness_notes",
                "do_not_repeat",
                "next_useful_tests",
                "open_questions",
                "source_artifacts",
                "next_research_prompt",
                "agent_instructions",
            ],
            list(conclusion.to_dict().keys()),
        )

    def test_distinguishes_valid_research_system_from_rejected_strategy(self):
        records = [
            _index_record(
                run_id="test_selected",
                run_type="test_selected_run",
                excess_total_return=-0.57,
                metadata_path="artifacts/research/spy/test_selected/run_metadata.json",
                created_at_utc="2026-07-25T01:00:00Z",
            )
            | {
                "data_start": "2021-01-04",
                "data_end": "2025-12-30",
                "benchmark_name": "buy-and-hold",
                "cost_preset": "retail-liquid",
                "sizing": "percent-equity",
                "cagr": 0.07,
                "benchmark_cagr": 0.10,
                "max_drawdown": -0.20,
                "benchmark_max_drawdown": -0.30,
            },
            _index_record(
                run_id="cost_check",
                run_type="cost_sensitivity_run",
                excess_total_return=-0.60,
                metadata_path="artifacts/research/spy/cost/run_metadata.json",
            ),
            _index_record(
                run_id="date_check",
                run_type="date_sensitivity_run",
                excess_total_return=-0.50,
                metadata_path="artifacts/research/spy/date/run_metadata.json",
            ),
            _index_record(
                run_id="benchmark_check",
                run_type="benchmark_sensitivity_run",
                excess_total_return=-0.55,
                metadata_path="artifacts/research/spy/benchmark/run_metadata.json",
            ),
        ]
        objective = InvestmentObjective(
            intended_benefit="lower drawdown with acceptable return retention",
            benchmark="buy-and-hold",
            primary_metric="max_drawdown",
            minimum_acceptable_performance="Retain 80% of benchmark CAGR and reduce max drawdown by 25%.",
            important_tradeoffs=["May lag raw SPY total return."],
            success_criteria=[
                SuccessCriterion(
                    name="return_retention",
                    metric="cagr",
                    comparison="strategy_vs_benchmark_ratio",
                    operator=">=",
                    threshold=0.8,
                ),
                SuccessCriterion(
                    name="drawdown_reduction",
                    metric="max_drawdown",
                    comparison="relative_reduction_vs_benchmark",
                    operator=">=",
                    threshold=0.25,
                ),
            ],
        )

        conclusion = build_experiment_conclusion(_experiment(), records, investment_objective=objective)
        markdown = format_experiment_conclusion_markdown(conclusion)

        self.assertEqual("valid", conclusion.research_system_status.status)
        self.assertEqual("partially_supported", conclusion.strategy_hypothesis_status.status)
        self.assertIn("## Research-System Status", markdown)
        self.assertIn("## Strategy-Hypothesis Status", markdown)
        self.assertIn("## Opportunity-Thesis Status", markdown)
        self.assertIn("`return_retention`: `fail`", markdown)
        self.assertIn("`drawdown_reduction`: `pass`", markdown)

    def test_opportunity_thesis_status_weakens_on_rejected_linked_strategy(self):
        records = [
            _index_record(
                run_id="test_selected",
                run_type="test_selected_run",
                excess_total_return=-0.57,
                metadata_path="artifacts/research/spy/test_selected/run_metadata.json",
            )
            | {
                "data_start": "2021-01-04",
                "data_end": "2025-12-30",
                "benchmark_name": "buy-and-hold",
                "cost_preset": "retail-liquid",
                "sizing": "percent-equity",
                "cagr": 0.04,
                "benchmark_cagr": 0.10,
            },
            _index_record(
                run_id="cost_check",
                run_type="cost_sensitivity_run",
                excess_total_return=-0.60,
                metadata_path="artifacts/research/spy/cost/run_metadata.json",
            ),
            _index_record(
                run_id="date_check",
                run_type="date_sensitivity_run",
                excess_total_return=-0.50,
                metadata_path="artifacts/research/spy/date/run_metadata.json",
            ),
            _index_record(
                run_id="benchmark_check",
                run_type="benchmark_sensitivity_run",
                excess_total_return=-0.55,
                metadata_path="artifacts/research/spy/benchmark/run_metadata.json",
            ),
        ]
        objective = InvestmentObjective(
            intended_benefit="return retention",
            benchmark="buy-and-hold",
            primary_metric="cagr",
            minimum_acceptable_performance="Retain 80% of benchmark CAGR.",
            success_criteria=[
                SuccessCriterion(
                    name="return_retention",
                    metric="cagr",
                    comparison="strategy_vs_benchmark_ratio",
                    operator=">=",
                    threshold=0.8,
                )
            ],
        )

        conclusion = build_experiment_conclusion(
            _experiment(tags=["campaign", "opportunity:liquid_etf_trend_defense"]),
            records,
            investment_objective=objective,
        )
        markdown = format_experiment_conclusion_markdown(conclusion)
        agent_context = format_agent_context(conclusion)

        self.assertEqual("rejected", conclusion.strategy_hypothesis_status.status)
        self.assertEqual("liquid_etf_trend_defense", conclusion.thesis_status.opportunity_thesis_id)
        self.assertEqual("weakened", conclusion.thesis_status.status)
        self.assertIn("does not fully reject", conclusion.thesis_status.reason)
        self.assertIn("- Status: `weakened`", markdown)
        self.assertIn("Opportunity-thesis status: `weakened`", agent_context)
        self.assertIn("Opportunity-thesis status: weakened", conclusion.next_research_prompt.known_result)
        self.assertTrue(
            any("liquid_etf_trend_defense" in item for item in conclusion.next_research_prompt.constraints)
        )

    def test_experiment_snapshot_extracts_campaign_strategy_template_tag(self):
        conclusion = build_experiment_conclusion(
            _experiment(tags=["campaign", "opportunity:liquid_etf_trend_defense", "template:sma-long-cash"]),
            [],
            generated_at_utc="2026-07-25T12:00:00Z",
        )
        markdown = format_experiment_conclusion_markdown(conclusion)

        self.assertEqual("sma-long-cash", conclusion.experiment.strategy_template)
        self.assertEqual("sma-long-cash", conclusion.to_dict()["experiment"]["strategy_template"])
        self.assertIn("Strategy template: `sma-long-cash`", markdown)

    def test_strategy_status_downgrades_when_criteria_pass_but_robustness_fails(self):
        records = [
            _index_record(
                run_id="test_selected",
                run_type="test_selected_run",
                excess_total_return=0.01,
                metadata_path="artifacts/research/eem/test_selected/run_metadata.json",
            )
            | {
                "data_start": "2021-01-04",
                "data_end": "2025-12-30",
                "benchmark_name": "buy-and-hold",
                "cost_preset": "retail-liquid",
                "sizing": "percent-equity",
                "cagr": 0.106,
                "benchmark_cagr": 0.10,
                "max_drawdown": -0.15,
                "benchmark_max_drawdown": -0.30,
            },
            _index_record(
                run_id="cost_check",
                run_type="cost_sensitivity_run",
                excess_total_return=-0.48,
                metadata_path="artifacts/research/eem/cost/run_metadata.json",
            ),
            _index_record(
                run_id="date_check",
                run_type="date_sensitivity_run",
                excess_total_return=-0.35,
                metadata_path="artifacts/research/eem/date/run_metadata.json",
            ),
            _index_record(
                run_id="benchmark_check",
                run_type="benchmark_sensitivity_run",
                excess_total_return=-0.10,
                metadata_path="artifacts/research/eem/benchmark/run_metadata.json",
            ),
        ]
        objective = InvestmentObjective(
            intended_benefit="lower drawdown with acceptable return retention",
            benchmark="buy-and-hold",
            primary_metric="max_drawdown",
            minimum_acceptable_performance="Retain 80% of benchmark CAGR and reduce max drawdown by 25%.",
            success_criteria=[
                SuccessCriterion(
                    name="return_retention",
                    metric="cagr",
                    comparison="strategy_vs_benchmark_ratio",
                    operator=">=",
                    threshold=0.8,
                ),
                SuccessCriterion(
                    name="drawdown_reduction",
                    metric="max_drawdown",
                    comparison="relative_reduction_vs_benchmark",
                    operator=">=",
                    threshold=0.25,
                ),
            ],
        )

        conclusion = build_experiment_conclusion(
            _experiment(tags=["campaign", "opportunity:liquid_etf_trend_defense"]),
            records,
            investment_objective=objective,
        )

        self.assertEqual("partially_supported", conclusion.strategy_hypothesis_status.status)
        self.assertIn("robustness", conclusion.strategy_hypothesis_status.summary)
        self.assertEqual("weakened", conclusion.thesis_status.status)

    def test_strategy_status_can_derive_benchmark_cagr_from_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / "run_metadata.json"
            metadata_path.write_text(json.dumps({"data": {"row_count": 253}}), encoding="utf-8")
            records = [
                _index_record(
                    run_id="test_selected",
                    run_type="test_selected_run",
                    excess_total_return=-0.02,
                    metadata_path=str(metadata_path),
                )
                | {
                    "data_start": "2026-01-01",
                    "data_end": "2026-12-31",
                    "benchmark_name": "buy-and-hold",
                    "cost_preset": "retail-liquid",
                    "sizing": "percent-equity",
                    "cagr": 0.05,
                    "benchmark_total_return": 0.10,
                }
            ]
            objective = InvestmentObjective(
                intended_benefit="return retention",
                benchmark="buy-and-hold",
                primary_metric="cagr",
                minimum_acceptable_performance="Retain 80% of benchmark CAGR.",
                success_criteria=[
                    SuccessCriterion(
                        name="return_retention",
                        metric="cagr",
                        comparison="strategy_vs_benchmark_ratio",
                        operator=">=",
                        threshold=0.8,
                    )
                ],
            )

            conclusion = build_experiment_conclusion(_experiment(), records, investment_objective=objective)

        result = conclusion.strategy_hypothesis_status.criteria_results[0]
        self.assertFalse(result.passed)
        self.assertNotIn("Could not evaluate", result.observed)

    def test_strategy_status_evaluates_strategy_vs_benchmark_sharpe_delta(self):
        records = [
            _index_record(
                run_id="test_selected",
                run_type="test_selected_run",
                excess_total_return=-0.02,
                metadata_path="artifacts/research/spy/test_selected/run_metadata.json",
            )
            | {
                "data_start": "2026-01-01",
                "data_end": "2026-12-31",
                "benchmark_name": "buy-and-hold",
                "cost_preset": "retail-liquid",
                "sizing": "percent-equity",
                "sharpe_ratio": 0.8,
                "benchmark_sharpe_ratio": 0.5,
            }
        ]
        objective = InvestmentObjective(
            intended_benefit="improved risk-adjusted return",
            benchmark="buy-and-hold",
            primary_metric="sharpe",
            minimum_acceptable_performance="Improve Sharpe versus buy-and-hold.",
            success_criteria=[
                SuccessCriterion(
                    name="risk_adjusted_return",
                    metric="sharpe",
                    comparison="strategy_vs_benchmark_delta",
                    operator=">",
                    threshold=0.0,
                )
            ],
        )

        conclusion = build_experiment_conclusion(_experiment(), records, investment_objective=objective)

        result = conclusion.strategy_hypothesis_status.criteria_results[0]
        self.assertTrue(result.passed)
        self.assertEqual("0.3000", result.observed)

    def test_builds_mixed_conclusion_with_supporting_and_contradicting_evidence(self):
        records = [
            _index_record(
                run_id="test_selected",
                run_type="test_selected_run",
                excess_total_return=0.03,
                metadata_path="artifacts/research/spy/test_selected/run_metadata.json",
            ),
            _index_record(
                run_id="date_check",
                run_type="date_sensitivity_run",
                excess_total_return=-0.02,
                metadata_path="artifacts/research/spy/date_check/run_metadata.json",
                created_at_utc="2026-07-25T01:00:00Z",
            ),
        ]

        conclusion = build_experiment_conclusion(_experiment(), records)

        self.assertEqual("mixed", conclusion.confidence_label)
        self.assertEqual("test_selected", conclusion.supporting_evidence[0].run_id)
        self.assertEqual("date_check", conclusion.contradicting_evidence[0].run_id)
        self.assertIn("contradicting evidence", " ".join(conclusion.do_not_repeat))
        self.assertIn("The current evidence is mixed", conclusion.next_research_prompt.known_result)
        self.assertTrue(conclusion.next_research_prompt.what_appears_promising)
        self.assertTrue(conclusion.next_research_prompt.what_failed)
        self.assertTrue(any("Change only one" in item for item in conclusion.next_research_prompt.constraints))
        source_paths = [artifact.path for artifact in conclusion.source_artifacts]
        self.assertIn("artifacts/research/spy/test_selected/run_metadata.json", source_paths)
        self.assertIn("artifacts/research/spy/date_check/run_metadata.json", source_paths)

    def test_robustness_notes_detect_passed_failed_and_missing_checks(self):
        records = [
            _index_record(
                run_id="test_selected",
                run_type="test_selected_run",
                excess_total_return=0.04,
                metadata_path="artifacts/research/spy/test_selected/run_metadata.json",
            ),
            _index_record(
                run_id="cost_low",
                run_type="cost_sensitivity_run",
                excess_total_return=0.02,
                metadata_path="artifacts/research/spy/cost_low/run_metadata.json",
            ),
            _index_record(
                run_id="date_bad",
                run_type="date_sensitivity_run",
                excess_total_return=-0.01,
                metadata_path="artifacts/research/spy/date_bad/run_metadata.json",
            ),
        ]

        conclusion = build_experiment_conclusion(_experiment(), records)
        statuses = {note.check: note.status for note in conclusion.robustness_notes}

        self.assertEqual("passed", statuses["cost_sensitivity"])
        self.assertEqual("failed", statuses["date_sensitivity"])
        self.assertEqual("missing", statuses["benchmark_sensitivity"])
        self.assertIn("missing robustness checks", conclusion.next_useful_tests[0].test.lower())

    def test_rejected_conclusion_prioritizes_stop_or_reformulate(self):
        records = [
            _index_record(
                run_id="baseline",
                run_type="run",
                excess_total_return=-4.11,
                metadata_path="artifacts/research/spy/baseline/run_metadata.json",
                trade_count=51,
            ),
            _index_record(
                run_id="sweep_best",
                run_type="sweep_run",
                excess_total_return=-2.01,
                metadata_path="artifacts/research/spy/sweep/run_metadata.json",
                trade_count=11,
            ),
        ]

        conclusion = build_experiment_conclusion(_experiment(), records)

        self.assertEqual("rejected", conclusion.confidence_label)
        self.assertEqual(
            "Stop this branch or reformulate the hypothesis before running more tests.",
            conclusion.next_useful_tests[0].test,
        )
        next_test_names = [test.test for test in conclusion.next_useful_tests]
        self.assertNotIn("Run train/test or walk-forward validation.", next_test_names)
        self.assertFalse(any("missing robustness checks" in test.test.lower() for test in conclusion.next_useful_tests))

    def test_linked_run_paths_can_select_records_without_experiment_id(self):
        linked_path = "artifacts/research/spy/manual/run_metadata.json"
        records = [
            _index_record(
                run_id="manual",
                run_type="manual_review_run",
                excess_total_return=0.01,
                metadata_path=linked_path,
                experiment_id=None,
            )
        ]

        conclusion = build_experiment_conclusion(_experiment(linked_runs=[linked_path]), records)

        self.assertEqual("weak", conclusion.confidence_label)
        self.assertEqual("manual", conclusion.supporting_evidence[0].run_id)

    def test_markdown_and_agent_context_are_readable_and_ordered(self):
        conclusion = build_experiment_conclusion(
            _experiment(),
            [],
            generated_at_utc="2026-07-25T12:00:00Z",
        )

        markdown = format_experiment_conclusion_markdown(conclusion)
        self.assertIn("Report role: main source of truth.", markdown)
        last_index = -1
        for section in MARKDOWN_SECTION_ORDER:
            section_index = markdown.index(section)
            self.assertGreater(section_index, last_index)
            last_index = section_index

        agent_context = format_agent_context(conclusion)
        self.assertIn("experiment_conclusion.json", agent_context)
        self.assertIn(conclusion.current_conclusion, agent_context)
        self.assertIn("Next research prompt:", agent_context)
        self.assertIn("Next experiment should:", agent_context)
        for instruction in AGENT_INSTRUCTIONS:
            self.assertIn(instruction, agent_context)


if __name__ == "__main__":
    unittest.main()
