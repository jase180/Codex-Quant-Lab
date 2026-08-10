from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.opportunity_theses import (
    find_opportunity_for_strategy_family,
    load_opportunity_catalog,
    validate_opportunity_thesis,
)


def _opportunity_thesis(**overrides) -> dict:
    payload = {
        "schema_version": "opportunity_thesis.v1",
        "thesis_id": "testable_pullback_liquidity",
        "title": "Testable Pullback Liquidity",
        "market_niche": "Liquid ETFs after short-term downside pressure.",
        "universe": ["SPY", "QQQ"],
        "phenomenon": "Temporary selling pressure may revert.",
        "counterparty_or_forced_actor": "Volatility-sensitive sellers.",
        "why_edge_might_exist": "Urgent liquidity demand may temporarily depress prices.",
        "why_large_funds_might_ignore_it": "The edge may be small, turnover-heavy, and capacity-limited.",
        "institutional_constraint_evidence": {
            "expected_daily_dollar_volume": "varies",
            "estimated_position_size": "unknown",
            "estimated_strategy_capacity": "unknown",
            "number_of_opportunities_per_year": "unknown",
            "estimated_absolute_pnl_at_capacity": "unknown",
            "evidence_quality": "unknown",
        },
        "expected_capacity": "Unknown until universe liquidity is measured.",
        "expected_holding_period": "Days to weeks.",
        "execution_constraints": ["next-open fills", "realistic costs"],
        "persistence_mechanism": "Liquidity shocks can recur.",
        "crowding_risk": "Medium.",
        "edge_decay_trigger": "No effect after costs across multiple regimes.",
        "observable_prediction": "Pullback rules should improve Sharpe after costs.",
        "falsification_tests": ["Reject if Sharpe does not improve after costs."],
        "required_project_capabilities": ["RSI indicator", "cost sensitivity"],
        "compatible_strategy_families": ["mean_reversion"],
        "suggested_validation": ["Use one prespecified threshold pair."],
        "references": ["Fixture reference"],
        "engine_fit": "ready",
        "rubric": {
            "structural_plausibility": "weak",
            "small_capital_advantage": "pass",
            "falsifiability": "pass",
            "deployability": "pass",
            "engine_fit": "ready",
        },
        "decision": "test_now",
    }
    payload.update(overrides)
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


class OpportunityThesesTest(unittest.TestCase):
    def test_tracked_opportunity_catalog_is_valid(self) -> None:
        catalog_dir = Path(__file__).resolve().parents[1] / "data" / "opportunity_catalog"

        theses = load_opportunity_catalog(catalog_dir)

        self.assertGreaterEqual(len(theses), 3)
        self.assertTrue(any(thesis.decision == "test_now" for thesis in theses))
        self.assertTrue(any(thesis.engine_fit == "blocked" for thesis in theses))

    def test_load_opportunity_catalog_requires_mechanism_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir)
            _write_json(catalog_dir / "pullback.json", _opportunity_thesis())

            theses = load_opportunity_catalog(catalog_dir)

        self.assertEqual(1, len(theses))
        self.assertEqual("testable_pullback_liquidity", theses[0].thesis_id)
        self.assertEqual(["mean_reversion"], theses[0].compatible_strategy_families)

    def test_validate_rejects_fake_rubric_values(self) -> None:
        payload = _opportunity_thesis(rubric={**_opportunity_thesis()["rubric"], "engine_fit": "pretty_good"})

        with self.assertRaisesRegex(ValueError, "rubric.engine_fit"):
            validate_opportunity_thesis(payload)

    def test_find_opportunity_for_strategy_family_only_returns_testable_ready_thesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir)
            _write_json(catalog_dir / "ready.json", _opportunity_thesis(thesis_id="ready", decision="test_now"))
            _write_json(
                catalog_dir / "blocked.json",
                _opportunity_thesis(
                    thesis_id="blocked",
                    engine_fit="blocked",
                    rubric={**_opportunity_thesis()["rubric"], "engine_fit": "blocked", "deployability": "blocked"},
                    decision="investigate_data",
                ),
            )
            theses = load_opportunity_catalog(catalog_dir)

        selected = find_opportunity_for_strategy_family(theses, "mean_reversion")

        self.assertIsNotNone(selected)
        self.assertEqual("ready", selected.thesis_id)


if __name__ == "__main__":
    unittest.main()
