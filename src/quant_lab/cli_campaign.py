"""CLI handlers for campaign orchestration."""

from __future__ import annotations

import argparse

from .campaign import (
    campaign_paths,
    format_campaign_status,
    initialize_campaign,
    load_campaign_config,
    load_campaign_state,
)


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
