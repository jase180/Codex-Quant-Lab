"""CLI handlers for portfolio batch planning."""

from __future__ import annotations

import argparse

from .portfolio_batch import (
    plan_portfolio_batch,
    portfolio_batch_manifest_path,
    portfolio_batch_result_path,
    portfolio_batch_summary_path,
    run_portfolio_batch,
    summarize_portfolio_batch,
)


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


def portfolio_batch_run_command(args: argparse.Namespace) -> int:
    result = run_portfolio_batch(
        manifest_path=args.manifest,
        experiment_id=args.experiment_id,
        continue_on_error=args.continue_on_error,
    )
    print(f"Portfolio batch result written: {portfolio_batch_result_path(args.manifest)}")
    print(f"planned_runs: {result.planned_count}")
    print(f"completed_runs: {result.completed_count}")
    print(f"failed_runs: {result.failed_count}")
    print(f"skipped_runs: {result.skipped_count}")
    for item in result.items:
        print(f"{item.status}: {item.portfolio_id}")
    return 1 if result.failed_count else 0


def portfolio_batch_summarize_command(args: argparse.Namespace) -> int:
    summary = summarize_portfolio_batch(
        manifest_path=args.manifest,
        output_path=args.out,
        max_planned_runs=args.max_planned_runs,
        min_completed_runs=args.min_completed_runs,
    )
    print(f"Portfolio batch summary written: {summary.summary_path}")
    print(f"planned_runs: {summary.planned_count}")
    print(f"completed_runs: {summary.completed_count}")
    print(f"failed_runs: {summary.failed_count}")
    print(f"skipped_runs: {summary.skipped_count}")
    print(f"warnings: {len(summary.warnings)}")
    for warning in summary.warnings:
        print(f"- {warning}")
    if summary.summary_path != str(portfolio_batch_summary_path(args.manifest)):
        print(f"default_summary_path: {portfolio_batch_summary_path(args.manifest)}")
    return 0
