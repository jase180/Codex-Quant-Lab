"""CLI handlers for portfolio batch planning."""

from __future__ import annotations

import argparse

from .portfolio_batch import plan_portfolio_batch, portfolio_batch_manifest_path


def portfolio_batch_plan_command(args: argparse.Namespace) -> int:
    manifest = plan_portfolio_batch(
        portfolios_dir=args.portfolios,
        output_dir=args.out,
        initial_cash=args.initial_cash,
        cost_preset=args.cost_preset,
        experiments_path=args.experiments_path,
        index_path=args.index_path,
        force=args.force,
    )
    print(f"Portfolio batch manifest written: {portfolio_batch_manifest_path(args.out)}")
    print(f"planned_runs: {manifest.item_count}")
    for item in manifest.items:
        print(f"{item.portfolio_id}: {item.output_dir}")
    return 0
