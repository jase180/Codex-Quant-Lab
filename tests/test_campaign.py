from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.campaign import (  # noqa: E402
    CAMPAIGN_CONFIG_FILENAME,
    CAMPAIGN_STATE_FILENAME,
    CAMPAIGN_STATE_MARKDOWN_FILENAME,
    initialize_campaign,
    load_campaign_config,
    load_campaign_state,
    parse_campaign_config,
    save_campaign_state,
)
from quant_lab.campaign_conversion import prepare_campaign_experiment_inputs  # noqa: E402
from quant_lab.campaign_execution import CampaignExecutionResult, execute_campaign_experiment_inputs  # noqa: E402
from quant_lab.campaign_knowledge import update_campaign_state_after_execution  # noqa: E402
from quant_lab.campaign_proposal import (  # noqa: E402
    deterministic_campaign_proposal,
    parse_campaign_proposal,
    projected_run_count,
    validate_campaign_proposal,
)
from quant_lab.campaign_provider import campaign_provider_proposal, campaign_provider_result  # noqa: E402
from quant_lab.campaign_provider_prompt import build_campaign_provider_context, build_campaign_provider_prompt  # noqa: E402
from quant_lab.campaign_report import build_final_campaign_report  # noqa: E402
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
        "max_total_runs": 33,
        "max_variants_per_experiment": 3,
        "duration_minutes": 30,
        "provider": "deterministic",
    }


def conclusion_payload() -> dict:
    return {
        "schema_version": "experiment_conclusion.v1",
        "experiment_id": "EXP-123",
        "experiment": {
            "title": "SPY SMA 200 long/cash campaign baseline",
            "hypothesis": "A trend rule may reduce drawdown.",
            "tags": ["campaign", "opportunity:liquid_etf_trend_defense"],
        },
        "research_system_status": {"status": "valid"},
        "strategy_hypothesis_status": {"status": "rejected"},
        "thesis_status": {
            "opportunity_thesis_id": "liquid_etf_trend_defense",
            "status": "weakened",
            "reason": "The exact strategy failed but did not fully reject the broader thesis.",
            "confidence": "medium",
        },
        "confidence_label": "rejected",
        "current_conclusion": "The repo measured the idea correctly, but the strategy failed the criteria.",
        "do_not_repeat": ["Do not rerun the same SMA 200 long/cash branch unchanged."],
        "open_questions": ["Did adjusted prices affect the comparison?"],
    }


