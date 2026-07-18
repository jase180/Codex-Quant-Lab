"""CLI command handlers for guided research plans."""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from .research_plan import create_research_plan, save_research_plan
from .research_registry import (
    append_experiment_record,
    create_experiment_record,
    load_experiments,
    next_experiment_id,
    normalize_tags,
)


def research_plan_init_command(args: argparse.Namespace) -> int:
    records = load_experiments(args.experiments_path)
    existing_ids = {record.experiment_id for record in records}
    experiment_id = args.experiment_id or next_experiment_id(records)
    if experiment_id not in existing_ids:
        record = create_experiment_record(
            experiment_id=experiment_id,
            title=args.title,
            hypothesis=args.hypothesis,
            status="planned",
            tags=normalize_tags(args.tag),
            strategy_path=args.strategy,
            data_path=args.data,
            notes="Created by research-plan init.",
        )
        append_experiment_record(record, args.experiments_path)

    plan = create_research_plan(
        title=args.title,
        hypothesis=args.hypothesis,
        strategy_path=args.strategy,
        data_path=args.data,
        symbol=args.symbol,
        experiment_id=experiment_id,
        experiments_path=args.experiments_path,
        index_path=args.index_path,
        output_dir=args.out,
        tags=args.tag,
    )
    json_path, markdown_path = save_research_plan(plan)
    baseline_command = build_baseline_run_command(args, experiment_id)

    print(f"Research plan created: {json_path}")
    print(f"markdown: {markdown_path}")
    print(f"experiment_id: {experiment_id}")
    print("next_command:")
    print(baseline_command)
    return 0


def build_baseline_run_command(args: argparse.Namespace, experiment_id: str) -> str:
    command = [
        "quant-lab",
        "run",
        "--strategy",
        str(args.strategy),
        "--data",
        str(args.data),
        "--out",
        str(Path(args.out) / "baseline"),
        "--initial-cash",
        str(args.initial_cash),
        "--quantity",
        str(args.quantity),
        "--sizing",
        str(args.sizing),
        "--allocation",
        str(args.allocation),
        "--benchmark",
        str(args.benchmark),
        "--cost-preset",
        str(args.cost_preset),
        "--experiments-path",
        str(args.experiments_path),
        "--experiment-id",
        experiment_id,
        "--index-path",
        str(args.index_path),
        "--note",
        f"Baseline for research plan: {args.hypothesis}",
    ]
    if args.commission_fixed is not None:
        command.extend(["--commission-fixed", str(args.commission_fixed)])
    if args.commission_rate is not None:
        command.extend(["--commission-rate", str(args.commission_rate)])
    if args.slippage_bps is not None:
        command.extend(["--slippage-bps", str(args.slippage_bps)])
    return shlex.join(command)
