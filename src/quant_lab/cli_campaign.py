"""CLI handlers for campaign orchestration."""

from __future__ import annotations

import argparse
from pathlib import Path

from .campaign import (
    campaign_paths,
    format_campaign_status,
    initialize_campaign,
    load_campaign_config,
    load_campaign_state,
    save_campaign_state,
)
from .campaign_conversion import prepare_campaign_experiment_inputs
from .campaign_execution import execute_campaign_experiment_inputs
from .campaign_knowledge import complete_campaign_state, update_campaign_state_after_execution
from .campaign_proposal import (
    save_campaign_proposal_artifacts,
    validate_campaign_proposal,
)
from .campaign_provider import campaign_provider_proposal
from .campaign_report import save_final_campaign_report


def campaign_init_command(args: argparse.Namespace) -> int:
    config = load_campaign_config(args.config)
    paths = initialize_campaign(config, args.out, overwrite=args.force)
    print(f"Campaign initialized: {paths.output_dir}")
    print(f"config: {paths.config_path}")
    print(f"state: {paths.state_path}")
    print(f"read_first: {paths.state_markdown_path}")
    return 0


def campaign_status_command(args: argparse.Namespace) -> int:
    paths = campaign_paths(args.campaign)
    config = load_campaign_config(paths.config_path)
    state = load_campaign_state(paths.state_path)
    print(format_campaign_status(config, state, paths))
    return 0


def campaign_run_command(args: argparse.Namespace) -> int:
    paths = campaign_paths(args.out)
    if args.config:
        config = load_campaign_config(args.config)
        if not args.resume or not _campaign_exists(paths):
            initialize_campaign(config, args.out, overwrite=args.force)
    else:
        config = load_campaign_config(paths.config_path)

    state = load_campaign_state(paths.state_path)
    if args.provider is not None and args.provider != config.provider:
        raise ValueError("campaign run provider override is not persisted yet; update the config file for now")

    proposal = campaign_provider_proposal(config, state)
    validation = validate_campaign_proposal(proposal, config=config, state=state)
    cycle_dir = _cycle_dir(paths.cycles_dir, state.cycle_number + 1)
    proposal_path, validation_path, validation_markdown_path = save_campaign_proposal_artifacts(
        proposal,
        validation,
        cycle_dir,
    )

    print(f"Campaign proposal written: {proposal_path}")
    print(f"validation: {validation_path}")
    print(f"read_first: {validation_markdown_path}")
    print(f"valid: {validation.valid}")
    print(f"projected_run_count: {validation.projected_run_count}")
    if validation.reasons:
        print("reasons:")
        for reason in validation.reasons:
            print(f"- {reason}")
    if validation.valid and proposal.action == "run_experiment":
        inputs = prepare_campaign_experiment_inputs(proposal, config=config, cycle_dir=cycle_dir)
        print(f"strategy: {inputs.strategy_path}")
        print(f"run_default_args: {inputs.run_default_args_path}")
        print(f"planned_command: {inputs.run_default_command_path}")
        execution = execute_campaign_experiment_inputs(inputs)
        updated_state = update_campaign_state_after_execution(
            state,
            config=config,
            execution=execution,
            projected_run_count=validation.projected_run_count,
        )
        save_campaign_state(updated_state, paths.output_dir, config=config)
        print(f"execution: {execution.status}")
        print(f"execution_receipt: {execution.execution_json_path}")
        print(f"conclusion: {execution.conclusion_path or '-'}")
        print(f"conclusion_json: {execution.conclusion_json_path or '-'}")
        print(f"read_first: {execution.read_first_path or '-'}")
        print(f"state: {paths.state_path}")
        print(f"cycle_number: {updated_state.cycle_number}")
        print(f"runs_used: {updated_state.runs_used}")
    elif validation.valid and proposal.action == "stop_campaign":
        updated_state = complete_campaign_state(state, stop_reason=proposal.rationale)
        save_campaign_state(updated_state, paths.output_dir, config=config)
        final_json_path, final_markdown_path = save_final_campaign_report(config, updated_state, paths)
        print("execution: skipped")
        print(f"state: {paths.state_path}")
        print(f"final_report: {final_markdown_path}")
        print(f"final_report_json: {final_json_path}")
    else:
        print("execution: skipped")
    return 0 if validation.valid else 1


def _campaign_exists(paths) -> bool:
    return Path(paths.config_path).exists() and Path(paths.state_path).exists()


def _cycle_dir(cycles_dir: str, cycle_number: int) -> str:
    return str(Path(cycles_dir) / f"cycle_{cycle_number:03d}")