def partial_conclusion_payload() -> dict:
    payload = conclusion_payload()
    payload["experiment_id"] = "EXP-124"
    payload["experiment"] = {
        "title": "SPY EMA 50 RSI trend-follow campaign follow-up",
        "hypothesis": "A faster trend rule may improve drawdown behavior.",
    }
    payload["strategy_hypothesis_status"] = {
        "status": "partially_supported",
        "criteria_results": [
            {"name": "return_retention", "passed": False, "observed": "0.4003"},
            {"name": "drawdown_reduction", "passed": True, "observed": "0.3799"},
        ],
    }
    payload["confidence_label"] = "rejected"
    payload["current_conclusion"] = "The strategy reduced drawdown but failed return-retention criteria."
    return payload


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
        self.assertEqual(state.remaining_budget["runs"], 33)
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
        self.assertIn("Runs used: 0/33", status_stdout.getvalue())

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

    def test_campaign_provider_boundary_returns_deterministic_proposal(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)

        proposal = campaign_provider_proposal(config, state)

        self.assertEqual(proposal.action, "run_experiment")
        self.assertEqual(proposal.strategy_template, "sma-long-cash")
        self.assertEqual(proposal.opportunity_thesis_id, "liquid_etf_trend_defense")

    def test_campaign_provider_context_includes_relevant_opportunity_theses(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            context = build_campaign_provider_context(config, state)

        thesis_ids = [item["thesis_id"] for item in context["opportunity_theses"]]
        self.assertIn("liquid_etf_trend_defense", thesis_ids)
        self.assertNotIn("forced_event_liquidity", thesis_ids)
        self.assertIn("Prefer proposals with an opportunity_thesis_id", " ".join(context["provider_rules"]))

    def test_campaign_provider_context_spotlights_forbidden_prior_proposals(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            state = replace(
                state,
                completed_experiments=[
                    {
                        "title": "SPY SMA 200 long/cash campaign baseline",
                        "opportunity_thesis_id": "liquid_etf_trend_defense",
                        "strategy_hypothesis_status": "rejected",
                        "thesis_status": "weakened",
                    }
                ],
            )
            context = build_campaign_provider_context(config, state)
            prompt = build_campaign_provider_prompt(context)

        forbidden = context["forbidden_proposals"]
        self.assertEqual(forbidden[0]["title"], "SPY SMA 200 long/cash campaign baseline")
        self.assertIn("Do not repeat any title", " ".join(context["provider_rules"]))
        self.assertIn("Forbidden proposal titles", prompt)
        self.assertIn("SPY SMA 200 long/cash campaign baseline", prompt)
        self.assertNotIn("Use this exact JSON shape", prompt)
        self.assertNotIn('"parameters": {"sma_length": 200}', prompt)

    def test_campaign_provider_prompt_spotlights_retry_feedback(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            context = build_campaign_provider_context(
                config,
                state,
                prior_attempt_feedback=["proposal appears to violate do_not_repeat campaign memory"],
            )
            prompt = build_campaign_provider_prompt(context)

        self.assertIn("Previous provider attempt was rejected", prompt)
        self.assertIn("proposal appears to violate do_not_repeat campaign memory", prompt)

    def test_campaign_validation_rejects_unknown_opportunity_thesis(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            proposal = parse_campaign_proposal(
                {
                    "schema_version": "campaign_proposal.v1",
                    "action": "run_experiment",
                    "title": "SPY unknown thesis test",
                    "hypothesis": "A test proposal cites an unknown thesis.",
                    "rationale": "Validator coverage.",
                    "difference_from_prior_work": "Uses an unknown thesis id.",
                    "strategy_template": "sma-long-cash",
                    "symbol": "SPY",
                    "opportunity_thesis_id": "missing_thesis",
                    "parameters": {"sma_length": 200},
                    "success_criteria": {"minimum_cagr_retention": 0.8},
                    "validation_plan": {"cost_sensitivity": True, "date_sensitivity": True, "train_test": True},
                }
            )

        validation = validate_campaign_proposal(proposal, config=config, state=state)

        self.assertFalse(validation.valid)
        self.assertTrue(any("not in the opportunity catalog" in reason for reason in validation.reasons))

    def test_campaign_validation_rejects_blocked_opportunity_thesis(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            proposal = parse_campaign_proposal(
                {
                    "schema_version": "campaign_proposal.v1",
                    "action": "run_experiment",
                    "title": "SPY blocked thesis test",
                    "hypothesis": "A test proposal cites a blocked thesis.",
                    "rationale": "Validator coverage.",
                    "difference_from_prior_work": "Uses a blocked event thesis.",
                    "strategy_template": "sma-long-cash",
                    "symbol": "SPY",
                    "opportunity_thesis_id": "forced_event_liquidity",
                    "parameters": {"sma_length": 200},
                    "success_criteria": {"minimum_cagr_retention": 0.8},
                    "validation_plan": {"cost_sensitivity": True, "date_sensitivity": True, "train_test": True},
                }
            )

        validation = validate_campaign_proposal(proposal, config=config, state=state)

        self.assertFalse(validation.valid)
        self.assertTrue(any("not marked test_now" in reason for reason in validation.reasons))
        self.assertTrue(any("engine_fit is not ready" in reason for reason in validation.reasons))

    def test_campaign_validation_rejects_unrelated_opportunity_thesis(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            proposal = parse_campaign_proposal(
                {
                    "schema_version": "campaign_proposal.v1",
                    "action": "run_experiment",
                    "title": "SPY unrelated thesis test",
                    "hypothesis": "A test proposal cites a thesis from another strategy family.",
                    "rationale": "Validator coverage.",
                    "difference_from_prior_work": "Uses an ETF rotation thesis with a trend template.",
                    "strategy_template": "sma-long-cash",
                    "symbol": "SPY",
                    "opportunity_thesis_id": "fragmented_etf_relative_strength",
                    "parameters": {"sma_length": 200},
                    "success_criteria": {"minimum_cagr_retention": 0.8},
                    "validation_plan": {"cost_sensitivity": True, "date_sensitivity": True, "train_test": True},
                }
            )

        validation = validate_campaign_proposal(proposal, config=config, state=state)

        self.assertFalse(validation.valid)
        self.assertTrue(any("not compatible with template" in reason for reason in validation.reasons))

    def test_campaign_validation_rejects_prompt_placeholder_text(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            proposal = parse_campaign_proposal(
                {
                    "schema_version": "campaign_proposal.v1",
                    "action": "run_experiment",
                    "title": "SPY SMA 200 long/cash campaign baseline",
                    "hypothesis": "A clear testable hypothesis.",
                    "rationale": "Why this test is justified now.",
                    "difference_from_prior_work": "What is materially different from prior work.",
                    "strategy_template": "sma-long-cash",
                    "symbol": "SPY",
                    "opportunity_thesis_id": "liquid_etf_trend_defense",
                    "parameters": {"sma_length": 200},
                    "success_criteria": {"minimum_cagr_retention": 0.8},
                    "validation_plan": {"cost_sensitivity": True, "date_sensitivity": True, "train_test": True},
                }
            )

        validation = validate_campaign_proposal(proposal, config=config, state=state)

        self.assertFalse(validation.valid)
        self.assertTrue(any("hypothesis appears to be copied placeholder text" in reason for reason in validation.reasons))
        self.assertTrue(any("rationale appears to be copied placeholder text" in reason for reason in validation.reasons))
        self.assertTrue(any("difference_from_prior_work appears" in reason for reason in validation.reasons))

    def test_campaign_validation_rejects_non_run_with_partial_experiment_fields(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            proposal = parse_campaign_proposal(
                {
                    "schema_version": "campaign_proposal.v1",
                    "action": "request_human_review",
                    "title": "Review vague SPY idea",
                    "hypothesis": "A human should review a vague SPY experiment.",
                    "rationale": "Validator coverage for non-run handoffs.",
                    "difference_from_prior_work": "Does not define a runnable experiment.",
                    "strategy_template": None,
                    "symbol": "SPY",
                    "opportunity_thesis_id": None,
                    "parameters": {},
                    "success_criteria": {"minimum_cagr_retention": 0.8},
                    "validation_plan": {"cost_sensitivity": True},
                }
            )

        validation = validate_campaign_proposal(proposal, config=config, state=state)

        self.assertFalse(validation.valid)
        self.assertTrue(any("symbol to null" in reason for reason in validation.reasons))
        self.assertTrue(any("success_criteria empty" in reason for reason in validation.reasons))
        self.assertTrue(any("validation_plan empty" in reason for reason in validation.reasons))

    def test_campaign_validation_allows_human_review_to_reference_opportunity_thesis(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            proposal = parse_campaign_proposal(
                {
                    "schema_version": "campaign_proposal.v1",
                    "action": "request_human_review",
                    "title": "Human review of liquid ETF thesis",
                    "hypothesis": "Human review should decide whether the thesis is still worth testing.",
                    "rationale": "Completed experiments weakened the current thesis.",
                    "difference_from_prior_work": "No new experiment; asks for thesis-level review.",
                    "strategy_template": None,
                    "symbol": None,
                    "opportunity_thesis_id": "liquid_etf_trend_defense",
                    "parameters": {},
                    "success_criteria": {},
                    "validation_plan": {},
                }
            )

        validation = validate_campaign_proposal(proposal, config=config, state=state)

        self.assertTrue(validation.valid, validation.reasons)

    def test_campaign_validation_rejects_stop_with_opportunity_thesis(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)
            proposal = parse_campaign_proposal(
                {
                    "schema_version": "campaign_proposal.v1",
                    "action": "stop_campaign",
                    "title": "Stop with dangling thesis",
                    "hypothesis": "No more experiments should run.",
                    "rationale": "Validator coverage.",
                    "difference_from_prior_work": "No new experiment.",
                    "strategy_template": None,
                    "symbol": None,
                    "opportunity_thesis_id": "liquid_etf_trend_defense",
                    "parameters": {},
                    "success_criteria": {},
                    "validation_plan": {},
                }
            )

        validation = validate_campaign_proposal(proposal, config=config, state=state)

        self.assertFalse(validation.valid)
        self.assertTrue(any("stop_campaign actions" in reason for reason in validation.reasons))

    def test_campaign_provider_boundary_returns_codex_handoff_proposal(self) -> None:
        payload = campaign_payload()
        payload["provider"] = "codex"
        config = parse_campaign_config(payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, temp_dir)
            state = load_campaign_state(paths.state_path)

        proposal = campaign_provider_proposal(config, state)

        self.assertEqual(proposal.action, "request_human_review")
        self.assertEqual(proposal.title, "Codex campaign proposal handoff")

    def test_ollama_campaign_provider_returns_strict_proposal_and_writes_artifacts(self) -> None:
        payload = campaign_payload()
        payload["provider"] = "ollama"
        config = parse_campaign_config(payload)
        model_payload = {
            "schema_version": "campaign_proposal.v1",
            "action": "run_experiment",
            "title": "SPY SMA 200 local-model dry run",
            "hypothesis": "A 200-day trend rule may reduce drawdown while retaining most growth.",
            "rationale": "Use an already supported template before broadening campaign scope.",
            "difference_from_prior_work": "First model-proposed campaign dry run.",
            "strategy_template": "sma-long-cash",
            "symbol": "SPY",
            "parameters": {"sma_length": 200},
            "success_criteria": {
                "minimum_cagr_retention": 0.8,
                "minimum_relative_drawdown_reduction": 0.25,
            },
            "validation_plan": {"cost_sensitivity": True, "date_sensitivity": True, "train_test": True},
        }

        def fake_post(url: str, payload: dict, timeout_seconds: float) -> dict:
            self.assertEqual(url, "http://local/v1/chat/completions")
            self.assertEqual(payload["model"], "model")
            self.assertEqual(timeout_seconds, 12.0)
            return {"choices": [{"message": {"content": json.dumps(model_payload)}}]}

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            result = campaign_provider_result(
                config,
                state,
                cycle_dir=Path(paths.cycles_dir) / "cycle_001",
                base_url="http://local/v1",
                model="model",
                timeout_seconds=12.0,
                http_post=fake_post,
            )

            context_exists = Path(result.context_path or "").exists()
            context_payload = json.loads(Path(result.context_path or "").read_text(encoding="utf-8"))
            prompt_exists = Path(result.prompt_path or "").exists()
            raw_exists = Path(result.raw_response_path or "").exists()
            parsed_exists = Path(result.parsed_proposal_path or "").exists()

        self.assertEqual(result.provider, "ollama")
        self.assertEqual(result.proposal.title, "SPY SMA 200 local-model dry run")
        self.assertIn("opportunity_theses", context_payload)
        self.assertTrue(any(item["thesis_id"] == "liquid_etf_trend_defense" for item in context_payload["opportunity_theses"]))
        self.assertTrue(context_exists)
        self.assertTrue(prompt_exists)
        self.assertTrue(raw_exists)
        self.assertTrue(parsed_exists)

    def test_prepare_campaign_experiment_inputs_writes_strategy_and_run_default_handoff(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            proposal = deterministic_campaign_proposal(config, state)
            inputs = prepare_campaign_experiment_inputs(
                proposal,
                config=config,
                cycle_dir=Path(paths.cycles_dir) / "cycle_001",
            )

            strategy = json.loads(Path(inputs.strategy_path).read_text(encoding="utf-8"))
            args_payload = json.loads(Path(inputs.run_default_args_path).read_text(encoding="utf-8"))
            command_markdown = Path(inputs.run_default_command_path).read_text(encoding="utf-8")

        self.assertEqual(strategy["name"], "SPY SMA 200 long/cash campaign baseline")
        self.assertEqual(strategy["market"]["symbol"], "SPY")
        self.assertIn("--param", inputs.command_tokens)
        self.assertIn("sma_200.inputs.length=200", inputs.command_tokens)
        self.assertIn("--success-criterion", inputs.command_tokens)
        self.assertEqual(args_payload["schema_version"], "campaign_experiment_inputs.v1")
        self.assertEqual(args_payload["opportunity_thesis_id"], "liquid_etf_trend_defense")
        self.assertIn("opportunity:liquid_etf_trend_defense", args_payload["run_default_args"]["tag"])
        self.assertIn("opportunity:liquid_etf_trend_defense", inputs.command_tokens)
        self.assertIn("quant-lab", command_markdown)
        self.assertIn("experiment", command_markdown)
        self.assertIn("run-default", command_markdown)

    def test_prepare_campaign_experiment_inputs_supports_expanded_campaign_templates(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            rsi_proposal = parse_campaign_proposal(
                {
                    "schema_version": "campaign_proposal.v1",
                    "action": "run_experiment",
                    "title": "SPY RSI pullback reversion candidate",
                    "hypothesis": "A prespecified RSI pullback rule may test retail pullback liquidity.",
                    "rationale": "Uses an existing campaign-safe template.",
                    "difference_from_prior_work": "Moves from trend defense to pullback reversion.",
                    "strategy_template": "rsi-reversion",
                    "symbol": "SPY",
                    "opportunity_thesis_id": "retail_pullback_liquidity",
                    "parameters": {},
                    "success_criteria": {
                        "minimum_cagr_retention": 0.7,
                        "minimum_relative_drawdown_reduction": 0.15,
                    },
                    "validation_plan": {"cost_sensitivity": True, "date_sensitivity": True, "train_test": True},
                }
            )
            breakout_proposal = parse_campaign_proposal(
                {
                    "schema_version": "campaign_proposal.v1",
                    "action": "run_experiment",
                    "title": "SPY breakout trend persistence candidate",
                    "hypothesis": "A prespecified breakout rule may test trend persistence.",
                    "rationale": "Uses an existing campaign-safe template.",
                    "difference_from_prior_work": "Uses rolling highs and lows instead of moving-average state.",
                    "strategy_template": "breakout-trend",
                    "symbol": "SPY",
                    "opportunity_thesis_id": "liquid_etf_trend_defense",
                    "parameters": {},
                    "success_criteria": {
                        "minimum_cagr_retention": 0.8,
                        "minimum_relative_drawdown_reduction": 0.2,
                    },
                    "validation_plan": {"cost_sensitivity": True, "date_sensitivity": True, "train_test": True},
                }
            )

            rsi_inputs = prepare_campaign_experiment_inputs(
                rsi_proposal,
                config=config,
                cycle_dir=Path(paths.cycles_dir) / "cycle_001",
            )
            breakout_inputs = prepare_campaign_experiment_inputs(
                breakout_proposal,
                config=config,
                cycle_dir=Path(paths.cycles_dir) / "cycle_002",
            )

            rsi_strategy = json.loads(Path(rsi_inputs.strategy_path).read_text(encoding="utf-8"))
            breakout_strategy = json.loads(Path(breakout_inputs.strategy_path).read_text(encoding="utf-8"))

        self.assertEqual("rsi", rsi_strategy["indicators"][0]["kind"])
        self.assertEqual(["rolling_high", "rolling_low"], [item["kind"] for item in breakout_strategy["indicators"]])
        self.assertIn("rsi_14.inputs.length=14", rsi_inputs.command_tokens)
        self.assertIn("high_20.inputs.length=20", breakout_inputs.command_tokens)
        self.assertIn("low_10.inputs.length=10", breakout_inputs.command_tokens)

    def test_execute_campaign_experiment_inputs_calls_default_workflow_and_saves_receipt(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            proposal = deterministic_campaign_proposal(config, state)
            inputs = prepare_campaign_experiment_inputs(
                proposal,
                config=config,
                cycle_dir=Path(paths.cycles_dir) / "cycle_001",
            )

            with patch("quant_lab.campaign_execution.run_default_experiment") as workflow:
                workflow.return_value.experiment_id = "EXP-123"
                workflow.return_value.output_dir = inputs.output_dir
                workflow.return_value.conclusion_path = str(Path(inputs.output_dir) / "experiment_conclusion.json")
                workflow.return_value.read_first_path = workflow.return_value.conclusion_path
                Path(workflow.return_value.conclusion_path).parent.mkdir(parents=True, exist_ok=True)
                Path(workflow.return_value.conclusion_path).write_text(json.dumps(conclusion_payload()), encoding="utf-8")
                result = execute_campaign_experiment_inputs(inputs)

            receipt = json.loads(Path(result.execution_json_path).read_text(encoding="utf-8"))
            markdown = Path(result.execution_markdown_path).read_text(encoding="utf-8")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.experiment_id, "EXP-123")
        self.assertEqual(result.conclusion_json_path, result.conclusion_path)
        self.assertTrue(workflow.called)
        self.assertEqual(receipt["schema_version"], "campaign_execution.v1")
        self.assertIn("Campaign Cycle Execution", markdown)

    def test_update_campaign_state_after_execution_carries_forward_conclusion_knowledge(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            conclusion_path = Path(temp_dir) / "experiment_conclusion.json"
            conclusion_path.write_text(json.dumps(conclusion_payload()), encoding="utf-8")
            execution = CampaignExecutionResult(
                schema_version="campaign_execution.v1",
                status="completed",
                experiment_id="EXP-123",
                output_dir=str(Path(temp_dir) / "experiment"),
                conclusion_path=str(conclusion_path.with_suffix(".md")),
                conclusion_json_path=str(conclusion_path),
                read_first_path=str(conclusion_path.with_suffix(".md")),
                execution_json_path=str(Path(temp_dir) / "campaign_execution.json"),
                execution_markdown_path=str(Path(temp_dir) / "campaign_execution.md"),
                error=None,
                elapsed_seconds=7,
                created_at_utc="2026-08-05T00:00:00Z",
            )

            updated = update_campaign_state_after_execution(
                state,
                config=config,
                execution=execution,
                projected_run_count=11,
            )

        self.assertEqual(updated.cycle_number, 1)
        self.assertEqual(updated.runs_used, 11)
        self.assertEqual(updated.elapsed_seconds, 7)
        self.assertEqual(updated.remaining_budget["cycles"], 2)
        self.assertEqual(updated.remaining_budget["runs"], 22)
        self.assertEqual(updated.completed_experiments[0]["research_system_status"], "valid")
        self.assertEqual(updated.completed_experiments[0]["strategy_hypothesis_status"], "rejected")
        self.assertEqual(updated.completed_experiments[0]["opportunity_thesis_id"], "liquid_etf_trend_defense")
        self.assertEqual(updated.completed_experiments[0]["thesis_status"], "weakened")
        self.assertIn("strategy failed", " ".join(updated.current_findings))
        self.assertIn("thesis `weakened`", " ".join(updated.current_findings))
        self.assertIn("Do not rerun the same SMA 200 long/cash branch unchanged.", updated.do_not_repeat)
        self.assertIn(
            "Do not repeat unchanged rejected experiment: SPY SMA 200 long/cash campaign baseline.",
            updated.do_not_repeat,
        )
        self.assertIn("Did adjusted prices affect the comparison?", updated.unresolved_questions)
        follow_up = deterministic_campaign_proposal(config, updated)
        follow_up_validation = validate_campaign_proposal(follow_up, config=config, state=updated)
        repeated_proposal = parse_campaign_proposal(
            {
                "schema_version": "campaign_proposal.v1",
                "action": "run_experiment",
                "title": "SPY SMA 200 long/cash campaign baseline",
                "hypothesis": "Repeat the rejected branch unchanged.",
                "rationale": "Validator check.",
                "difference_from_prior_work": "No material difference.",
                "strategy_template": "sma-long-cash",
                "symbol": "SPY",
                "parameters": {"sma_length": 200},
                "success_criteria": {"minimum_cagr_retention": 0.8},
                "validation_plan": {"cost_sensitivity": True, "date_sensitivity": True, "train_test": True},
            }
        )
        repeated_validation = validate_campaign_proposal(repeated_proposal, config=config, state=updated)
        self.assertEqual(follow_up.strategy_template, "ema-trend-follow")
        self.assertTrue(follow_up_validation.valid)
        self.assertFalse(repeated_validation.valid)
        self.assertTrue(any("do_not_repeat" in reason for reason in repeated_validation.reasons))

    def test_deterministic_campaign_proposal_stops_after_known_sequence_is_exhausted(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)

        state.completed_experiments.extend(
            [
                {"title": "SPY SMA 200 long/cash campaign baseline"},
                {"title": "SPY EMA 50 RSI trend-follow campaign follow-up"},
            ]
        )
        proposal = deterministic_campaign_proposal(config, state)

        self.assertEqual(proposal.action, "stop_campaign")
        self.assertEqual(projected_run_count(proposal), 0)

    def test_final_campaign_report_summarizes_completed_experiments_without_overclaiming(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            conclusion_one = Path(temp_dir) / "conclusion_one.json"
            conclusion_two = Path(temp_dir) / "conclusion_two.json"
            conclusion_one.write_text(json.dumps(conclusion_payload()), encoding="utf-8")
            conclusion_two.write_text(json.dumps(partial_conclusion_payload()), encoding="utf-8")
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            completed_state = replace(
                state,
                status="complete",
                cycle_number=2,
                runs_used=22,
                completed_experiments=[
                    {
                        "experiment_id": "EXP-123",
                        "title": "SPY SMA 200 long/cash campaign baseline",
                        "research_system_status": "valid",
                        "strategy_hypothesis_status": "rejected",
                        "opportunity_thesis_id": "liquid_etf_trend_defense",
                        "thesis_status": "weakened",
                        "confidence_label": "rejected",
                        "conclusion_json_path": str(conclusion_one),
                        "conclusion_path": str(conclusion_one.with_suffix(".md")),
                        "projected_run_count": 11,
                        "elapsed_seconds": 5,
                    },
                    {
                        "experiment_id": "EXP-124",
                        "title": "SPY EMA 50 RSI trend-follow campaign follow-up",
                        "research_system_status": "valid",
                        "strategy_hypothesis_status": "partially_supported",
                        "opportunity_thesis_id": "liquid_etf_trend_defense",
                        "thesis_status": "weakened",
                        "confidence_label": "rejected",
                        "conclusion_json_path": str(conclusion_two),
                        "conclusion_path": str(conclusion_two.with_suffix(".md")),
                        "projected_run_count": 11,
                        "elapsed_seconds": 6,
                    },
                ],
                current_findings=["One branch rejected.", "One branch partially supported."],
                stop_reason="No remaining deterministic campaign proposal is materially different from prior work.",
            )

            report = build_final_campaign_report(config, completed_state)

        self.assertEqual(report.status, "complete")
        self.assertEqual(report.hypothesis_status_counts["rejected"], 1)
        self.assertEqual(report.hypothesis_status_counts["partially_supported"], 1)
        self.assertEqual(report.thesis_status_counts["weakened"], 2)
        self.assertEqual(report.experiments_attempted[0]["opportunity_thesis_id"], "liquid_etf_trend_defense")
        self.assertEqual(report.best_completed_result["title"], "SPY EMA 50 RSI trend-follow campaign follow-up")
        self.assertIn("review the conclusion", report.best_completed_result["note"])
        self.assertIsNone(report.best_remaining_candidate)

    def test_campaign_run_stop_writes_final_report_and_marks_state_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = parse_campaign_config(campaign_payload())
            paths = initialize_campaign(config, root / "campaign")
            state = load_campaign_state(paths.state_path)
            stopped_ready_state = replace(
                state,
                completed_experiments=[
                    {"title": "SPY SMA 200 long/cash campaign baseline"},
                    {"title": "SPY EMA 50 RSI trend-follow campaign follow-up"},
                ],
                do_not_repeat=[
                    "Do not keep widening this branch without a materially different trend-defense mechanism.",
                ],
            )
            save_campaign_state(stopped_ready_state, paths.output_dir, config=config)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["campaign", "run", "--out", paths.output_dir, "--resume"])

            final_json_path = Path(paths.final_report_json_path)
            final_markdown_path = Path(paths.final_report_markdown_path)
            updated_state = load_campaign_state(paths.state_path)
            final_json_exists = final_json_path.exists()
            final_markdown_exists = final_markdown_path.exists()
            final_report = json.loads(final_json_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(updated_state.status, "complete")
        self.assertTrue(final_json_exists)
        self.assertTrue(final_markdown_exists)
        self.assertEqual(final_report["schema_version"], "campaign_final_report.v1")
        self.assertIn("best_completed_result", final_report)
        self.assertIsNone(final_report["best_remaining_candidate"])
        self.assertIn("final_report:", stdout.getvalue())

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

    def test_campaign_run_writes_conversion_and_execution_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(campaign_payload()), encoding="utf-8")
            fake_conclusion_path = out_dir / "cycles" / "cycle_001" / "experiment" / "experiment_conclusion.json"
            fake_conclusion_path.parent.mkdir(parents=True, exist_ok=True)
            fake_conclusion_path.write_text(json.dumps(conclusion_payload()), encoding="utf-8")

            fake_execution = CampaignExecutionResult(
                schema_version="campaign_execution.v1",
                status="completed",
                experiment_id="EXP-999",
                output_dir=str(out_dir / "cycles" / "cycle_001" / "experiment"),
                conclusion_path=str(fake_conclusion_path.with_suffix(".md")),
                conclusion_json_path=str(fake_conclusion_path),
                read_first_path=str(out_dir / "cycles" / "cycle_001" / "experiment" / "experiment_conclusion.md"),
                execution_json_path=str(out_dir / "cycles" / "cycle_001" / "campaign_execution.json"),
                execution_markdown_path=str(out_dir / "cycles" / "cycle_001" / "campaign_execution.md"),
                error=None,
                elapsed_seconds=5,
                created_at_utc="2026-08-05T00:00:00Z",
            )
            with patch("quant_lab.cli_campaign.execute_campaign_experiment_inputs", return_value=fake_execution):
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
            strategy_path = out_dir / "cycles" / "cycle_001" / "strategy.json"
            args_path = out_dir / "cycles" / "cycle_001" / "run_default_args.json"
            command_path = out_dir / "cycles" / "cycle_001" / "run_default_command.md"
            proposal_exists = proposal_path.exists()
            validation_exists = validation_path.exists()
            strategy_exists = strategy_path.exists()
            args_exists = args_path.exists()
            command_exists = command_path.exists()
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            state = load_campaign_state(out_dir / CAMPAIGN_STATE_FILENAME)

        self.assertEqual(exit_code, 0)
        self.assertTrue(proposal_exists)
        self.assertTrue(validation_exists)
        self.assertTrue(strategy_exists)
        self.assertTrue(args_exists)
        self.assertTrue(command_exists)
        self.assertTrue(validation["valid"])
        self.assertEqual(state.cycle_number, 1)
        self.assertEqual(state.runs_used, 11)
        self.assertIn("Do not rerun the same SMA 200 long/cash branch unchanged.", state.do_not_repeat)
        self.assertIn("planned_command:", stdout.getvalue())
        self.assertIn("execution: completed", stdout.getvalue())
        self.assertIn("conclusion:", stdout.getvalue())
        self.assertIn("cycle_number: 1", stdout.getvalue())

    def test_campaign_run_loop_runs_until_deterministic_stop_and_final_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(campaign_payload()), encoding="utf-8")
            calls: list[str] = []

            def fake_execute(inputs) -> CampaignExecutionResult:
                calls.append(inputs.output_dir)
                conclusion = conclusion_payload() if len(calls) == 1 else partial_conclusion_payload()
                conclusion_path = Path(inputs.output_dir) / "experiment_conclusion.json"
                conclusion_path.parent.mkdir(parents=True, exist_ok=True)
                conclusion_path.write_text(json.dumps(conclusion), encoding="utf-8")
                return CampaignExecutionResult(
                    schema_version="campaign_execution.v1",
                    status="completed",
                    experiment_id=f"EXP-{len(calls)}",
                    output_dir=inputs.output_dir,
                    conclusion_path=str(conclusion_path.with_suffix(".md")),
                    conclusion_json_path=str(conclusion_path),
                    read_first_path=str(conclusion_path.with_suffix(".md")),
                    execution_json_path=str(Path(inputs.output_dir).parent / "campaign_execution.json"),
                    execution_markdown_path=str(Path(inputs.output_dir).parent / "campaign_execution.md"),
                    error=None,
                    elapsed_seconds=5,
                    created_at_utc="2026-08-05T00:00:00Z",
                )

            with patch("quant_lab.cli_campaign.execute_campaign_experiment_inputs", side_effect=fake_execute):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    exit_code = main(
                        [
                            "campaign",
                            "run",
                            "--config",
                            str(config_path),
                            "--out",
                            str(out_dir),
                            "--loop",
                        ]
                    )

            state = load_campaign_state(out_dir / CAMPAIGN_STATE_FILENAME)
            final_report_path = out_dir / "final_report.md"
            cycle_one_exists = (out_dir / "cycles" / "cycle_001" / "proposal.json").exists()
            cycle_two_exists = (out_dir / "cycles" / "cycle_002" / "proposal.json").exists()
            cycle_three_exists = (out_dir / "cycles" / "cycle_003" / "proposal.json").exists()
            final_report_exists = final_report_path.exists()
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(calls), 3)
        self.assertEqual(state.status, "complete")
        self.assertEqual(state.cycle_number, 3)
        self.assertEqual(state.runs_used, 33)
        self.assertTrue(final_report_exists)
        self.assertTrue(cycle_one_exists)
        self.assertTrue(cycle_two_exists)
        self.assertTrue(cycle_three_exists)
        self.assertIn("Campaign loop starting", output)
        self.assertIn("final_report:", output)

    def test_campaign_run_budget_overrides_initialize_saved_config_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(campaign_payload()), encoding="utf-8")
            fake_conclusion_path = out_dir / "cycles" / "cycle_001" / "experiment" / "experiment_conclusion.json"
            fake_conclusion_path.parent.mkdir(parents=True, exist_ok=True)
            fake_conclusion_path.write_text(json.dumps(conclusion_payload()), encoding="utf-8")
            fake_execution = CampaignExecutionResult(
                schema_version="campaign_execution.v1",
                status="completed",
                experiment_id="EXP-OVERRIDE",
                output_dir=str(out_dir / "cycles" / "cycle_001" / "experiment"),
                conclusion_path=str(fake_conclusion_path.with_suffix(".md")),
                conclusion_json_path=str(fake_conclusion_path),
                read_first_path=str(fake_conclusion_path.with_suffix(".md")),
                execution_json_path=str(out_dir / "cycles" / "cycle_001" / "campaign_execution.json"),
                execution_markdown_path=str(out_dir / "cycles" / "cycle_001" / "campaign_execution.md"),
                error=None,
                elapsed_seconds=5,
                created_at_utc="2026-08-05T00:00:00Z",
            )

            with patch("quant_lab.cli_campaign.execute_campaign_experiment_inputs", return_value=fake_execution):
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = main(
                        [
                            "campaign",
                            "run",
                            "--config",
                            str(config_path),
                            "--out",
                            str(out_dir),
                            "--duration",
                            "90s",
                            "--max-cycles",
                            "2",
                            "--max-total-runs",
                            "22",
                        ]
                    )

            saved_config = load_campaign_config(out_dir / "campaign_config.json")
            state = load_campaign_state(out_dir / CAMPAIGN_STATE_FILENAME)

        self.assertEqual(exit_code, 0)
        self.assertEqual(saved_config.duration_minutes, 2)
        self.assertEqual(saved_config.max_cycles, 2)
        self.assertEqual(saved_config.max_total_runs, 22)
        self.assertEqual(state.remaining_budget["cycles"], 1)
        self.assertEqual(state.remaining_budget["runs"], 11)
        self.assertEqual(state.remaining_budget["seconds"], 115)

    def test_campaign_run_provider_override_initializes_saved_config(self) -> None:
        model_payload = {
            "schema_version": "campaign_proposal.v1",
            "action": "run_experiment",
            "title": "SPY SMA 200 provider override dry run",
            "hypothesis": "A 200-day trend rule may reduce drawdown while retaining most growth.",
            "rationale": "Validate provider override persistence.",
            "difference_from_prior_work": "First provider override dry run.",
            "strategy_template": "sma-long-cash",
            "symbol": "SPY",
            "parameters": {"sma_length": 200},
            "success_criteria": {"minimum_cagr_retention": 0.8},
            "validation_plan": {"cost_sensitivity": True, "date_sensitivity": True, "train_test": True},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(campaign_payload()), encoding="utf-8")

            def fake_post(url: str, request_payload: dict, timeout_seconds: float) -> dict:
                return {"choices": [{"message": {"content": json.dumps(model_payload)}}]}

            with patch("quant_lab.campaign_provider._post_json", side_effect=fake_post):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    exit_code = main(
                        [
                            "campaign",
                            "run",
                            "--config",
                            str(config_path),
                            "--provider",
                            "ollama",
                            "--out",
                            str(out_dir),
                            "--model",
                            "model",
                        ]
                    )

            saved_config = load_campaign_config(out_dir / "campaign_config.json")
            state = load_campaign_state(out_dir / CAMPAIGN_STATE_FILENAME)
            provider_context_exists = (
                out_dir / "cycles" / "cycle_001" / "provider_attempt_001" / "provider_context.json"
            ).exists()
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertEqual(saved_config.provider, "ollama")
        self.assertEqual(state.cycle_number, 0)
        self.assertTrue(provider_context_exists)
        self.assertIn("execution: skipped_provider_dry_run", output)

    def test_campaign_run_budget_overrides_reject_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(campaign_payload()), encoding="utf-8")
            config = parse_campaign_config(campaign_payload())
            initialize_campaign(config, out_dir)

            with self.assertRaisesRegex(ValueError, "overrides can only initialize"):
                main(
                    [
                        "campaign",
                        "run",
                        "--config",
                        str(config_path),
                        "--out",
                        str(out_dir),
                        "--resume",
                        "--max-cycles",
                        "2",
                    ]
                )

    def test_campaign_run_provider_override_rejects_resume_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(campaign_payload()), encoding="utf-8")
            config = parse_campaign_config(campaign_payload())
            initialize_campaign(config, out_dir)

            with self.assertRaisesRegex(ValueError, "overrides can only initialize"):
                main(
                    [
                        "campaign",
                        "run",
                        "--config",
                        str(config_path),
                        "--out",
                        str(out_dir),
                        "--resume",
                        "--provider",
                        "ollama",
                    ]
                )

    def test_campaign_run_codex_provider_writes_handoff_artifacts(self) -> None:
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
                        "--provider",
                        "codex",
                        "--out",
                        str(out_dir),
                    ]
                )

            saved_config = load_campaign_config(out_dir / "campaign_config.json")
            cycle_dir = out_dir / "cycles" / "cycle_001"
            choice = json.loads((cycle_dir / "candidate_choice.json").read_text(encoding="utf-8"))
            provider_context_exists = (cycle_dir / "provider_attempt_001" / "provider_context.json").exists()
            provider_prompt_exists = (cycle_dir / "provider_attempt_001" / "provider_prompt.md").exists()
            provider_choice_exists = (cycle_dir / "provider_attempt_001" / "provider_proposal.json").exists()
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertEqual(saved_config.provider, "codex")
        self.assertEqual(choice["action"], "request_human_review")
        self.assertTrue(provider_context_exists)
        self.assertTrue(provider_prompt_exists)
        self.assertTrue(provider_choice_exists)
        self.assertIn("execution: skipped_human_review", output)

    def test_campaign_run_loop_stops_on_duration_limit_between_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(campaign_payload()), encoding="utf-8")
            fake_conclusion_path = out_dir / "cycles" / "cycle_001" / "experiment" / "experiment_conclusion.json"
            fake_conclusion_path.parent.mkdir(parents=True, exist_ok=True)
            fake_conclusion_path.write_text(json.dumps(conclusion_payload()), encoding="utf-8")
            fake_execution = CampaignExecutionResult(
                schema_version="campaign_execution.v1",
                status="completed",
                experiment_id="EXP-TIME",
                output_dir=str(out_dir / "cycles" / "cycle_001" / "experiment"),
                conclusion_path=str(fake_conclusion_path.with_suffix(".md")),
                conclusion_json_path=str(fake_conclusion_path),
                read_first_path=str(fake_conclusion_path.with_suffix(".md")),
                execution_json_path=str(out_dir / "cycles" / "cycle_001" / "campaign_execution.json"),
                execution_markdown_path=str(out_dir / "cycles" / "cycle_001" / "campaign_execution.md"),
                error=None,
                elapsed_seconds=5,
                created_at_utc="2026-08-05T00:00:00Z",
            )

            with patch("quant_lab.cli_campaign.execute_campaign_experiment_inputs", return_value=fake_execution):
                with patch("quant_lab.cli_campaign.time.monotonic", side_effect=[0.0, 0.0, 61.0]):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        exit_code = main(
                            [
                                "campaign",
                                "run",
                                "--config",
                                str(config_path),
                                "--out",
                                str(out_dir),
                                "--loop",
                                "--duration",
                                "1m",
                            ]
                        )

            state = load_campaign_state(out_dir / CAMPAIGN_STATE_FILENAME)
            final_report_exists = (out_dir / "final_report.md").exists()
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertEqual(state.status, "complete")
        self.assertEqual(state.stop_reason, "duration wall-clock limit reached")
        self.assertTrue(final_report_exists)
        self.assertIn("duration limit reached", output)

    def test_campaign_run_ollama_provider_dry_run_saves_proposal_without_execution(self) -> None:
        payload = campaign_payload()
        payload["provider"] = "ollama"
        model_payload = {
            "schema_version": "campaign_candidate_choice.v1",
            "action": "choose_candidate",
            "candidate_id": "spy_price_vs_sma_trend_003",
            "rationale": "Choose the canonical SMA 200 baseline candidate from the bounded menu.",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(payload), encoding="utf-8")

            def fake_post(url: str, request_payload: dict, timeout_seconds: float) -> dict:
                return {"choices": [{"message": {"content": json.dumps(model_payload)}}]}

            with patch("quant_lab.campaign_candidate_provider._post_json", side_effect=fake_post):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    exit_code = main(
                        [
                            "campaign",
                            "run",
                            "--config",
                            str(config_path),
                            "--out",
                            str(out_dir),
                            "--model",
                            "model",
                        ]
                    )

            cycle_dir = out_dir / "cycles" / "cycle_001"
            attempt_dir = cycle_dir / "provider_attempt_001"
            proposal_path = cycle_dir / "proposal.json"
            validation_path = cycle_dir / "proposal_validation.json"
            context_path = attempt_dir / "provider_context.json"
            raw_path = attempt_dir / "provider_raw_response.txt"
            choice_path = cycle_dir / "candidate_choice.json"
            strategy_path = cycle_dir / "strategy.json"
            execution_path = cycle_dir / "campaign_execution.json"
            state = load_campaign_state(out_dir / CAMPAIGN_STATE_FILENAME)
            proposal_exists = proposal_path.exists()
            validation_exists = validation_path.exists()
            context_exists = context_path.exists()
            raw_exists = raw_path.exists()
            choice_exists = choice_path.exists()
            strategy_exists = strategy_path.exists()
            execution_exists = execution_path.exists()
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertTrue(proposal_exists)
        self.assertTrue(validation_exists)
        self.assertTrue(context_exists)
        self.assertTrue(raw_exists)
        self.assertTrue(choice_exists)
        self.assertFalse(strategy_exists)
        self.assertFalse(execution_exists)
        self.assertEqual(state.cycle_number, 0)
        self.assertIn("execution: skipped_provider_dry_run", output)

    def test_campaign_run_ollama_provider_executes_valid_model_proposal_when_explicitly_enabled(self) -> None:
        payload = campaign_payload()
        payload["provider"] = "ollama"
        model_payload = {
            "schema_version": "campaign_candidate_choice.v1",
            "action": "choose_candidate",
            "candidate_id": "spy_price_vs_sma_trend_003",
            "rationale": "Choose the canonical SMA 200 baseline candidate from the bounded menu.",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(payload), encoding="utf-8")
            fake_conclusion_path = out_dir / "cycles" / "cycle_001" / "experiment" / "experiment_conclusion.json"
            fake_conclusion_path.parent.mkdir(parents=True, exist_ok=True)
            fake_conclusion_path.write_text(json.dumps(conclusion_payload()), encoding="utf-8")
            fake_execution = CampaignExecutionResult(
                schema_version="campaign_execution.v1",
                status="completed",
                experiment_id="EXP-MODEL",
                output_dir=str(out_dir / "cycles" / "cycle_001" / "experiment"),
                conclusion_path=str(fake_conclusion_path.with_suffix(".md")),
                conclusion_json_path=str(fake_conclusion_path),
                read_first_path=str(fake_conclusion_path.with_suffix(".md")),
                execution_json_path=str(out_dir / "cycles" / "cycle_001" / "campaign_execution.json"),
                execution_markdown_path=str(out_dir / "cycles" / "cycle_001" / "campaign_execution.md"),
                error=None,
                elapsed_seconds=5,
                created_at_utc="2026-08-05T00:00:00Z",
            )

            def fake_post(url: str, request_payload: dict, timeout_seconds: float) -> dict:
                return {"choices": [{"message": {"content": json.dumps(model_payload)}}]}

            with patch("quant_lab.campaign_candidate_provider._post_json", side_effect=fake_post):
                with patch("quant_lab.cli_campaign.execute_campaign_experiment_inputs", return_value=fake_execution):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        exit_code = main(
                            [
                                "campaign",
                                "run",
                                "--config",
                                str(config_path),
                                "--out",
                                str(out_dir),
                                "--model",
                                "model",
                                "--execute-model-proposal",
                            ]
                        )

            strategy_path = out_dir / "cycles" / "cycle_001" / "strategy.json"
            state = load_campaign_state(out_dir / CAMPAIGN_STATE_FILENAME)
            strategy_exists = strategy_path.exists()
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertTrue(strategy_exists)
        self.assertEqual(state.cycle_number, 1)
        self.assertEqual(state.runs_used, 11)
        self.assertIn("execution: completed", output)
        self.assertIn("conclusion_json:", output)

    def test_campaign_run_ollama_provider_retries_invalid_proposal_with_feedback(self) -> None:
        payload = campaign_payload()
        payload["provider"] = "ollama"
        invalid_payload = {
            "schema_version": "campaign_candidate_choice.v1",
            "action": "choose_candidate",
            "candidate_id": "missing",
            "rationale": "Try a missing candidate.",
        }
        valid_payload = {
            "schema_version": "campaign_candidate_choice.v1",
            "action": "choose_candidate",
            "candidate_id": "spy_price_vs_sma_trend_003",
            "rationale": "Retry with a candidate ID present in the bounded menu.",
        }
        responses = [invalid_payload, valid_payload]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(payload), encoding="utf-8")

            def fake_post(url: str, request_payload: dict, timeout_seconds: float) -> dict:
                return {"choices": [{"message": {"content": json.dumps(responses.pop(0))}}]}

            with patch("quant_lab.campaign_candidate_provider._post_json", side_effect=fake_post):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    exit_code = main(
                        [
                            "campaign",
                            "run",
                            "--config",
                            str(config_path),
                            "--out",
                            str(out_dir),
                            "--model",
                            "model",
                        ]
                    )

            cycle_dir = out_dir / "cycles" / "cycle_001"
            final_proposal = json.loads((cycle_dir / "proposal.json").read_text(encoding="utf-8"))
            first_validation = json.loads(
                (cycle_dir / "provider_attempt_001" / "candidate_choice_validation.json").read_text(encoding="utf-8")
            )
            second_context = json.loads(
                (cycle_dir / "provider_attempt_002" / "provider_context.json").read_text(encoding="utf-8")
            )
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertFalse(first_validation["valid"])
        self.assertEqual(final_proposal["title"], "SPY SMA 200 long/cash campaign baseline")
        self.assertTrue(any("candidate_id is not in candidate menu" in item for item in second_context["prior_attempt_feedback"]))
        self.assertIn("provider_attempt_1: valid=False", output)
        self.assertIn("provider_attempt_2: valid=True", output)
        self.assertNotIn("provider_fallback", output)

    def test_campaign_run_ollama_provider_failure_writes_error_receipt(self) -> None:
        payload = campaign_payload()
        payload["provider"] = "ollama"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "campaign.json"
            out_dir = root / "campaign"
            config_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch("quant_lab.campaign_candidate_provider._post_json", side_effect=RuntimeError("provider timed out")):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    exit_code = main(
                        [
                            "campaign",
                            "run",
                            "--config",
                            str(config_path),
                            "--out",
                            str(out_dir),
                            "--model",
                            "model",
                            "--execute-model-proposal",
                        ]
                    )

            cycle_dir = out_dir / "cycles" / "cycle_001"
            first_attempt_dir = cycle_dir / "provider_attempt_001"
            second_attempt_dir = cycle_dir / "provider_attempt_002"
            error_json_path = first_attempt_dir / "provider_error.json"
            error_markdown_path = first_attempt_dir / "provider_error.md"
            second_error_json_path = second_attempt_dir / "provider_error.json"
            proposal_path = cycle_dir / "proposal.json"
            strategy_path = cycle_dir / "strategy.json"
            error_exists = error_json_path.exists()
            error_markdown_exists = error_markdown_path.exists()
            second_error_exists = second_error_json_path.exists()
            fallback_proposal_exists = proposal_path.exists()
            strategy_exists = strategy_path.exists()
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertTrue(error_exists)
        self.assertTrue(error_markdown_exists)
        self.assertTrue(second_error_exists)
        self.assertTrue(fallback_proposal_exists)
        self.assertFalse(strategy_exists)
        self.assertIn("provider_fallback: deterministic", output)
        self.assertIn("execution: skipped_provider_dry_run", output)
        self.assertIn("did not come from a model response", output)


if __name__ == "__main__":
    unittest.main()
