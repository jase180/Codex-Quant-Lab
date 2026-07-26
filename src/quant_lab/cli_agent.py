"""CLI command handlers for local-agent advisor helpers."""

from __future__ import annotations

import argparse

from .agent_context import agent_context_to_json, build_agent_context, save_agent_context


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
