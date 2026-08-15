"""CLI handlers for the research-mechanism catalog."""

from __future__ import annotations

import argparse

from .research_mechanisms import (
    find_research_mechanism,
    format_research_mechanism_data_needs,
    format_research_mechanism_detail,
    format_research_mechanism_list,
    load_research_mechanisms,
)


def mechanisms_list_command(args: argparse.Namespace) -> int:
    mechanisms = load_research_mechanisms(args.catalog_dir)
    print(format_research_mechanism_list(mechanisms))
    return 0


def mechanisms_show_command(args: argparse.Namespace) -> int:
    mechanisms = load_research_mechanisms(args.catalog_dir)
    mechanism = find_research_mechanism(mechanisms, args.id)
    if mechanism is None:
        print(f"No research mechanism found with id: {args.id}")
        return 1
    print(format_research_mechanism_detail(mechanism))
    return 0


def mechanisms_data_needs_command(args: argparse.Namespace) -> int:
    mechanisms = load_research_mechanisms(args.catalog_dir)
    print(format_research_mechanism_data_needs(mechanisms, engine_fit=args.engine_fit))
    return 0
