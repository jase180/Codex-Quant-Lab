from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.cli import main
from quant_lab.discovery_map import build_discovery_map, format_discovery_map
from quant_lab.research_mechanisms import (
    find_research_mechanism,
    format_research_mechanism_data_needs,
    format_research_mechanism_detail,
    format_research_mechanism_list,
    load_research_mechanisms,
    validate_research_mechanism,
)


def valid_mechanism_payload() -> dict:
    return {
        "schema_version": "research_mechanism.v1",
        "mechanism_id": "test_mechanism",
        "title": "Test Mechanism",
        "source_type": "manual",
        "market_behavior": "A testable market behavior.",
        "forced_actor": "A forced actor.",
        "why_edge_might_exist": "A structural reason.",
        "why_large_capital_may_ignore_it": "A capacity or friction reason.",
        "capacity_hypothesis": "A bounded capacity hypothesis.",
        "data_required": ["daily OHLCV"],
        "observable_predictions": ["Prediction before looking at results."],
        "falsification_tests": ["Reject when the prediction fails."],
        "engine_fit": "proxy_only",
        "suggested_opportunity_theses": ["test_thesis"],
        "references": ["Manual seed record"],
    }


class ResearchMechanismsTest(unittest.TestCase):
    def test_load_research_mechanism_catalog(self) -> None:
        mechanisms = load_research_mechanisms("data/research_mechanisms")

        mechanism_ids = {mechanism.mechanism_id for mechanism in mechanisms}

        self.assertGreaterEqual(len(mechanisms), 7)
        self.assertIn("forced_index_flows", mechanism_ids)
        self.assertIn("etf_flow_pressure", mechanism_ids)
        self.assertIn("cross_sectional_relative_strength", mechanism_ids)

    def test_validate_research_mechanism_rejects_missing_forced_actor(self) -> None:
        payload = valid_mechanism_payload()
        payload.pop("forced_actor")

        with self.assertRaisesRegex(ValueError, "forced_actor"):
            validate_research_mechanism(payload)

    def test_validate_research_mechanism_rejects_unsupported_engine_fit(self) -> None:
        payload = valid_mechanism_payload()
        payload["engine_fit"] = "magic"

        with self.assertRaisesRegex(ValueError, "engine_fit"):
            validate_research_mechanism(payload)

    def test_find_research_mechanism_by_id(self) -> None:
        mechanisms = load_research_mechanisms("data/research_mechanisms")

        mechanism = find_research_mechanism(mechanisms, "etf_flow_pressure")

        self.assertIsNotNone(mechanism)
        self.assertEqual("ETF Flow Pressure", mechanism.title)

    def test_format_research_mechanism_outputs_catalog_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test_mechanism.json"
            path.write_text(json.dumps(valid_mechanism_payload()), encoding="utf-8")
            mechanism = load_research_mechanisms(temp_dir)[0]

        listing = format_research_mechanism_list([mechanism])
        detail = format_research_mechanism_detail(mechanism)

        self.assertIn("structured raw material", listing)
        self.assertIn("test_mechanism", listing)
        self.assertIn("Forced Actor", detail)
        self.assertIn("Falsification Tests", detail)

    def test_format_research_mechanism_data_needs_can_filter_engine_fit(self) -> None:
        mechanisms = load_research_mechanisms("data/research_mechanisms")

        output = format_research_mechanism_data_needs(mechanisms, engine_fit="needs_data")

        self.assertIn("Research Mechanism Data Needs", output)
        self.assertIn("Filter: engine_fit = `needs_data`", output)
        self.assertIn("Forced Index Flows", output)
        self.assertIn("historical index membership changes", output)
        self.assertNotIn("ETF Flow Pressure", output)

    def test_cli_mechanisms_list_prints_seed_catalog(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["mechanisms", "list"])

        output = stdout.getvalue()

        self.assertEqual(0, exit_code)
        self.assertIn("Research Mechanisms", output)
        self.assertIn("forced_index_flows", output)

    def test_cli_mechanisms_show_prints_one_record(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["mechanisms", "show", "--id", "etf_flow_pressure"])

        output = stdout.getvalue()

        self.assertEqual(0, exit_code)
        self.assertIn("Research Mechanism: ETF Flow Pressure", output)
        self.assertIn("Observable Predictions", output)

    def test_cli_mechanisms_show_returns_error_for_unknown_id(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["mechanisms", "show", "--id", "missing"])

        output = stdout.getvalue()

        self.assertEqual(1, exit_code)
        self.assertIn("No research mechanism found", output)

    def test_cli_mechanisms_data_needs_prints_filtered_requirements(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["mechanisms", "data-needs", "--engine-fit", "needs_data"])

        output = stdout.getvalue()

        self.assertEqual(0, exit_code)
        self.assertIn("Research Mechanism Data Needs", output)
        self.assertIn("Tax-Loss Selling Pressure", output)
        self.assertIn("survivorship-aware equity universe", output)
        self.assertNotIn("ETF Flow Pressure", output)

    def test_discovery_map_joins_mechanisms_theses_datasets_and_templates(self) -> None:
        entries = build_discovery_map()
        by_id = {entry.mechanism_id: entry for entry in entries}

        self.assertIn("calendar_rebalance_effects", by_id)
        self.assertIn("forced_index_flows", by_id)
        self.assertEqual("testable_now", by_id["calendar_rebalance_effects"].disposition)
        self.assertIn("calendar_month_end_window", by_id["calendar_rebalance_effects"].ready_template_ids)
        self.assertEqual("proxy_testable", by_id["small_cap_liquidity_shocks"].disposition)
        self.assertEqual("needs_data", by_id["forced_index_flows"].disposition)
        self.assertIn("forced_event_liquidity", by_id["forced_index_flows"].opportunity_theses)

    def test_format_discovery_map_names_ready_and_blocked_work(self) -> None:
        output = format_discovery_map(build_discovery_map())

        self.assertIn("# Discovery Map", output)
        self.assertIn("calendar_rebalance_effects", output)
        self.assertIn("calendar_month_end_window", output)
        self.assertIn("forced_index_flows", output)
        self.assertIn("proxy_testable", output)
        self.assertIn("needs_data", output)

    def test_cli_mechanisms_map_prints_discovery_readiness(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["mechanisms", "map"])

        output = stdout.getvalue()

        self.assertEqual(0, exit_code)
        self.assertIn("Discovery Map", output)
        self.assertIn("testable_now", output)
        self.assertIn("needs_data", output)


if __name__ == "__main__":
    unittest.main()
