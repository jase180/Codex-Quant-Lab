"""CLI command handlers for local-agent advisor helpers."""

from __future__ import annotations

import argparse

from .agent_cycle import agent_cycle_to_json, format_agent_cycle_markdown, run_agent_cycle
from .agent_context import agent_context_to_json, build_agent_context, save_agent_context
from .agent_recommendation import (
    AgentRecommendation,
    agent_recommendation_to_json,
    format_agent_recommendation_markdown,
    load_agent_recommendation,
    save_agent_recommendation,
)
from .agent_suggest import save_agent_suggestion, suggest_from_manifest


def _print_written_artifacts(label: str, json_path: str, markdown_path: str) -> None:
    print(f"{label} written: {json_path}")
    print(f"markdown: {markdown_path}")


def _print_optional_command(label: str, command: str | None) -> None:
    if command:
        print(f"{label}:")
        print(command)
    else:
        print(f"{label}: -")


def _print_recommendation_summary(recommendation: AgentRecommendation) -> None:
    print(f"action: {recommendation.recommended_action}")
    print(f"confidence: {recommendation.confidence}")
    _print_optional_command("next_command", recommendation.next_command)


def agent_context_command(args: argparse.Namespace) -> int:
    context = build_agent_context(
        args.manifest,
        max_chars_per_file=args.max_chars_per_file,
    )
    json_path, markdown_path = save_agent_context(context, args.out_dir)

    if args.json:
        print(agent_context_to_json(context))
    else:
        _print_written_artifacts("Agent context", json_path, markdown_path)
        print(f"status: {context.manifest['current_status']}")
        print(f"read_first: {markdown_path}")
        if context.next_commands:
            print("next_command:")
            print(context.next_commands[0])
    return 0


def agent_validate_recommendation_command(args: argparse.Namespace) -> int:
    recommendation = load_agent_recommendation(args.recommendation)
    if args.out_dir is not None:
        json_path, markdown_path = save_agent_recommendation(recommendation, args.out_dir)

    if args.json:
        print(agent_recommendation_to_json(recommendation))
    elif args.out_dir is None:
        print("Agent recommendation: valid")
        _print_recommendation_summary(recommendation)
        if args.markdown:
            print(format_agent_recommendation_markdown(recommendation))
    else:
        _print_written_artifacts("Agent recommendation", json_path, markdown_path)
    return 0


def agent_suggest_command(args: argparse.Namespace) -> int:
    recommendation = suggest_from_manifest(
        args.manifest,
        provider=args.provider,
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
    )
    json_path, markdown_path = save_agent_suggestion(recommendation, args.manifest, args.out_dir)

    if args.json:
        print(agent_recommendation_to_json(recommendation))
    else:
        _print_written_artifacts("Agent recommendation", json_path, markdown_path)
        _print_recommendation_summary(recommendation)
        if args.markdown:
            print(format_agent_recommendation_markdown(recommendation))
    return 0


def agent_cycle_command(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("agent cycle currently supports --dry-run only")
        return 2

    result = run_agent_cycle(
        args.manifest,
        dry_run=args.dry_run,
        provider=args.provider,
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
        output_dir=args.out_dir,
    )

    if args.json:
        print(agent_cycle_to_json(result))
    else:
        _print_written_artifacts("Agent cycle", result.cycle_json_path, result.cycle_markdown_path)
        print(f"action: {result.recommended_action}")
        print(f"dry_run: {result.dry_run}")
        print(f"stop_reason: {result.stop_reason}")
        _print_optional_command("proposed_command", result.proposed_command)
        if args.markdown:
            print(format_agent_cycle_markdown(result))
    return 0
