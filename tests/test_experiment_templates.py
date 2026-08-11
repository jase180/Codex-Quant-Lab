from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.experiment_templates import (
    find_parameter_neighborhood,
    load_experiment_template_catalog,
    load_parameter_neighborhood_catalog,
    validate_experiment_template,
    validate_parameter_neighborhood,
)


def _experiment_template(**overrides) -> dict:
    payload = {
        "schema_version": "experiment_template.v1",
        "template_id": "test_sma_template",
        "title": "Test SMA Template",
        "strategy_family": "trend_following",
        "rationale": "Tests a simple trend state.",
        "tests_claim": "A simple trend state may reduce drawdown.",
        "supported_universe": ["single_liquid_etf"],
        "required_project_capabilities": ["SMA indicator", "next-open fills"],
        "executable_mapping": {
            "campaign_strategy_template": "sma-long-cash",
            "parameter_map": {"lookback": "sma_length"},
        },
        "default_validation_plan": {
            "cost_sensitivity": True,
            "date_sensitivity": True,
            "train_test": True,
        },
        "parameter_neighborhood_id": "test_neighborhood",
        "expected_information_gain": "medium",
        "parameter_mining_risk": "low",
        "known_limitations": ["Fixture limitation."],
        "engine_support_status": "ready",
    }
    payload.update(overrides)
    return payload


def _parameter_neighborhood(**overrides) -> dict:
    payload = {
        "schema_version": "parameter_neighborhood.v1",
        "neighborhood_id": "test_neighborhood",
        "title": "Test Neighborhood",
        "rationale": "Small fixture parameter set.",
        "parameters": {"lookback": [100, 200]},
        "max_variants": 2,
        "selection_rule": "Use all fixture values.",
    }
    payload.update(overrides)
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


class ExperimentTemplateCatalogTest(unittest.TestCase):
    def test_tracked_catalogs_are_valid_and_link_to_neighborhoods(self) -> None:
        root = Path(__file__).resolve().parents[1]
        templates = load_experiment_template_catalog(root / "data" / "experiment_template_catalog")
        neighborhoods = load_parameter_neighborhood_catalog(root / "data" / "parameter_neighborhoods")
        neighborhood_ids = {item.neighborhood_id for item in neighborhoods}

        self.assertGreaterEqual(len(templates), 2)
        self.assertGreaterEqual(len(neighborhoods), 2)
        self.assertTrue(all(template.engine_support_status == "ready" for template in templates))
        self.assertTrue(all(template.parameter_neighborhood_id in neighborhood_ids for template in templates))
        self.assertTrue(any(template.campaign_strategy_template == "sma-long-cash" for template in templates))
        self.assertTrue(any(template.campaign_strategy_template == "ema-trend-follow" for template in templates))

    def test_load_experiment_template_catalog_requires_strict_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir)
            _write_json(catalog_dir / "template.json", _experiment_template())

            templates = load_experiment_template_catalog(catalog_dir)

        self.assertEqual(1, len(templates))
        self.assertEqual("test_sma_template", templates[0].template_id)
        self.assertEqual("trend_following", templates[0].strategy_family)
        self.assertEqual("sma-long-cash", templates[0].campaign_strategy_template)

    def test_validate_template_rejects_unsupported_mining_risk(self) -> None:
        payload = _experiment_template(parameter_mining_risk="spicy")

        with self.assertRaisesRegex(ValueError, "parameter_mining_risk"):
            validate_experiment_template(payload)

    def test_validate_template_rejects_unknown_fields(self) -> None:
        payload = _experiment_template(extra_field=True)

        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            validate_experiment_template(payload)

    def test_validate_template_rejects_unsupported_campaign_parameter_mapping(self) -> None:
        payload = _experiment_template(
            executable_mapping={
                "campaign_strategy_template": "sma-long-cash",
                "parameter_map": {"lookback": "not_supported"},
            }
        )

        with self.assertRaisesRegex(ValueError, "unsupported campaign parameters"):
            validate_experiment_template(payload)

    def test_load_parameter_neighborhood_catalog_requires_strict_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir)
            _write_json(catalog_dir / "neighborhood.json", _parameter_neighborhood())

            neighborhoods = load_parameter_neighborhood_catalog(catalog_dir)

        self.assertEqual(1, len(neighborhoods))
        self.assertEqual("test_neighborhood", neighborhoods[0].neighborhood_id)
        self.assertEqual({"lookback": [100, 200]}, neighborhoods[0].parameters)
        self.assertEqual(2, neighborhoods[0].max_variants)

    def test_validate_neighborhood_rejects_empty_parameter_values(self) -> None:
        payload = _parameter_neighborhood(parameters={"lookback": []})

        with self.assertRaisesRegex(ValueError, "non-empty list"):
            validate_parameter_neighborhood(payload)

    def test_find_parameter_neighborhood_returns_matching_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir)
            _write_json(catalog_dir / "neighborhood.json", _parameter_neighborhood())
            neighborhoods = load_parameter_neighborhood_catalog(catalog_dir)

        selected = find_parameter_neighborhood(neighborhoods, "test_neighborhood")

        self.assertIsNotNone(selected)
        self.assertEqual("test_neighborhood", selected.neighborhood_id)
        self.assertIsNone(find_parameter_neighborhood(neighborhoods, "missing"))


if __name__ == "__main__":
    unittest.main()
