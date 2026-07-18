"""CLI command handlers for backtest runs and the research index."""

from __future__ import annotations

import argparse

import pandas as pd

from .costs import CostAssumptions, resolve_cost_assumptions
from .data_quality import build_data_quality_report
from .research_index import format_index_csv, filter_index_records, format_index_table, load_research_index, sort_index_records
from .research_registry import require_experiment
from .run_artifacts import run_single_backtest
from .run_config import RunExecutionConfig
from .run_notes import load_research_note, save_research_note
from .strategy_schema import load_strategy


def resolve_cli_costs(args: argparse.Namespace) -> CostAssumptions:
    return resolve_cost_assumptions(
        cost_preset=args.cost_preset,
        commission_fixed=args.commission_fixed,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
    )


def run_command(args: argparse.Namespace) -> int:
    args.cost_assumptions = resolve_cli_costs(args)
    require_experiment(args.experiments_path, args.experiment_id)
    config = RunExecutionConfig.from_args(args)
    strategy_spec = load_strategy(args.strategy)
    data = pd.read_csv(args.data)
    data_quality = build_data_quality_report(data)
    run_name = args.run_name or strategy_spec.name
    note = load_research_note(args)
    research_note_path = save_research_note(note, args.out) if note is not None else None
    run_output = run_single_backtest(
        config=config,
        data=data,
        data_quality=data_quality,
        strategy_spec=strategy_spec,
        output_dir=args.out,
        run_name=run_name,
        research_note_path=research_note_path,
    )

    print(f"Run complete: {run_name}")
    for artifact_name in sorted(run_output.artifact_paths):
        print(f"{artifact_name}: {run_output.artifact_paths[artifact_name]}")
    print(f"final_equity: {run_output.final_equity:.2f}")
    print(f"total_return: {run_output.total_return:.2%}")
    print(f"benchmark: {run_output.benchmark_name}")
    print(f"benchmark_total_return: {run_output.benchmark_total_return:.2%}")
    print(f"excess_total_return: {run_output.excess_total_return:.2%}")
    print(f"cost_preset: {config.cost_assumptions.preset}")
    print(f"commission_fixed: {config.cost_assumptions.commission_fixed}")
    print(f"commission_rate: {config.cost_assumptions.commission_rate}")
    print(f"slippage_bps: {config.cost_assumptions.slippage_bps}")
    return 0


def list_runs_command(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")

    records = load_research_index(args.index_path)
    records = filter_index_records(
        records,
        symbol=args.symbol,
        strategy_id=args.strategy_id,
        run_type=args.run_type,
        experiment_id=args.experiment_id,
    )
    records = sort_index_records(records, args.sort, descending=not args.ascending)
    records = records[: args.limit]

    if not records:
        print(f"No runs found in {args.index_path}")
        return 0

    if args.csv:
        print(format_index_csv(records))
    else:
        print(format_index_table(records))
    return 0
