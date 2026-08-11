"""CLI handlers for campaign orchestration."""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, replace
from pathlib import Path

from .campaign import (
    CampaignConfig,
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
from .campaign_candidate_choice import (
    CampaignCandidateChoiceValidation,
    save_campaign_candidate_choice_artifacts,
    validate_campaign_candidate_choice,
)
from .campaign_candidate_provider import CampaignCandidateProviderResult, campaign_candidate_provider_result
from .campaign_candidates import (
    build_campaign_candidate_menu,
    campaign_candidate_to_proposal,
    find_campaign_candidate,
    save_campaign_candidate_menu,
)
from .campaign_proposal import (
    CampaignProposalValidation,
    save_campaign_proposal_artifacts,
    validate_campaign_proposal,
)
from .campaign_provider import CampaignProviderResult, campaign_provider_result, save_campaign_provider_error_artifacts
from .campaign_report import save_final_campaign_report


@dataclass(frozen=True)
class CampaignProposalSelection:
    provider_result: CampaignProviderResult
    validation: CampaignProposalValidation
    proposal_path: str
    validation_path: str
    validation_markdown_path: str
    diagnostics: list[str]


@dataclass(frozen=True)
class CampaignCycleResult:
    exit_code: int
    stop_loop: bool


@dataclass(frozen=True)
class CampaignCandidateChoiceSelection:
    provider_result: CampaignCandidateProviderResult
    validation: CampaignCandidateChoiceValidation
    choice_path: str
    validation_path: str
    validation_markdown_path: str
    diagnostics: list[str]


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


def campaign_candidates_command(args: argparse.Namespace) -> int:
    paths = campaign_paths(args.campaign)
    config = load_campaign_config(paths.config_path)
    state = load_campaign_state(paths.state_path)
    cycle_dir = _cycle_dir(paths.cycles_dir, state.cycle_number + 1)
    menu = build_campaign_candidate_menu(
        config,
        state,
        opportunity_catalog_dir=args.opportunity_catalog,
        experiment_template_catalog_dir=args.experiment_template_catalog,
        parameter_neighborhoods_dir=args.parameter_neighborhoods,
    )
    json_path, markdown_path = save_campaign_candidate_menu(menu, cycle_dir)
    print(f"candidate_menu: {json_path}")
    print(f"read_first: {markdown_path}")
    print(f"status: {menu.status}")
    print(f"candidates: {len(menu.candidates)}")
    print(f"rejected_candidates: {len(menu.rejected_candidates)}")
    return 0


def campaign_choose_candidate_command(args: argparse.Namespace) -> int:
    paths = campaign_paths(args.campaign)
    config = load_campaign_config(paths.config_path)
    state = load_campaign_state(paths.state_path)
    cycle_dir = _cycle_dir(paths.cycles_dir, state.cycle_number + 1)
    menu = build_campaign_candidate_menu(
        config,
        state,
        opportunity_catalog_dir=args.opportunity_catalog,
        experiment_template_catalog_dir=args.experiment_template_catalog,
        parameter_neighborhoods_dir=args.parameter_neighborhoods,
    )
    menu_json_path, menu_markdown_path = save_campaign_candidate_menu(menu, cycle_dir)
    selection = _select_campaign_candidate_choice(args, config=config, state=state, menu=menu, cycle_dir=cycle_dir)
    print(f"candidate_menu: {menu_json_path}")
    print(f"candidate_menu_read_first: {menu_markdown_path}")
    print(f"choice: {selection.choice_path}")
    print(f"choice_validation: {selection.validation_path}")
    print(f"choice_read_first: {selection.validation_markdown_path}")
    for diagnostic in selection.diagnostics:
        print(diagnostic)
    provider_result = selection.provider_result
    if provider_result.context_path:
        print(f"provider_context: {provider_result.context_path}")
    if provider_result.prompt_path:
        print(f"provider_prompt: {provider_result.prompt_path}")
    if provider_result.raw_response_path:
        print(f"provider_raw_response: {provider_result.raw_response_path}")
    if provider_result.parsed_choice_path:
        print(f"provider_choice: {provider_result.parsed_choice_path}")
    print(f"valid: {selection.validation.valid}")
    print(f"action: {provider_result.choice.action}")
    print(f"selected_candidate_id: {provider_result.choice.candidate_id or '-'}")
    if selection.validation.reasons:
        print("reasons:")
        for reason in selection.validation.reasons:
            print(f"- {reason}")
    if not selection.validation.valid:
        return 1
    if provider_result.choice.action != "choose_candidate":
        print("execution: skipped")
        return 0

    candidate = find_campaign_candidate(menu, provider_result.choice.candidate_id or "")
    if candidate is None:
        raise ValueError("validated candidate choice could not be found in menu")
    proposal = campaign_candidate_to_proposal(candidate)
    proposal_validation = validate_campaign_proposal(proposal, config=config, state=state)
    proposal_path, proposal_validation_path, proposal_markdown_path = save_campaign_proposal_artifacts(
        proposal,
        proposal_validation,
        cycle_dir,
    )
    print(f"proposal: {proposal_path}")
    print(f"proposal_validation: {proposal_validation_path}")
    print(f"proposal_read_first: {proposal_markdown_path}")
    print(f"proposal_valid: {proposal_validation.valid}")
    print("execution: skipped_candidate_choice")
    return 0 if proposal_validation.valid else 1


def campaign_run_command(args: argparse.Namespace) -> int:
    paths = campaign_paths(args.out)
    exists = _campaign_exists(paths)
    if args.config:
        config = load_campaign_config(args.config)
        if _has_campaign_initialization_overrides(args):
            if args.resume and exists:
                raise ValueError("campaign initialization overrides can only initialize a new campaign, not resume one")
            config = _config_with_initialization_overrides(config, args)
        if not args.resume or not exists:
            initialize_campaign(config, args.out, overwrite=args.force)
    else:
        if _has_campaign_initialization_overrides(args):
            raise ValueError("campaign initialization overrides require --config so a new campaign config can be written")
        config = load_campaign_config(paths.config_path)

    state = load_campaign_state(paths.state_path)
    if args.provider is not None and args.provider != config.provider:
        raise ValueError("campaign run provider override is not persisted yet; update the config file for now")

    if getattr(args, "loop", False):
        return _run_campaign_loop(args, config=config, paths=paths)
    return _run_one_campaign_cycle(args, config=config, state=state, paths=paths).exit_code


def _select_campaign_candidate_choice(
    args: argparse.Namespace,
    *,
    config: CampaignConfig,
    state,
    menu,
    cycle_dir: str,
) -> CampaignCandidateChoiceSelection:
    if config.provider == "deterministic":
        provider_result = campaign_candidate_provider_result(config, state, menu, cycle_dir=cycle_dir)
        validation = validate_campaign_candidate_choice(provider_result.choice, menu=menu)
        choice_path, validation_path, validation_markdown_path = save_campaign_candidate_choice_artifacts(
            provider_result.choice,
            validation,
            cycle_dir,
        )
        return CampaignCandidateChoiceSelection(
            provider_result=provider_result,
            validation=validation,
            choice_path=choice_path,
            validation_path=validation_path,
            validation_markdown_path=validation_markdown_path,
            diagnostics=[],
        )
    return _select_model_candidate_choice(args, config=config, state=state, menu=menu, cycle_dir=cycle_dir)


def _select_model_candidate_choice(
    args: argparse.Namespace,
    *,
    config: CampaignConfig,
    state,
    menu,
    cycle_dir: str,
) -> CampaignCandidateChoiceSelection:
    diagnostics: list[str] = []
    last_selection: CampaignCandidateChoiceSelection | None = None
    retry_feedback: list[str] = []
    for attempt_number in (1, 2):
        attempt_dir = str(Path(cycle_dir) / f"provider_attempt_{attempt_number:03d}")
        try:
            provider_result = campaign_candidate_provider_result(
                config,
                state,
                menu,
                cycle_dir=attempt_dir,
                base_url=getattr(args, "base_url", None),
                model=getattr(args, "model", None),
                timeout_seconds=getattr(args, "timeout_seconds", 60.0),
                prior_attempt_feedback=retry_feedback,
            )
        except Exception as exc:
            feedback = f"attempt {attempt_number} provider error: {exc}"
            error_json_path, error_markdown_path = save_campaign_provider_error_artifacts(
                cycle_dir=attempt_dir,
                provider=config.provider,
                error=feedback,
            )
            retry_feedback.append(feedback)
            diagnostics.extend(
                [
                    f"provider_attempt_{attempt_number}: failed",
                    f"provider_error_{attempt_number}: {error_json_path}",
                    f"provider_error_read_first_{attempt_number}: {error_markdown_path}",
                ]
            )
            continue

        validation = validate_campaign_candidate_choice(provider_result.choice, menu=menu)
        attempt_choice_path, attempt_validation_path, attempt_markdown_path = save_campaign_candidate_choice_artifacts(
            provider_result.choice,
            validation,
            attempt_dir,
        )
        diagnostics.extend(
            [
                f"provider_attempt_{attempt_number}: valid={validation.valid}",
                f"provider_attempt_choice_{attempt_number}: {attempt_choice_path}",
                f"provider_attempt_validation_{attempt_number}: {attempt_validation_path}",
                f"provider_attempt_read_first_{attempt_number}: {attempt_markdown_path}",
            ]
        )
        selection = _save_final_candidate_choice(
            provider_result=provider_result,
            validation=validation,
            cycle_dir=cycle_dir,
            diagnostics=diagnostics,
        )
        last_selection = selection
        if validation.valid:
            return selection
        retry_feedback.extend([f"attempt {attempt_number} validation error: {reason}" for reason in validation.reasons])

    fallback_result = campaign_candidate_provider_result(replace(config, provider="deterministic"), state, menu, cycle_dir=None)
    fallback_validation = validate_campaign_candidate_choice(fallback_result.choice, menu=menu)
    diagnostics = [
        *diagnostics,
        "provider_fallback: deterministic",
        "provider_fallback_reason: model provider did not produce a valid candidate choice after one retry",
    ]
    if fallback_validation.valid:
        return _save_final_candidate_choice(
            provider_result=replace(fallback_result, provider=config.provider),
            validation=fallback_validation,
            cycle_dir=cycle_dir,
            diagnostics=diagnostics,
        )
    if last_selection is not None:
        return last_selection
    return _save_final_candidate_choice(
        provider_result=replace(fallback_result, provider=config.provider),
        validation=fallback_validation,
        cycle_dir=cycle_dir,
        diagnostics=diagnostics,
    )


def _save_final_candidate_choice(
    *,
    provider_result: CampaignCandidateProviderResult,
    validation: CampaignCandidateChoiceValidation,
    cycle_dir: str,
    diagnostics: list[str],
) -> CampaignCandidateChoiceSelection:
    choice_path, validation_path, validation_markdown_path = save_campaign_candidate_choice_artifacts(
        provider_result.choice,
        validation,
        cycle_dir,
    )
    return CampaignCandidateChoiceSelection(
        provider_result=provider_result,
        validation=validation,
        choice_path=choice_path,
        validation_path=validation_path,
        validation_markdown_path=validation_markdown_path,
        diagnostics=list(diagnostics),
    )


def _run_campaign_loop(args: argparse.Namespace, *, config: CampaignConfig, paths) -> int:
    max_iterations = config.max_cycles + 1
    started_at = time.monotonic()
    duration_seconds = config.duration_minutes * 60
    print("Campaign loop starting")
    for iteration in range(1, max_iterations + 1):
        state = load_campaign_state(paths.state_path)
        if state.status != "running":
            print(f"Campaign loop stopped: status={state.status}")
            return 0
        if time.monotonic() - started_at >= duration_seconds:
            updated_state = complete_campaign_state(state, stop_reason="duration wall-clock limit reached")
            save_campaign_state(updated_state, paths.output_dir, config=config)
            final_json_path, final_markdown_path = save_final_campaign_report(config, updated_state, paths)
            print("Campaign loop stopped: duration limit reached")
            print(f"state: {paths.state_path}")
            print(f"final_report: {final_markdown_path}")
            print(f"final_report_json: {final_json_path}")
            return 0
        print(f"Campaign loop cycle: {iteration}")
        result = _run_one_campaign_cycle(args, config=config, state=state, paths=paths)
        if result.stop_loop or result.exit_code != 0:
            print(f"Campaign loop stopped: exit_code={result.exit_code}")
            return result.exit_code
    print("Campaign loop stopped: max loop iterations reached")
    return 1


def _run_one_campaign_cycle(args: argparse.Namespace, *, config: CampaignConfig, state, paths) -> CampaignCycleResult:
    cycle_dir = _cycle_dir(paths.cycles_dir, state.cycle_number + 1)
    selection = _select_campaign_proposal(args, config=config, state=state, cycle_dir=cycle_dir)
    provider_result = selection.provider_result
    proposal = provider_result.proposal
    validation = selection.validation
    proposal_path = selection.proposal_path
    validation_path = selection.validation_path
    validation_markdown_path = selection.validation_markdown_path

    print(f"Campaign proposal written: {proposal_path}")
    print(f"validation: {validation_path}")
    print(f"read_first: {validation_markdown_path}")
    for diagnostic in selection.diagnostics:
        print(diagnostic)
    if provider_result.context_path:
        print(f"provider_context: {provider_result.context_path}")
    if provider_result.prompt_path:
        print(f"provider_prompt: {provider_result.prompt_path}")
    if provider_result.raw_response_path:
        print(f"provider_raw_response: {provider_result.raw_response_path}")
    if provider_result.parsed_proposal_path:
        print(f"provider_proposal: {provider_result.parsed_proposal_path}")
    print(f"valid: {validation.valid}")
    print(f"projected_run_count: {validation.projected_run_count}")
    if validation.reasons:
        print("reasons:")
        for reason in validation.reasons:
            print(f"- {reason}")
    if _should_skip_model_execution(args, config=config, provider_result=provider_result, validation=validation):
        print(f"execution: skipped_provider_dry_run")
        print(f"provider: {config.provider}")
        if getattr(args, "execute_model_proposal", False):
            print("note: model execution was requested, but the selected proposal did not come from a model response")
        else:
            print("note: pass --execute-model-proposal to run a valid model proposal")
        return CampaignCycleResult(exit_code=0, stop_loop=True)
    elif validation.valid and proposal.action == "run_experiment":
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
        return CampaignCycleResult(exit_code=0, stop_loop=False)
    elif validation.valid and proposal.action == "stop_campaign":
        updated_state = complete_campaign_state(state, stop_reason=proposal.rationale)
        save_campaign_state(updated_state, paths.output_dir, config=config)
        final_json_path, final_markdown_path = save_final_campaign_report(config, updated_state, paths)
        print("execution: skipped")
        print(f"state: {paths.state_path}")
        print(f"final_report: {final_markdown_path}")
        print(f"final_report_json: {final_json_path}")
        return CampaignCycleResult(exit_code=0, stop_loop=True)
    elif validation.valid and proposal.action == "request_human_review":
        print("execution: skipped_human_review")
        print(f"provider: {config.provider}")
        print("note: review the provider prompt and supply a valid campaign proposal before execution")
        return CampaignCycleResult(exit_code=0, stop_loop=True)
    else:
        print("execution: skipped")
        return CampaignCycleResult(exit_code=0 if validation.valid else 1, stop_loop=True)


def _should_skip_model_execution(
    args: argparse.Namespace,
    *,
    config: CampaignConfig,
    provider_result: CampaignProviderResult,
    validation: CampaignProposalValidation,
) -> bool:
    if config.provider == "deterministic":
        return False
    if not validation.valid or provider_result.proposal.action != "run_experiment":
        return False
    if not getattr(args, "execute_model_proposal", False):
        return True
    return provider_result.raw_response is None


def _select_campaign_proposal(
    args: argparse.Namespace,
    *,
    config: CampaignConfig,
    state,
    cycle_dir: str,
) -> CampaignProposalSelection:
    if config.provider == "deterministic":
        provider_result = campaign_provider_result(config, state, cycle_dir=cycle_dir)
        validation = validate_campaign_proposal(provider_result.proposal, config=config, state=state)
        proposal_path, validation_path, validation_markdown_path = save_campaign_proposal_artifacts(
            provider_result.proposal,
            validation,
            cycle_dir,
        )
        return CampaignProposalSelection(
            provider_result=provider_result,
            validation=validation,
            proposal_path=proposal_path,
            validation_path=validation_path,
            validation_markdown_path=validation_markdown_path,
            diagnostics=[],
        )

    return _select_model_campaign_proposal(args, config=config, state=state, cycle_dir=cycle_dir)


def _select_model_campaign_proposal(
    args: argparse.Namespace,
    *,
    config: CampaignConfig,
    state,
    cycle_dir: str,
) -> CampaignProposalSelection:
    diagnostics: list[str] = []
    last_selection: CampaignProposalSelection | None = None
    retry_feedback: list[str] = []
    for attempt_number in (1, 2):
        attempt_dir = str(Path(cycle_dir) / f"provider_attempt_{attempt_number:03d}")
        try:
            provider_result = campaign_provider_result(
                config,
                state,
                cycle_dir=attempt_dir,
                base_url=getattr(args, "base_url", None),
                model=getattr(args, "model", None),
                timeout_seconds=getattr(args, "timeout_seconds", 60.0),
                prior_attempt_feedback=retry_feedback,
            )
        except Exception as exc:
            feedback = f"attempt {attempt_number} provider error: {exc}"
            error_json_path, error_markdown_path = save_campaign_provider_error_artifacts(
                cycle_dir=attempt_dir,
                provider=config.provider,
                error=feedback,
            )
            retry_feedback.append(feedback)
            diagnostics.extend(
                [
                    f"provider_attempt_{attempt_number}: failed",
                    f"provider_error_{attempt_number}: {error_json_path}",
                    f"provider_error_read_first_{attempt_number}: {error_markdown_path}",
                ]
            )
            continue

        validation = validate_campaign_proposal(provider_result.proposal, config=config, state=state)
        attempt_proposal_path, attempt_validation_path, attempt_validation_markdown_path = save_campaign_proposal_artifacts(
            provider_result.proposal,
            validation,
            attempt_dir,
        )
        diagnostics.extend(
            [
                f"provider_attempt_{attempt_number}: valid={validation.valid}",
                f"provider_attempt_proposal_{attempt_number}: {attempt_proposal_path}",
                f"provider_attempt_validation_{attempt_number}: {attempt_validation_path}",
                f"provider_attempt_read_first_{attempt_number}: {attempt_validation_markdown_path}",
            ]
        )
        selection = _save_final_cycle_proposal(
            provider_result=provider_result,
            validation=validation,
            cycle_dir=cycle_dir,
            diagnostics=diagnostics,
        )
        last_selection = selection
        if validation.valid:
            return selection
        retry_feedback.extend([f"attempt {attempt_number} validation error: {reason}" for reason in validation.reasons])

    fallback_selection = _deterministic_fallback_selection(config, state, cycle_dir=cycle_dir, diagnostics=diagnostics)
    if fallback_selection is not None:
        return fallback_selection
    if last_selection is not None:
        return last_selection
    return _provider_failure_stop_selection(config, state, cycle_dir=cycle_dir, diagnostics=diagnostics)


def _save_final_cycle_proposal(
    *,
    provider_result: CampaignProviderResult,
    validation: CampaignProposalValidation,
    cycle_dir: str,
    diagnostics: list[str],
) -> CampaignProposalSelection:
    proposal_path, validation_path, validation_markdown_path = save_campaign_proposal_artifacts(
        provider_result.proposal,
        validation,
        cycle_dir,
    )
    return CampaignProposalSelection(
        provider_result=provider_result,
        validation=validation,
        proposal_path=proposal_path,
        validation_path=validation_path,
        validation_markdown_path=validation_markdown_path,
        diagnostics=list(diagnostics),
    )


def _deterministic_fallback_selection(
    config: CampaignConfig,
    state,
    *,
    cycle_dir: str,
    diagnostics: list[str],
) -> CampaignProposalSelection | None:
    fallback_config = replace(config, provider="deterministic")
    provider_result = campaign_provider_result(fallback_config, state, cycle_dir=None)
    validation = validate_campaign_proposal(provider_result.proposal, config=config, state=state)
    if not validation.valid:
        return None
    diagnostics = [
        *diagnostics,
        "provider_fallback: deterministic",
        "provider_fallback_reason: model provider did not produce a valid proposal after one retry",
    ]
    return _save_final_cycle_proposal(
        provider_result=replace(provider_result, provider=config.provider),
        validation=validation,
        cycle_dir=cycle_dir,
        diagnostics=diagnostics,
    )


def _provider_failure_stop_selection(
    config: CampaignConfig,
    state,
    *,
    cycle_dir: str,
    diagnostics: list[str],
) -> CampaignProposalSelection:
    fallback_config = replace(config, provider="deterministic")
    provider_result = campaign_provider_result(fallback_config, state, cycle_dir=None)
    validation = validate_campaign_proposal(provider_result.proposal, config=config, state=state)
    diagnostics = [
        *diagnostics,
        "provider_fallback: deterministic_unvalidated",
        "provider_fallback_reason: no provider proposal could be parsed; returning deterministic proposal for inspection",
    ]
    return _save_final_cycle_proposal(
        provider_result=replace(provider_result, provider=config.provider),
        validation=validation,
        cycle_dir=cycle_dir,
        diagnostics=diagnostics,
    )


def _campaign_exists(paths) -> bool:
    return Path(paths.config_path).exists() and Path(paths.state_path).exists()


def _cycle_dir(cycles_dir: str, cycle_number: int) -> str:
    return str(Path(cycles_dir) / f"cycle_{cycle_number:03d}")


def _has_campaign_initialization_overrides(args: argparse.Namespace) -> bool:
    return (
        getattr(args, "provider", None) is not None
        or getattr(args, "duration", None) is not None
        or getattr(args, "max_cycles", None) is not None
        or getattr(args, "max_total_runs", None) is not None
    )


def _config_with_initialization_overrides(config: CampaignConfig, args: argparse.Namespace) -> CampaignConfig:
    updates = {}
    if getattr(args, "provider", None) is not None:
        updates["provider"] = args.provider
    if getattr(args, "duration", None) is not None:
        updates["duration_minutes"] = _parse_duration_minutes(args.duration)
    if getattr(args, "max_cycles", None) is not None:
        updates["max_cycles"] = _positive_int(args.max_cycles, "--max-cycles")
    if getattr(args, "max_total_runs", None) is not None:
        updates["max_total_runs"] = _positive_int(args.max_total_runs, "--max-total-runs")
    return replace(config, **updates)


def _parse_duration_minutes(value: str) -> int:
    cleaned = str(value).strip().lower()
    if not cleaned:
        raise ValueError("--duration must not be empty")
    if cleaned.endswith("m"):
        return _positive_int(cleaned[:-1], "--duration")
    if cleaned.endswith("h"):
        return _positive_int(cleaned[:-1], "--duration") * 60
    if cleaned.endswith("s"):
        seconds = _positive_int(cleaned[:-1], "--duration")
        return max(1, (seconds + 59) // 60)
    return _positive_int(cleaned, "--duration")


def _positive_int(value, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return parsed
