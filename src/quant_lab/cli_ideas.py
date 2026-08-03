"""CLI handlers for conceptual strategy idea suggestions."""

from __future__ import annotations

import argparse

from .strategy_ideas import format_strategy_idea_suggestion, suggest_strategy_idea


def ideas_suggest_command(args: argparse.Namespace) -> int:
    suggestion = suggest_strategy_idea(
        catalog_dir=args.catalog_dir,
        conclusions_dir=args.conclusions_dir,
    )
    print(format_strategy_idea_suggestion(suggestion))
    return 0
