"""Command-line interface for Codex Quant Lab."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

from .costs import COST_PRESETS, CostAssumptions, resolve_cost_assumptions
from .data_fetch import fetch_market_data, write_market_data_csv
from .data_quality import build_data_quality_report
from .experiment_summary import format_experiment_decision_draft, format_experiment_evidence_summary
from .research_index import format_index_csv
from .research_index import filter_index_records, format_index_table, load_research_index, sort_index_records
from .research_registry import (
    EXPERIMENT_DECISION_OUTCOMES,
    EXPERIMENT_STATUSES,
    append_experiment_record,
    create_experiment_decision,
    create_experiment_record,
    decide_experiment_record,
    filter_experiments,
    find_experiment,
    format_experiment_csv,
    format_experiment_detail,
    format_experiment_table,
    link_runs_to_experiment,
    load_experiments,
    next_experiment_id,
    normalize_tags,
    replace_experiment_record,
    require_experiment,
    update_experiment_record,
)
from .run_inspection import format_run_comparison, format_run_summary, load_run_summaries, load_run_summary
from .run_artifacts import run_single_backtest
from .run_config import RunExecutionConfig
from .run_notes import load_research_note, save_research_note
from .run_metadata import command_tokens
from .strategy_schema import load_strategy
from .strategy_templates import (
    available_strategy_templates,
    build_strategy_template,
    write_strategy_template,
)
from .sweep_workflows import (
    build_sweep_variants,
    parse_param_sweeps,
    parse_walk_forward_windows,
    split_train_test_data,
    sweep_command,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quant-lab",
        description="Run Codex Quant Lab backtests and research workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one strategy against one OHLCV CSV.")
    run_parser.add_argument("--strategy", required=True, help="Path to a v1 strategy JSON file.")
    run_parser.add_argument("--data", required=True, help="Path to a daily OHLCV CSV file.")
    run_parser.add_argument("--out", required=True, help="Directory where run artifacts are written.")
    run_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash. Defaults to 100000.",
    )
    run_parser.add_argument(
        "--quantity",
        type=float,
        default=1,
        help="Order quantity for fixed-shares sizing. Defaults to 1.",
    )
    run_parser.add_argument(
        "--sizing",
        choices=["fixed-shares", "percent-equity"],
        default="fixed-shares",
        help="Position sizing mode. Defaults to fixed-shares.",
    )
    run_parser.add_argument(
        "--allocation",
        type=float,
        default=1.0,
        help="Cash fraction to invest for percent-equity buys. Defaults to 1.0.",
    )
    run_parser.add_argument(
        "--run-name",
        default=None,
        help="Report title. Defaults to the strategy name.",
    )
    add_cost_arguments(run_parser)
    add_benchmark_argument(run_parser)
    add_note_arguments(run_parser)
    add_experiment_registry_argument(run_parser)
    add_experiment_link_argument(run_parser)
    add_index_argument(run_parser)
    run_parser.set_defaults(func=run_command)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch daily market data into the local CSV cache.",
    )
    fetch_parser.add_argument("--symbol", required=True, help="Ticker symbol, such as SPY or QQQ.")
    fetch_parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format.")
    fetch_parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format.")
    fetch_parser.add_argument(
        "--out",
        default="data/cache",
        help="Directory where the normalized OHLCV CSV is written. Defaults to data/cache.",
    )
    fetch_parser.add_argument(
        "--interval",
        default="1d",
        help="Market data interval. Only 1d is supported for now.",
    )
    fetch_parser.set_defaults(func=fetch_command)

    template_list_parser = subparsers.add_parser(
        "list-strategy-templates",
        help="List built-in strategy templates.",
    )
    template_list_parser.set_defaults(func=list_strategy_templates_command)

    new_strategy_parser = subparsers.add_parser(
        "new-strategy",
        help="Create a valid v1 strategy JSON file from a built-in template.",
    )
    new_strategy_parser.add_argument(
        "--template",
        required=True,
        choices=available_strategy_templates(),
        help="Template name.",
    )
    new_strategy_parser.add_argument("--symbol", required=True, help="Market symbol, such as QQQ or SPY.")
    new_strategy_parser.add_argument("--out", required=True, help="Path where the strategy JSON is written.")
    new_strategy_parser.add_argument("--strategy-id", default=None, help="Optional strategy_id override.")
    new_strategy_parser.add_argument("--name", default=None, help="Optional display name override.")
    new_strategy_parser.add_argument("--force", action="store_true", help="Overwrite --out if it already exists.")
    new_strategy_parser.set_defaults(func=new_strategy_command)

    list_parser = subparsers.add_parser(
        "list-runs",
        help="List runs from the local research index.",
    )
    add_index_argument(list_parser)
    list_parser.add_argument("--symbol", default=None, help="Only show runs for one symbol, such as QQQ.")
    list_parser.add_argument("--strategy-id", default=None, help="Only show runs for one strategy id.")
    list_parser.add_argument("--experiment-id", default=None, help="Only show runs linked to one experiment id.")
    list_parser.add_argument(
        "--run-type",
        choices=[
            "run",
            "sweep_run",
            "train_sweep_run",
            "test_selected_run",
            "walk_forward_train_run",
            "walk_forward_test_run",
        ],
        default=None,
        help="Only show one run type.",
    )
    list_parser.add_argument("--csv", action="store_true", help="Print CSV instead of a fixed-width table.")
    list_parser.add_argument(
        "--sort",
        default="created_at_utc",
        choices=[
            "created_at_utc",
            "total_return",
            "benchmark_total_return",
            "excess_total_return",
            "sharpe_ratio",
            "max_drawdown",
            "trade_count",
        ],
        help="Index field to sort by. Defaults to created_at_utc.",
    )
    list_parser.add_argument(
        "--ascending",
        action="store_true",
        help="Sort smallest to largest. Defaults to descending.",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum rows to print. Defaults to 20.",
    )
    list_parser.set_defaults(func=list_runs_command)

    show_parser = subparsers.add_parser(
        "show-run",
        help="Inspect one saved run from run_metadata.json.",
    )
    show_parser.add_argument("--metadata", required=True, help="Path to a run_metadata.json file.")
    show_parser.set_defaults(func=show_run_command)

    compare_parser = subparsers.add_parser(
        "compare-runs",
        help="Compare two or more saved runs from run_metadata.json files.",
    )
    compare_parser.add_argument(
        "--metadata",
        action="append",
        required=True,
        help="Path to a run_metadata.json file. Provide at least two.",
    )
    compare_parser.set_defaults(func=compare_runs_command)

    new_experiment_parser = subparsers.add_parser(
        "new-experiment",
        help="Create a research experiment record.",
    )
    add_experiment_registry_argument(new_experiment_parser)
    new_experiment_parser.add_argument("--title", required=True, help="Short experiment title.")
    new_experiment_parser.add_argument("--hypothesis", required=True, help="Research hypothesis being tested.")
    new_experiment_parser.add_argument(
        "--experiment-id",
        default=None,
        help="Optional explicit id such as EXP-001. Defaults to the next local id.",
    )
    new_experiment_parser.add_argument(
        "--status",
        choices=EXPERIMENT_STATUSES,
        default="planned",
        help="Initial experiment status. Defaults to planned.",
    )
    new_experiment_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Experiment tag. May be repeated or comma-separated.",
    )
    new_experiment_parser.add_argument("--strategy", default=None, help="Optional strategy JSON path.")
    new_experiment_parser.add_argument("--data", default=None, help="Optional OHLCV CSV path.")
    new_experiment_parser.add_argument("--notes", default=None, help="Optional free-form notes.")
    new_experiment_parser.set_defaults(func=new_experiment_command)

    list_experiments_parser = subparsers.add_parser(
        "list-experiments",
        help="List research experiment records.",
    )
    add_experiment_registry_argument(list_experiments_parser)
    list_experiments_parser.add_argument(
        "--status",
        choices=EXPERIMENT_STATUSES,
        default=None,
        help="Only show experiments with this status.",
    )
    list_experiments_parser.add_argument("--tag", default=None, help="Only show experiments with this tag.")
    list_experiments_parser.add_argument("--csv", action="store_true", help="Print CSV instead of a table.")
    list_experiments_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum rows to print. Defaults to 20.",
    )
    list_experiments_parser.set_defaults(func=list_experiments_command)

    show_experiment_parser = subparsers.add_parser(
        "show-experiment",
        help="Show one research experiment record.",
    )
    add_experiment_registry_argument(show_experiment_parser)
    show_experiment_parser.add_argument("--experiment-id", required=True, help="Experiment id, such as EXP-001.")
    show_experiment_parser.set_defaults(func=show_experiment_command)

    update_experiment_parser = subparsers.add_parser(
        "update-experiment",
        help="Update experiment status, decision, notes, or tags.",
    )
    add_experiment_registry_argument(update_experiment_parser)
    update_experiment_parser.add_argument("--experiment-id", required=True, help="Experiment id, such as EXP-001.")
    update_experiment_parser.add_argument(
        "--status",
        choices=EXPERIMENT_STATUSES,
        default=None,
        help="New experiment status.",
    )
    update_experiment_parser.add_argument("--decision", default=None, help="Decision or conclusion text.")
    update_experiment_parser.add_argument("--notes", default=None, help="Replacement free-form notes.")
    update_experiment_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Tag to add. May be repeated or comma-separated.",
    )
    update_experiment_parser.set_defaults(func=update_experiment_command)

    decide_experiment_parser = subparsers.add_parser(
        "decide-experiment",
        help="Record a structured research decision for an experiment.",
    )
    add_experiment_registry_argument(decide_experiment_parser)
    decide_experiment_parser.add_argument("--experiment-id", required=True, help="Experiment id, such as EXP-001.")
    decide_experiment_parser.add_argument(
        "--outcome",
        required=True,
        choices=EXPERIMENT_DECISION_OUTCOMES,
        help="Research decision outcome. Accept/reject complete the experiment; continue keeps it running.",
    )
    decide_experiment_parser.add_argument("--rationale", required=True, help="Why this decision follows from evidence.")
    decide_experiment_parser.add_argument(
        "--supporting-run",
        default=None,
        help="Metadata path or run label for the strongest supporting evidence.",
    )
    decide_experiment_parser.add_argument(
        "--contradicting-run",
        default=None,
        help="Metadata path or run label for the strongest contradictory evidence.",
    )
    decide_experiment_parser.add_argument("--next-action", default=None, help="Concrete next research action.")
    decide_experiment_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Tag to add with the decision. May be repeated or comma-separated.",
    )
    decide_experiment_parser.set_defaults(func=decide_experiment_command)

    link_run_parser = subparsers.add_parser(
        "link-run",
        help="Attach one or more run metadata paths to an experiment record.",
    )
    add_experiment_registry_argument(link_run_parser)
    link_run_parser.add_argument("--experiment-id", required=True, help="Experiment id, such as EXP-001.")
    link_run_parser.add_argument(
        "--metadata",
        action="append",
        required=True,
        help="Path to a run_metadata.json file. May be provided more than once.",
    )
    link_run_parser.set_defaults(func=link_run_command)

    summarize_experiment_parser = subparsers.add_parser(
        "summarize-experiment",
        help="Summarize an experiment and its linked run evidence.",
    )
    add_experiment_registry_argument(summarize_experiment_parser)
    add_index_argument(summarize_experiment_parser)
    summarize_experiment_parser.add_argument("--experiment-id", required=True, help="Experiment id, such as EXP-001.")
    summarize_experiment_parser.add_argument(
        "--recent-limit",
        type=int,
        default=5,
        help="Maximum recent linked runs to show. Defaults to 5.",
    )
    summarize_experiment_parser.set_defaults(func=summarize_experiment_command)

    draft_decision_parser = subparsers.add_parser(
        "draft-decision",
        help="Draft a conservative experiment decision without writing to the registry.",
    )
    add_experiment_registry_argument(draft_decision_parser)
    add_index_argument(draft_decision_parser)
    draft_decision_parser.add_argument("--experiment-id", required=True, help="Experiment id, such as EXP-001.")
    draft_decision_parser.set_defaults(func=draft_decision_command)

    sweep_parser = subparsers.add_parser(
        "sweep",
        help="Run every combination of strategy parameter overrides.",
    )
    sweep_parser.add_argument("--strategy", required=True, help="Path to a v1 strategy JSON file.")
    sweep_parser.add_argument("--data", required=True, help="Path to a daily OHLCV CSV file.")
    sweep_parser.add_argument("--out", required=True, help="Directory where sweep artifacts are written.")
    sweep_parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="Parameter sweep in path=value1,value2 form, such as sma_20.inputs.length=5,10,20.",
    )
    sweep_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash. Defaults to 100000.",
    )
    sweep_parser.add_argument(
        "--quantity",
        type=float,
        default=1,
        help="Order quantity for fixed-shares sizing. Defaults to 1.",
    )
    sweep_parser.add_argument(
        "--sizing",
        choices=["fixed-shares", "percent-equity"],
        default="fixed-shares",
        help="Position sizing mode. Defaults to fixed-shares.",
    )
    sweep_parser.add_argument(
        "--allocation",
        type=float,
        default=1.0,
        help="Cash fraction to invest for percent-equity buys. Defaults to 1.0.",
    )
    sweep_parser.add_argument(
        "--run-name",
        default=None,
        help="Report title prefix. Defaults to the strategy name.",
    )
    sweep_parser.add_argument("--train-end", default=None, help="Final train date for train/test sweep mode.")
    sweep_parser.add_argument("--test-start", default=None, help="First test date for train/test sweep mode.")
    sweep_parser.add_argument(
        "--select-by",
        choices=["total_return", "sharpe_ratio"],
        default="total_return",
        help="Metric used to select the train winner for test rerun. Defaults to total_return.",
    )
    sweep_parser.add_argument(
        "--walk-forward-window",
        action="append",
        default=[],
        help=(
            "Explicit walk-forward window in train_start,train_end,test_start,test_end form. "
            "May be provided more than once."
        ),
    )
    add_cost_arguments(sweep_parser)
    add_benchmark_argument(sweep_parser)
    add_note_arguments(sweep_parser)
    add_experiment_registry_argument(sweep_parser)
    add_experiment_link_argument(sweep_parser)
    add_index_argument(sweep_parser)
    sweep_parser.set_defaults(func=sweep_command)
    return parser


def add_cost_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cost-preset",
        choices=sorted(COST_PRESETS),
        default="none",
        help="Named transaction cost preset. Explicit cost flags override preset values.",
    )
    parser.add_argument(
        "--commission-fixed",
        type=float,
        default=None,
        help="Flat commission charged per fill. Overrides --cost-preset.",
    )
    parser.add_argument(
        "--commission-rate",
        type=float,
        default=None,
        help="Commission as a decimal fraction of trade notional. Overrides --cost-preset.",
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        default=None,
        help="One-way slippage in basis points. Overrides --cost-preset.",
    )


def add_index_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--index-path",
        default="artifacts/research_index.jsonl",
        help="Append-only JSONL research index path. Defaults to artifacts/research_index.jsonl.",
    )


def add_experiment_registry_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--experiments-path",
        default="artifacts/experiments.jsonl",
        help="Append-only JSONL experiment registry path. Defaults to artifacts/experiments.jsonl.",
    )


def add_experiment_link_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--experiment-id",
        default=None,
        help="Optional experiment id to store in run metadata and the research index, such as EXP-001.",
    )


def add_benchmark_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--benchmark",
        choices=["buy-and-hold", "cash"],
        default="buy-and-hold",
        help="Benchmark used in reports, summaries, charts, and metadata. Defaults to buy-and-hold.",
    )


def add_note_arguments(parser: argparse.ArgumentParser) -> None:
    note_group = parser.add_mutually_exclusive_group()
    note_group.add_argument(
        "--note",
        default=None,
        help="Research note text saved as research_note.md beside run artifacts.",
    )
    note_group.add_argument(
        "--note-file",
        default=None,
        help="Path to a markdown/text file saved as research_note.md beside run artifacts.",
    )


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


def fetch_command(args: argparse.Namespace) -> int:
    data = fetch_market_data(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        interval=args.interval,
    )
    csv_path = write_market_data_csv(
        data=data,
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        output_dir=args.out,
    )
    print(f"Fetched {len(data)} rows for {args.symbol.upper()}")
    print(f"data: {csv_path}")
    return 0


def list_strategy_templates_command(args: argparse.Namespace) -> int:
    for template_name in available_strategy_templates():
        print(template_name)
    return 0


def new_strategy_command(args: argparse.Namespace) -> int:
    payload = build_strategy_template(
        args.template,
        symbol=args.symbol,
        strategy_id=args.strategy_id,
        name=args.name,
    )
    output_path = write_strategy_template(payload, args.out, force=args.force)
    print(f"Strategy template written: {output_path}")
    print(f"template: {args.template}")
    print(f"strategy_id: {payload['strategy_id']}")
    print(f"symbol: {payload['market']['symbol']}")
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


def show_run_command(args: argparse.Namespace) -> int:
    summary = load_run_summary(args.metadata)
    print(format_run_summary(summary))
    return 0


def compare_runs_command(args: argparse.Namespace) -> int:
    summaries = load_run_summaries(args.metadata)
    print(format_run_comparison(summaries))
    return 0


def new_experiment_command(args: argparse.Namespace) -> int:
    records = load_experiments(args.experiments_path)
    experiment_id = args.experiment_id or next_experiment_id(records)
    record = create_experiment_record(
        experiment_id=experiment_id,
        title=args.title,
        hypothesis=args.hypothesis,
        status=args.status,
        tags=normalize_tags(args.tag),
        strategy_path=args.strategy,
        data_path=args.data,
        notes=args.notes,
    )
    registry_path = append_experiment_record(record, args.experiments_path)

    print(f"Experiment created: {record.experiment_id}")
    print(f"registry: {registry_path}")
    print(f"status: {record.status}")
    print(f"title: {record.title}")
    return 0


def list_experiments_command(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")

    records = load_experiments(args.experiments_path)
    records = filter_experiments(records, status=args.status, tag=args.tag)
    records = records[: args.limit]

    if not records:
        print(f"No experiments found in {args.experiments_path}")
        return 0

    if args.csv:
        print(format_experiment_csv(records))
    else:
        print(format_experiment_table(records))
    return 0


def show_experiment_command(args: argparse.Namespace) -> int:
    records = load_experiments(args.experiments_path)
    record = find_experiment(records, args.experiment_id)
    print(format_experiment_detail(record))
    return 0


def update_experiment_command(args: argparse.Namespace) -> int:
    if args.status is None and args.decision is None and args.notes is None and not args.tag:
        raise ValueError("update-experiment requires at least one of --status, --decision, --notes, or --tag")

    records = load_experiments(args.experiments_path)
    record = find_experiment(records, args.experiment_id)
    updated = update_experiment_record(
        record,
        status=args.status,
        decision=args.decision,
        notes=args.notes,
        add_tags=args.tag,
    )
    registry_path = replace_experiment_record(updated, args.experiments_path)

    print(f"Experiment updated: {updated.experiment_id}")
    print(f"registry: {registry_path}")
    print(f"status: {updated.status}")
    if updated.decision is not None:
        print(f"decision: {updated.decision}")
    return 0


def decide_experiment_command(args: argparse.Namespace) -> int:
    records = load_experiments(args.experiments_path)
    record = find_experiment(records, args.experiment_id)
    decision_record = create_experiment_decision(
        outcome=args.outcome,
        rationale=args.rationale,
        supporting_run=args.supporting_run,
        contradicting_run=args.contradicting_run,
        next_action=args.next_action,
    )
    updated = decide_experiment_record(record, decision_record, add_tags=args.tag)
    registry_path = replace_experiment_record(updated, args.experiments_path)

    print(f"Experiment decided: {updated.experiment_id}")
    print(f"registry: {registry_path}")
    print(f"status: {updated.status}")
    print(f"outcome: {decision_record.outcome}")
    print(f"rationale: {decision_record.rationale}")
    if decision_record.next_action is not None:
        print(f"next_action: {decision_record.next_action}")
    return 0


def link_run_command(args: argparse.Namespace) -> int:
    metadata_paths = [str(Path(metadata_path)) for metadata_path in args.metadata]
    missing_paths = [metadata_path for metadata_path in metadata_paths if not Path(metadata_path).exists()]
    if missing_paths:
        raise FileNotFoundError(f"run metadata file not found: {missing_paths[0]}")

    records = load_experiments(args.experiments_path)
    record = find_experiment(records, args.experiment_id)
    updated = link_runs_to_experiment(record, metadata_paths)
    registry_path = replace_experiment_record(updated, args.experiments_path)

    print(f"Experiment linked: {updated.experiment_id}")
    print(f"registry: {registry_path}")
    print(f"linked_runs: {len(updated.linked_runs)}")
    return 0


def summarize_experiment_command(args: argparse.Namespace) -> int:
    if args.recent_limit < 1:
        raise ValueError("--recent-limit must be at least 1")

    records = load_experiments(args.experiments_path)
    experiment = find_experiment(records, args.experiment_id)
    index_records = load_research_index(args.index_path)
    print(
        format_experiment_evidence_summary(
            experiment,
            index_records,
            recent_limit=args.recent_limit,
        )
    )
    return 0


def draft_decision_command(args: argparse.Namespace) -> int:
    records = load_experiments(args.experiments_path)
    experiment = find_experiment(records, args.experiment_id)
    index_records = load_research_index(args.index_path)
    print(format_experiment_decision_draft(experiment, index_records))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(raw_argv)
    args.command_tokens = command_tokens("quant-lab", raw_argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
