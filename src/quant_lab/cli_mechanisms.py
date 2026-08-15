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
from .research_datasets import (
    dataset_plans_for_mechanism,
    format_dataset_plan_list,
    format_dataset_plans_for_mechanism,
    load_research_dataset_plans,
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


def mechanisms_data_plan_command(args: argparse.Namespace) -> int:
    plans = load_research_dataset_plans(args.dataset_plan_dir)
    if args.id is None:
        print(format_dataset_plan_list(plans))
        return 0

    mechanisms = load_research_mechanisms(args.catalog_dir)
    mechanism = find_research_mechanism(mechanisms, args.id)
    if mechanism is None:
        print(f"No research mechanism found with id: {args.id}")
        return 1
    matching = dataset_plans_for_mechanism(plans, args.id)
    print(format_dataset_plans_for_mechanism(args.id, matching))
    return 0
