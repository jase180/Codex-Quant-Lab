from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quant_lab.campaign import initialize_campaign, load_campaign_state, parse_campaign_config
from quant_lab.campaign_candidate_choice import (
    parse_campaign_candidate_choice,
    validate_campaign_candidate_choice,
)
from quant_lab.campaign_candidate_provider import campaign_candidate_provider_result
from quant_lab.campaign_candidates import build_campaign_candidate_menu, campaign_candidate_to_proposal
from quant_lab.campaign_proposal import validate_campaign_proposal
from quant_lab.cli import main


def campaign_payload(provider: str = "deterministic") -> dict:
    return {
        "schema_version": "campaign_config.v1",
        "title": "SPY drawdown-control research",
        "objective": "Find simple SPY drawdown controls that retain most long-term growth.",
        "allowed_symbols": ["SPY"],
        "allowed_templates": ["sma-long-cash", "ema-trend-follow"],
        "benchmark": "buy-and-hold",
        "data_paths": {"SPY": "data/cache/SPY_2015-01-01_2025-12-31.csv"},
        "cost_preset": "retail-liquid",
        "max_cycles": 3,
        "max_total_runs": 33,
        "max_variants_per_experiment": 3,
        "duration_minutes": 30,
        "provider": provider,
    }


class CampaignCandidateChoiceTest(unittest.TestCase):
    def test_deterministic_provider_selects_candidate_from_ready_menu(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            menu = build_campaign_candidate_menu(config, state)
            result = campaign_candidate_provider_result(config, state, menu, cycle_dir=Path(paths.cycles_dir) / "cycle_001")
            validation = validate_campaign_candidate_choice(result.choice, menu=menu)

        self.assertEqual("choose_candidate", result.choice.action)
        self.assertTrue(result.choice.candidate_id)
        self.assertEqual(menu.candidates[0].candidate_id, result.choice.candidate_id)
        self.assertTrue(validation.valid, validation.reasons)

    def test_candidate_choice_rejects_missing_candidate_id(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            menu = build_campaign_candidate_menu(config, state)
            choice = parse_campaign_candidate_choice(
                {
                    "schema_version": "campaign_candidate_choice.v1",
                    "action": "choose_candidate",
                    "candidate_id": "missing",
                    "rationale": "Bad ID.",
                }
            )

        validation = validate_campaign_candidate_choice(choice, menu=menu)

        self.assertFalse(validation.valid)
        self.assertTrue(any("not in candidate menu" in reason for reason in validation.reasons))

    def test_candidate_can_convert_to_valid_campaign_proposal(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            menu = build_campaign_candidate_menu(config, state)
            proposal = campaign_candidate_to_proposal(menu.candidates[0])
            validation = validate_campaign_proposal(proposal, config=config, state=state)

        self.assertTrue(validation.valid, validation.reasons)
        self.assertEqual("run_experiment", proposal.action)
        self.assertEqual(menu.candidates[0].candidate_id.startswith("spy_"), True)

    def test_choose_candidate_command_writes_choice_and_proposal_without_execution(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            campaign_dir = Path(temp_dir) / "campaign"
            paths = initialize_campaign(config, campaign_dir)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["campaign", "choose-candidate", "--campaign", str(campaign_dir)])

            cycle_dir = Path(paths.cycles_dir) / "cycle_001"
            choice_exists = (cycle_dir / "candidate_choice.json").exists()
            proposal_exists = (cycle_dir / "proposal.json").exists()
            execution_exists = (cycle_dir / "campaign_execution.json").exists()
            output = stdout.getvalue()

        self.assertEqual(0, exit_code)
        self.assertTrue(choice_exists)
        self.assertTrue(proposal_exists)
        self.assertFalse(execution_exists)
        self.assertIn("execution: skipped_candidate_choice", output)

    def test_ollama_choice_retries_invalid_candidate_id(self) -> None:
        payload = campaign_payload(provider="ollama")
        config = parse_campaign_config(payload)
        responses = [
            {
                "schema_version": "campaign_candidate_choice.v1",
                "action": "choose_candidate",
                "candidate_id": "missing",
                "rationale": "Try a missing candidate.",
            },
            {
                "schema_version": "campaign_candidate_choice.v1",
                "action": "choose_candidate",
                "candidate_id": "spy_price_vs_sma_trend_001",
                "rationale": "Choose the first valid bounded candidate.",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            campaign_dir = root / "campaign"
            config_path.write_text(json.dumps(payload), encoding="utf-8")

            def fake_post(url: str, request_payload: dict, timeout_seconds: float) -> dict:
                return {"choices": [{"message": {"content": json.dumps(responses.pop(0))}}]}

            with patch("quant_lab.campaign_candidate_provider._post_json", side_effect=fake_post):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    init_exit = main(["campaign", "init", "--config", str(config_path), "--out", str(campaign_dir)])
                    choose_exit = main(
                        [
                            "campaign",
                            "choose-candidate",
                            "--campaign",
                            str(campaign_dir),
                            "--model",
                            "model",
                        ]
                    )

            cycle_dir = campaign_dir / "cycles" / "cycle_001"
            first_validation = json.loads(
                (cycle_dir / "provider_attempt_001" / "candidate_choice_validation.json").read_text(encoding="utf-8")
            )
            final_choice = json.loads((cycle_dir / "candidate_choice.json").read_text(encoding="utf-8"))
            output = stdout.getvalue()

        self.assertEqual(0, init_exit)
        self.assertEqual(0, choose_exit)
        self.assertFalse(first_validation["valid"])
        self.assertEqual("spy_price_vs_sma_trend_001", final_choice["candidate_id"])
        self.assertIn("provider_attempt_1: valid=False", output)
        self.assertIn("provider_attempt_2: valid=True", output)


if __name__ == "__main__":
    unittest.main()
