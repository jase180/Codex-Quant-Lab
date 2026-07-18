"""CLI command handlers for portfolio research runs."""

from __future__ import annotations

import argparse

from .cli_runs import resolve_cli_costs
from .portfolio_candidates import write_portfolio_candidates
from .portfolio_execution import execute_portfolio_run
from .portfolio_templates import (
    available_portfolio_templates,
    build_portfolio_template,
    write_portfolio_template,
)
from .portfolio_variants import write_portfolio_variants


def list_portfolio_templates_command(args: argparse.Namespace) -> int:
    for template_name in available_portfolio_templates():
        print(template_name)
    return 0


def new_portfolio_command(args: argparse.Namespace) -> int:
    payload = build_portfolio_template(args.template)
    output_path = write_portfolio_template(payload, args.out, force=args.force)
    print(f"Portfolio template written: {output_path}")
    print(f"template: {args.template}")
    print(f"portfolio_id: {payload['portfolio_id']}")
    print(f"symbols: {', '.join(symbol['symbol'] for symbol in payload['symbols'])}")
    return 0


def portfolio_variants_command(args: argparse.Namespace) -> int:
    results = write_portfolio_variants(
        portfolio_path=args.portfolio,
        raw_weight_sets=args.weights,
        output_dir=args.out,
        rebalance_frequencies=args.rebalance,
        force=args.force,
    )
    print(f"Portfolio variants written: {len(results)}")
    for result in results:
        print(f"{result.portfolio_id}: {result.path}")
    return 0


def portfolio_candidates_command(args: argparse.Namespace) -> int:
    result = write_portfolio_candidates(
        symbols=args.symbols,
        step=args.step,
        data_dir=args.data_dir,
        output_dir=args.out,
        max_candidates=args.max_candidates,
        rebalance_frequency=args.rebalance,
        benchmark_symbol=args.benchmark_symbol,
        force=args.force,
    )
    print(f"Portfolio candidates written: {len(result.written)}")
    print(f"skipped_candidates: {result.skipped_count}")
    for written in result.written:
        print(f"{written.portfolio_id}: {written.path}")
    return 0


def portfolio_run_command(args: argparse.Namespace) -> int:
    args.cost_assumptions = resolve_cli_costs(args)
    run = execute_portfolio_run(
        portfolio_path=args.portfolio,
        output_dir=args.out,
        initial_cash=args.initial_cash,
        cost_assumptions=args.cost_assumptions,
        experiments_path=args.experiments_path,
        experiment_id=args.experiment_id,
        index_path=args.index_path,
        command=args.command_tokens,
    )

    print(f"Portfolio run complete: {run.portfolio_name}")
    for artifact_name in sorted(run.artifact_paths):
        print(f"{artifact_name}: {run.artifact_paths[artifact_name]}")
    print(f"final_equity: {run.final_equity:.2f}")
    print(f"total_return: {run.total_return:.2%}")
    print(f"benchmark: buy-and-hold {run.benchmark_symbol}")
    print(f"benchmark_total_return: {run.benchmark_total_return:.2%}")
    print(f"excess_total_return: {run.excess_total_return:.2%}")
    print(f"cost_preset: {run.cost_preset}")
    return 0
