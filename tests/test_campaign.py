from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.campaign import (  # noqa: E402
    CAMPAIGN_CONFIG_FILENAME,
    CAMPAIGN_STATE_FILENAME,
    CAMPAIGN_STATE_MARKDOWN_FILENAME,
    initialize_campaign,
    load_campaign_config,
    load_campaign_state,
    parse_campaign_config,
)
from quant_lab.campaign_proposal import (  # noqa: E402
    deterministic_campaign_proposal,
    parse_campaign_proposal,
    projected_run_count,
    validate_campaign_proposal,
)
from quant_lab.cli import main  # noqa: E402


def campaign_payload() -> dict:
    return {
        "schema_version": "campaign_config.v1",
        "title": "SPY drawdown-control research",
        "objective": "Find simple SPY drawdown controls that retain most long-term growth.",
        "allowed_symbols": ["spy"],
        "allowed_templates": ["sma-long-cash", "ema-trend-follow"],
        "benchmark": "buy-and-hold",
        "data_paths": {"SPY": "data/cache/SPY_2015-01-01_2025-12-31.csv"},
        "cost_preset": "retail-liquid",
        "max_cycles": 3,
        "max_total_runs": 20,
        "max_variants_per_experiment": 3,
        "duration_minutes": 30,
        "provider": "deterministic",
    }


class CampaignTests(unittest.TestCase):
    def test_parse_campaign_config_normalizes_symbols_and_budgets(self) -> None:
        config = parse_campaign_config(campaign_payload())

        self.assertEqual(config.allowed_symbols, ["SPY"])
        self.assertEqual(config.data_paths["SPY"], "data/cache/SPY_2015-01-01_2025-12-31.csv")
        self.assertEqual(config.max_cycles, 3)
        self.assertEqual(config.provider, "deterministic")

    def test_parse_campaign_config_rejects_missing_symbol_data_path(self) -> None:
        payload = campaign_payload()
        payload["data_paths"] = {}

        with self.assertRaisesRegex(ValueError, "data_paths missing"):
            parse_campaign_config(payload)

    def test_initialize_campaign_writes_state_and_markdown(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            markdown = Path(paths.state_markdown_path).read_text(encoding="utf-8")

        self.assertEqual(Path(paths.config_path).name, CAMPAIGN_CONFIG_FILENAME)
        self.assertEqual(Path(paths.state_path).name, CAMPAIGN_STATE_FILENAME)
        self.assertEqual(Path(paths.state_markdown_path).name, CAMPAIGN_STATE_MARKDOWN_FILENAME)
        self.assertEqual(state.status, "running")
        self.assertEqual(state.remaining_budget["cycles"], 3)
        self.assertEqual(state.remaining_budget["runs"], 20)
        self.assertIn("What Are We Trying To Learn?", markdown)
        self.assertIn("SPY drawdown-control research", markdown)

    def test_campaign_init_and_status_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(campaign_payload()), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as init_stdout:
                init_exit = main(["campaign", "init", "--config", str(config_path), "--out", str(out_dir)])
            with contextlib.redirect_stdout(io.StringIO()) as status_stdout:
                status_exit = main(["campaign", "status", "--campaign", str(out_dir)])

            loaded = load_campaign_config(out_dir / CAMPAIGN_CONFIG_FILENAME)

        self.assertEqual(init_exit, 0)
        self.assertEqual(status_exit, 0)
        self.assertEqual(loaded.title, "SPY drawdown-control research")
        self.assertIn("Campaign initialized", init_stdout.getvalue())
        self.assertIn("Campaign Status", status_stdout.getvalue())
        self.assertIn("Runs used: 0/20", status_stdout.getvalue())

    def test_deterministic_campaign_proposal_validates_against_budget(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)

        proposal = deterministic_campaign_proposal(config, state)
        validation = validate_campaign_proposal(proposal, config=config, state=state)

        self.assertEqual(proposal.action, "run_experiment")
        self.assertEqual(proposal.strategy_template, "sma-long-cash")
        self.assertEqual(proposal.symbol, "SPY")
        self.assertEqual(projected_run_count(proposal), 11)
        self.assertTrue(validation.valid)
        self.assertEqual(validation.projected_run_count, 11)

    def test_campaign_proposal_rejects_unsupported_template_parameter(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)

        proposal = parse_campaign_proposal(
            {
                "schema_version": "campaign_proposal.v1",
                "action": "run_experiment",
                "title": "Bad parameter test",
                "hypothesis": "A bad parameter should be rejected before execution.",
                "rationale": "Validator check.",
                "difference_from_prior_work": "Uses unsupported parameter.",
                "strategy_template": "sma-long-cash",
                "symbol": "SPY",
                "parameters": {"not_supported": 1},
                "success_criteria": {"minimum_cagr_retention": 0.8},
                "validation_plan": {"train_test": True},
            }
        )
        validation = validate_campaign_proposal(proposal, config=config, state=state)

        self.assertFalse(validation.valid)
        self.assertTrue(any("unsupported parameters" in reason for reason in validation.reasons))

    def test_campaign_run_writes_validation_only_cycle_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(campaign_payload()), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "campaign",
                        "run",
                        "--config",
                        str(config_path),
                        "--out",
                        str(out_dir),
                    ]
                )

            proposal_path = out_dir / "cycles" / "cycle_001" / "proposal.json"
            validation_path = out_dir / "cycles" / "cycle_001" / "proposal_validation.json"
            proposal_exists = proposal_path.exists()
            validation_exists = validation_path.exists()
            validation = json.loads(validation_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertTrue(proposal_exists)
        self.assertTrue(validation_exists)
        self.assertTrue(validation["valid"])
        self.assertIn("execution: skipped", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
