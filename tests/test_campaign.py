from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
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


def conclusion_payload() -> dict:
    return {
        "schema_version": "experiment_conclusion.v1",
        "experiment_id": "EXP-123",
        "experiment": {
            "title": "SPY SMA 200 long/cash campaign baseline",
            "hypothesis": "A trend rule may reduce drawdown.",
        },
        "research_system_status": {"status": "valid"},
        "strategy_hypothesis_status": {"status": "rejected"},
        "confidence_label": "rejected",
        "current_conclusion": "The repo measured the idea correctly, but the strategy failed the criteria.",
        "do_not_repeat": ["Do not rerun the same SMA 200 long/cash branch unchanged."],
        "open_questions": ["Did adjusted prices affect the comparison?"],
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
        self.assertIn("quant-lab", command_markdown)
        self.assertIn("experiment", command_markdown)
        self.assertIn("run-default", command_markdown)

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
        self.assertEqual(updated.remaining_budget["runs"], 9)
        self.assertEqual(updated.completed_experiments[0]["research_system_status"], "valid")
        self.assertEqual(updated.completed_experiments[0]["strategy_hypothesis_status"], "rejected")
        self.assertIn("strategy failed", " ".join(updated.current_findings))
        self.assertIn("Do not rerun the same SMA 200 long/cash branch unchanged.", updated.do_not_repeat)
        self.assertIn(
            "Do not repeat unchanged rejected experiment: SPY SMA 200 long/cash campaign baseline.",
            updated.do_not_repeat,
        )
        self.assertIn("Did adjusted prices affect the comparison?", updated.unresolved_questions)
        repeated_proposal = deterministic_campaign_proposal(config, updated)
        repeated_validation = validate_campaign_proposal(repeated_proposal, config=config, state=updated)
        self.assertFalse(repeated_validation.valid)
        self.assertTrue(any("do_not_repeat" in reason for reason in repeated_validation.reasons))

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


if __name__ == "__main__":
    unittest.main()
