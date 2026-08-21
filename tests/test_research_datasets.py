from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.cli import main
from quant_lab.research_datasets import (
    dataset_plans_for_mechanism,
    format_dataset_plan_list,
    format_dataset_plans_for_mechanism,
    load_research_dataset_plans,
    validate_research_dataset_plan,
)


def valid_dataset_plan_payload() -> dict:
    return {
        "schema_version": "research_dataset_plan.v1",
        "dataset_id": "test_dataset",
        "mechanism_id": "calendar_rebalance_effects",
        "title": "Test Dataset",
        "status": "planned",
        "purpose": "Define a test dataset.",
        "data_grain": "daily",
        "required_fields": ["event_date"],
        "candidate_sources": ["manual fixture"],
        "construction_rules": ["Do not use returns to choose rows."],
        "quality_checks": ["event_date is present"],
        "minimum_viable_tests": ["event-study summary"],
        "known_limitations": ["fixture only"],
        "next_action": "Build fixture rows.",
    }


class ResearchDatasetsTest(unittest.TestCase):
    def test_load_research_dataset_plan_catalog(self) -> None:
        plans = load_research_dataset_plans("data/research_datasets")

        plan_ids = {plan.dataset_id for plan in plans}

        self.assertIn("calendar_rebalance_daily_proxy", plan_ids)
        self.assertIn("forced_index_membership_events", plan_ids)
        self.assertTrue(all(plan.status in {"planned", "available", "blocked"} for plan in plans))

    def test_validate_research_dataset_plan_rejects_missing_required_fields(self) -> None:
        payload = valid_dataset_plan_payload()
        payload.pop("quality_checks")

        with self.assertRaisesRegex(ValueError, "quality_checks"):
            validate_research_dataset_plan(payload)

    def test_dataset_plans_for_mechanism_filters_by_mechanism(self) -> None:
        plans = load_research_dataset_plans("data/research_datasets")

        matching = dataset_plans_for_mechanism(plans, "calendar_rebalance_effects")

        self.assertEqual(1, len(matching))
        self.assertEqual("calendar_rebalance_daily_proxy", matching[0].dataset_id)

        forced = dataset_plans_for_mechanism(plans, "forced_index_flows")
        self.assertEqual(1, len(forced))
        self.assertEqual("planned", forced[0].status)

    def test_format_dataset_plan_list_and_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dataset.json"
            path.write_text(json.dumps(valid_dataset_plan_payload()), encoding="utf-8")
            plans = load_research_dataset_plans(temp_dir)

        listing = format_dataset_plan_list(plans)
        detail = format_dataset_plans_for_mechanism("calendar_rebalance_effects", plans)

        self.assertIn("Research Dataset Plans", listing)
        self.assertIn("test_dataset", listing)
        self.assertIn("Required fields", detail)
        self.assertIn("Do not use returns", detail)

    def test_cli_mechanisms_data_plan_lists_all_plans(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["mechanisms", "data-plan"])

        output = stdout.getvalue()

        self.assertEqual(0, exit_code)
        self.assertIn("Research Dataset Plans", output)
        self.assertIn("calendar_rebalance_daily_proxy", output)
        self.assertIn("forced_index_membership_events", output)

    def test_cli_mechanisms_data_plan_shows_matching_plan(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["mechanisms", "data-plan", "--id", "calendar_rebalance_effects"])

        output = stdout.getvalue()

        self.assertEqual(0, exit_code)
        self.assertIn("Dataset Plans For Mechanism: calendar_rebalance_effects", output)
        self.assertIn("Calendar/Rebalance Daily Proxy", output)
        self.assertIn("generated_without_return_data", output)

    def test_cli_mechanisms_data_plan_shows_forced_index_plan(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["mechanisms", "data-plan", "--id", "forced_index_flows"])

        output = stdout.getvalue()

        self.assertEqual(0, exit_code)
        self.assertIn("Forced Index Membership Events", output)
        self.assertIn("announcement_date", output)
        self.assertIn("effective_date", output)


if __name__ == "__main__":
    unittest.main()
