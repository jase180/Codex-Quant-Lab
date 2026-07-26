import unittest

from quant_lab.experiment_conclusion import (
    AGENT_INSTRUCTIONS,
    EXPERIMENT_CONCLUSION_SCHEMA_VERSION,
    MARKDOWN_SECTION_ORDER,
    build_experiment_conclusion,
    format_agent_context,
    format_experiment_conclusion_markdown,
)
from quant_lab.research_registry import EXPERIMENT_SCHEMA_VERSION, ExperimentRecord


def _experiment(linked_runs=None):
    return ExperimentRecord(
        experiment_schema_version=EXPERIMENT_SCHEMA_VERSION,
        experiment_id="EXP-001",
        created_at_utc="2026-07-25T00:00:00Z",
        title="SPY trend trust check",
        hypothesis="A simple SPY trend rule may reduce drawdown without trailing buy-and-hold too much.",
        status="running",
        tags=["spy", "trend"],
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
                "confidence_label",
                "current_conclusion",
                "supporting_evidence",
                "contradicting_evidence",
                "robustness_notes",
                "do_not_repeat",
                "next_useful_tests",
                "open_questions",
                "source_artifacts",
                "agent_instructions",
            ],
            list(conclusion.to_dict().keys()),
        )

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
        last_index = -1
        for section in MARKDOWN_SECTION_ORDER:
            section_index = markdown.index(section)
            self.assertGreater(section_index, last_index)
            last_index = section_index

        agent_context = format_agent_context(conclusion)
        self.assertIn("experiment_conclusion.json", agent_context)
        self.assertIn(conclusion.current_conclusion, agent_context)
        for instruction in AGENT_INSTRUCTIONS:
            self.assertIn(instruction, agent_context)


if __name__ == "__main__":
    unittest.main()
