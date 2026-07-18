"""Command-line interface for Codex Quant Lab."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .cli_data import fetch_command, list_strategy_templates_command, new_strategy_command
from .cli_runs import list_runs_command, run_command
from .costs import COST_PRESETS
from .cli_experiments import (
    decide_experiment_command,
    draft_decision_command,
    link_run_command,
    list_experiments_command,
    new_experiment_command,
    show_experiment_command,
    summarize_portfolio_experiment_command,
    summarize_experiment_command,
    update_experiment_command,
)
from .cli_run_inspection import (
    compare_portfolio_runs_command,
    compare_runs_command,
    show_portfolio_run_command,
    show_run_command,
    verify_run_command,
)
from .cli_portfolio import (
    list_portfolio_templates_command,
    new_portfolio_command,
    portfolio_candidates_command,
    portfolio_variants_command,
    portfolio_run_command,
)
from .cli_portfolio_batch import portfolio_batch_plan_command, portfolio_batch_run_command
from .cli_portfolio_research_plan import portfolio_plan_init_command, portfolio_plan_next_command
from .cli_research_plan import research_plan_init_command, research_plan_next_command
from .research_registry import (
    EXPERIMENT_DECISION_OUTCOMES,
    EXPERIMENT_STATUSES,
)
from .run_metadata import command_tokens
from .strategy_templates import available_strategy_templates
from .portfolio_templates import available_portfolio_templates
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

    register_run_commands(subparsers)
    register_portfolio_commands(subparsers)
    register_portfolio_batch_commands(subparsers)
    register_data_commands(subparsers)
    register_run_inspection_commands(subparsers)
    register_experiment_commands(subparsers)
    register_research_plan_commands(subparsers)
    register_portfolio_plan_commands(subparsers)
    register_sweep_commands(subparsers)
    return parser


def register_run_commands(subparsers) -> None:
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
            "portfolio_run",
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


def register_portfolio_commands(subparsers) -> None:
    template_list_parser = subparsers.add_parser(
        "list-portfolio-templates",
        help="List built-in portfolio templates.",
    )
    template_list_parser.set_defaults(func=list_portfolio_templates_command)

    new_portfolio_parser = subparsers.add_parser(
        "new-portfolio",
        help="Create a valid portfolio_plan.v1 JSON file from a built-in template.",
    )
    new_portfolio_parser.add_argument(
        "--template",
        required=True,
        choices=available_portfolio_templates(),
        help="Template name.",
    )
    new_portfolio_parser.add_argument("--out", required=True, help="Path where the portfolio JSON is written.")
    new_portfolio_parser.add_argument("--force", action="store_true", help="Overwrite --out if it already exists.")
    new_portfolio_parser.set_defaults(func=new_portfolio_command)

    variants_parser = subparsers.add_parser(
        "portfolio-variants",
        help="Generate valid portfolio_plan.v1 weight variants from a base portfolio spec.",
    )
    variants_parser.add_argument(
        "--portfolio",
        required=True,
        help="Path to the base portfolio_plan.v1 JSON file.",
    )
    variants_parser.add_argument(
        "--weights",
        action="append",
        required=True,
        help="Variant weights in SYMBOL=weight,SYMBOL=weight form. May be repeated.",
    )
    variants_parser.add_argument(
        "--rebalance",
        action="append",
        choices=["none", "monthly", "quarterly", "annually"],
        default=None,
        help="Rebalance frequency to generate. May be repeated. Defaults to the base spec frequency.",
    )
    variants_parser.add_argument(
        "--out",
        required=True,
        help="Directory where generated portfolio JSON files are written.",
    )
    variants_parser.add_argument("--force", action="store_true", help="Overwrite generated files if they exist.")
    variants_parser.set_defaults(func=portfolio_variants_command)

    candidates_parser = subparsers.add_parser(
        "portfolio-candidates",
        help="Generate capped static-weight portfolio candidate specs on a coarse grid.",
    )
    candidates_parser.add_argument(
        "--symbols",
        required=True,
        help="Comma-separated symbols, such as QQQ,SPY,TLT.",
    )
    candidates_parser.add_argument(
        "--step",
        type=float,
        required=True,
        help="Weight grid step that divides 1.0 evenly, such as 0.5, 0.25, or 0.1.",
    )
    candidates_parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory containing one CSV per symbol.",
    )
    candidates_parser.add_argument(
        "--out",
        required=True,
        help="Directory where generated portfolio JSON files are written.",
    )
    candidates_parser.add_argument(
        "--max-candidates",
        type=int,
        default=100,
        help="Maximum candidate specs to write. Defaults to 100.",
    )
    candidates_parser.add_argument(
        "--rebalance",
        choices=["none", "monthly", "quarterly", "annually"],
        default="monthly",
        help="Rebalance frequency for generated candidates. Defaults to monthly.",
    )
    candidates_parser.add_argument(
        "--benchmark-symbol",
        default=None,
        help="Benchmark symbol. Defaults to the first symbol.",
    )
    candidates_parser.add_argument("--force", action="store_true", help="Overwrite generated files if they exist.")
    candidates_parser.set_defaults(func=portfolio_candidates_command)

    portfolio_parser = subparsers.add_parser(
        "portfolio-run",
        help="Run one static-weight portfolio spec against aligned OHLCV CSV inputs.",
    )
    portfolio_parser.add_argument(
        "--portfolio",
        required=True,
        help="Path to a portfolio_plan.v1 JSON file.",
    )
    portfolio_parser.add_argument(
        "--out",
        required=True,
        help="Directory where portfolio artifacts are written.",
    )
    portfolio_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash. Defaults to 100000.",
    )
    add_cost_arguments(portfolio_parser)
    add_experiment_registry_argument(portfolio_parser)
    add_experiment_link_argument(portfolio_parser)
    add_index_argument(portfolio_parser)
    portfolio_parser.set_defaults(func=portfolio_run_command)


def register_portfolio_batch_commands(subparsers) -> None:
    batch_parser = subparsers.add_parser(
        "portfolio-batch",
        help="Plan and run auditable batches of portfolio specs.",
    )
    batch_subparsers = batch_parser.add_subparsers(dest="portfolio_batch_command", required=True)

    plan_parser = batch_subparsers.add_parser(
        "plan",
        help="Write a dry-run manifest for a directory of portfolio specs.",
    )
    plan_parser.add_argument(
        "--portfolios",
        required=True,
        help="Directory containing portfolio_plan.v1 JSON specs.",
    )
    plan_parser.add_argument(
        "--out",
        required=True,
        help="Directory where portfolio_batch_manifest.json is written.",
    )
    plan_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash for planned runs. Defaults to 100000.",
    )
    plan_parser.add_argument(
        "--cost-preset",
        choices=sorted(COST_PRESETS),
        default="none",
        help="Cost preset for planned runs. Defaults to none.",
    )
    add_experiment_registry_argument(plan_parser)
    add_index_argument(plan_parser)
    plan_parser.add_argument("--force", action="store_true", help="Overwrite an existing manifest.")
    plan_parser.set_defaults(func=portfolio_batch_plan_command)

    run_parser = batch_subparsers.add_parser(
        "run",
        help="Execute a saved portfolio batch manifest sequentially.",
    )
    run_parser.add_argument(
        "--manifest",
        required=True,
        help="Path to portfolio_batch_manifest.json.",
    )
    run_parser.add_argument(
        "--experiment-id",
        required=True,
        help="Experiment id to attach every completed portfolio run to.",
    )
    run_parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue after a failed item instead of stopping the batch.",
    )
    run_parser.set_defaults(func=portfolio_batch_run_command)


def register_data_commands(subparsers) -> None:
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


def register_run_inspection_commands(subparsers) -> None:
    show_parser = subparsers.add_parser(
        "show-run",
        help="Inspect one saved run from run_metadata.json.",
    )
    show_parser.add_argument("--metadata", required=True, help="Path to a run_metadata.json file.")
    show_parser.set_defaults(func=show_run_command)

    show_portfolio_parser = subparsers.add_parser(
        "show-portfolio-run",
        help="Inspect one saved portfolio run from portfolio_metadata.json.",
    )
    show_portfolio_parser.add_argument(
        "--metadata",
        required=True,
        help="Path to a portfolio_metadata.json file.",
    )
    show_portfolio_parser.set_defaults(func=show_portfolio_run_command)

    verify_parser = subparsers.add_parser(
        "verify-run",
        help="Check whether a saved run still matches its local input data file.",
    )
    verify_parser.add_argument("--metadata", required=True, help="Path to a run_metadata.json file.")
    verify_parser.set_defaults(func=verify_run_command)

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

    compare_portfolio_parser = subparsers.add_parser(
        "compare-portfolio-runs",
        help="Compare two or more saved portfolio runs from portfolio_metadata.json files.",
    )
    compare_portfolio_parser.add_argument(
        "--metadata",
        action="append",
        required=True,
        help="Path to a portfolio_metadata.json file. Provide at least two.",
    )
    compare_portfolio_parser.set_defaults(func=compare_portfolio_runs_command)


def register_experiment_commands(subparsers) -> None:
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

    summarize_portfolio_experiment_parser = subparsers.add_parser(
        "summarize-portfolio-experiment",
        help="Write or print a portfolio-specific evidence summary for one experiment.",
    )
    add_experiment_registry_argument(summarize_portfolio_experiment_parser)
    add_index_argument(summarize_portfolio_experiment_parser)
    summarize_portfolio_experiment_parser.add_argument(
        "--experiment-id",
        required=True,
        help="Experiment id, such as EXP-001.",
    )
    summarize_portfolio_experiment_parser.add_argument(
        "--out",
        default=None,
        help="Optional markdown path to write. Defaults to printing to stdout.",
    )
    summarize_portfolio_experiment_parser.add_argument(
        "--top-limit",
        type=int,
        default=5,
        help="Maximum rows per ranked section. Defaults to 5.",
    )
    summarize_portfolio_experiment_parser.set_defaults(func=summarize_portfolio_experiment_command)

    draft_decision_parser = subparsers.add_parser(
        "draft-decision",
        help="Draft a conservative experiment decision without writing to the registry.",
    )
    add_experiment_registry_argument(draft_decision_parser)
    add_index_argument(draft_decision_parser)
    draft_decision_parser.add_argument("--experiment-id", required=True, help="Experiment id, such as EXP-001.")
    draft_decision_parser.set_defaults(func=draft_decision_command)


def register_research_plan_commands(subparsers) -> None:
    research_plan_parser = subparsers.add_parser(
        "research-plan",
        help="Create and inspect guided research workflow plans.",
    )
    research_plan_subparsers = research_plan_parser.add_subparsers(dest="research_plan_command", required=True)

    init_parser = research_plan_subparsers.add_parser(
        "init",
        help="Create a local research plan and print the baseline run command.",
    )
    init_parser.add_argument("--title", required=True, help="Short research plan title.")
    init_parser.add_argument("--hypothesis", required=True, help="Research hypothesis to test.")
    init_parser.add_argument("--strategy", required=True, help="Path to a v1 strategy JSON file.")
    init_parser.add_argument("--data", required=True, help="Path to a daily OHLCV CSV file.")
    init_parser.add_argument("--symbol", required=True, help="Market symbol, such as QQQ or SPY.")
    init_parser.add_argument("--out", required=True, help="Directory where research_plan files are written.")
    init_parser.add_argument(
        "--experiment-id",
        default=None,
        help="Optional explicit id such as EXP-001. Defaults to the next local id.",
    )
    init_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Research tag. May be repeated or comma-separated.",
    )
    init_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash for the recommended baseline. Defaults to 100000.",
    )
    init_parser.add_argument(
        "--quantity",
        type=float,
        default=1,
        help="Order quantity for fixed-shares sizing. Defaults to 1.",
    )
    init_parser.add_argument(
        "--sizing",
        choices=["fixed-shares", "percent-equity"],
        default="percent-equity",
        help="Position sizing mode for the recommended baseline. Defaults to percent-equity.",
    )
    init_parser.add_argument(
        "--allocation",
        type=float,
        default=1.0,
        help="Cash fraction to invest for percent-equity buys. Defaults to 1.0.",
    )
    add_cost_arguments(init_parser)
    add_benchmark_argument(init_parser)
    add_experiment_registry_argument(init_parser)
    add_index_argument(init_parser)
    init_parser.set_defaults(func=research_plan_init_command)

    next_parser = research_plan_subparsers.add_parser(
        "next",
        help="Recommend the next command for an existing research plan.",
    )
    next_parser.add_argument("--plan", required=True, help="Path to research_plan.json.")
    next_parser.set_defaults(func=research_plan_next_command)


def register_portfolio_plan_commands(subparsers) -> None:
    portfolio_plan_parser = subparsers.add_parser(
        "portfolio-plan",
        help="Create and inspect guided portfolio research workflow plans.",
    )
    portfolio_plan_subparsers = portfolio_plan_parser.add_subparsers(
        dest="portfolio_plan_command",
        required=True,
    )

    init_parser = portfolio_plan_subparsers.add_parser(
        "init",
        help="Create a local portfolio research plan and print the baseline portfolio-run command.",
    )
    init_parser.add_argument("--title", required=True, help="Short research plan title.")
    init_parser.add_argument("--hypothesis", required=True, help="Portfolio hypothesis to test.")
    init_parser.add_argument("--portfolio", required=True, help="Path to a portfolio_plan.v1 JSON file.")
    init_parser.add_argument(
        "--out",
        required=True,
        help="Directory where portfolio_research_plan files are written.",
    )
    init_parser.add_argument(
        "--experiment-id",
        default=None,
        help="Optional explicit id such as EXP-001. Defaults to the next local id.",
    )
    init_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Research tag. May be repeated or comma-separated.",
    )
    init_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash for the recommended baseline. Defaults to 100000.",
    )
    add_cost_arguments(init_parser)
    add_experiment_registry_argument(init_parser)
    add_index_argument(init_parser)
    init_parser.set_defaults(func=portfolio_plan_init_command)

    next_parser = portfolio_plan_subparsers.add_parser(
        "next",
        help="Recommend the next command for an existing portfolio research plan.",
    )
    next_parser.add_argument("--plan", required=True, help="Path to portfolio_research_plan.json.")
    next_parser.set_defaults(func=portfolio_plan_next_command)


def register_sweep_commands(subparsers) -> None:
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(raw_argv)
    args.command_tokens = command_tokens("quant-lab", raw_argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
