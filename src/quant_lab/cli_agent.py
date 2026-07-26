"""CLI command handlers for local-agent advisor helpers."""

from __future__ import annotations

import argparse

from .agent_context import agent_context_to_json, build_agent_context, save_agent_context
from .agent_recommendation import (
    agent_recommendation_to_json,
    format_agent_recommendation_markdown,
    load_agent_recommendation,
    save_agent_recommendation,
)
from .agent_suggest import save_agent_suggestion, suggest_from_manifest


def agent_context_command(args: argparse.Namespace) -> int:
    context = build_agent_context(
        args.manifest,
        max_chars_per_file=args.max_chars_per_file,
    )
    json_path, markdown_path = save_agent_context(context, args.out_dir)

    if args.json:
        print(agent_context_to_json(context))
    else:
        print(f"Agent context written: {json_path}")
        print(f"markdown: {markdown_path}")
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
        print(f"action: {recommendation.recommended_action}")
        print(f"confidence: {recommendation.confidence}")
        if recommendation.next_command:
            print("next_command:")
            print(recommendation.next_command)
        else:
            print("next_command: -")
        if args.markdown:
            print(format_agent_recommendation_markdown(recommendation))
    else:
        print(f"Agent recommendation written: {json_path}")
        print(f"markdown: {markdown_path}")
    return 0


def agent_suggest_command(args: argparse.Namespace) -> int:
    recommendation = suggest_from_manifest(args.manifest)
    json_path, markdown_path = save_agent_suggestion(recommendation, args.manifest, args.out_dir)

    if args.json:
        print(agent_recommendation_to_json(recommendation))
    else:
        print(f"Agent recommendation written: {json_path}")
        print(f"markdown: {markdown_path}")
        print(f"action: {recommendation.recommended_action}")
        print(f"confidence: {recommendation.confidence}")
        if recommendation.next_command:
            print("next_command:")
            print(recommendation.next_command)
        else:
            print("next_command: -")
        if args.markdown:
            print(format_agent_recommendation_markdown(recommendation))
    return 0
