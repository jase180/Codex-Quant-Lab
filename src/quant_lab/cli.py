"""Command-line interface for Codex Quant Lab."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .cli_data import (
    audit_adjusted_prices_command,
    fetch_command,
    list_data_cache_command,
    list_strategy_templates_command,
    new_strategy_command,
    show_data_source_command,
)
from .cli_agent import (
    agent_context_command,
    agent_cycle_command,
    agent_suggest_command,
    agent_validate_recommendation_command,
)
from .cli_campaign import campaign_init_command, campaign_status_command
from .cli_health import doctor_command, smoke_test_command
from .cli_ideas import ideas_suggest_command
from .cli_runs import list_runs_command, run_command
from .costs import COST_PRESETS
from .default_experiment import run_default_experiment, validate_default_experiment_args
from .cli_experiments import (
    conclude_experiment_command,
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
    summarize_portfolio_data_trust_command,
    summarize_run_trust_command,
    verify_run_command,
)
from .cli_portfolio import (
    list_portfolio_templates_command,
    new_portfolio_command,
    portfolio_candidates_command,
    portfolio_variants_command,
    portfolio_run_command,
)
from .cli_portfolio_batch import (
    portfolio_batch_plan_command,
    portfolio_batch_run_command,
    portfolio_batch_summarize_command,
)
from .cli_portfolio_research_plan import portfolio_plan_init_command, portfolio_plan_next_command
from .cli_research_plan import research_plan_init_command, research_plan_next_command
from .cli_robustness import (
    benchmark_sensitivity_command,
    cost_sensitivity_command,
    date_sensitivity_command,
    parameter_neighborhood_command,
)
from .cli_session import session_refresh_command, session_replay_plan_command, session_status_command
from .cli_sweep_guardrails import summarize_sweep_guardrails_command
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
    register_health_commands(subparsers)
    register_run_inspection_commands(subparsers)
    register_experiment_commands(subparsers)
    register_default_experiment_commands(subparsers)
    register_research_plan_commands(subparsers)
    register_portfolio_plan_commands(subparsers)
    register_session_commands(subparsers)
    register_agent_commands(subparsers)
    register_campaign_commands(subparsers)
    register_ideas_commands(subparsers)
    register_robustness_commands(subparsers)
    register_sweep_commands(subparsers)
    register_sweep_guardrail_commands(subparsers)
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
            "cost_sensitivity_run",
            "date_sensitivity_run",
            "benchmark_sensitivity_run",
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

    summarize_parser = batch_subparsers.add_parser(
        "summarize",
        help="Write a guardrail summary for a portfolio batch manifest.",
    )
    summarize_parser.add_argument(
        "--manifest",
        required=True,
        help="Path to portfolio_batch_manifest.json.",
    )
    summarize_parser.add_argument(
        "--out",
        default=None,
        help="Path for the markdown summary. Defaults beside the manifest.",
    )
    summarize_parser.add_argument(
        "--max-planned-runs",
        type=int,
        default=25,
        help="Warn when planned runs exceed this count. Defaults to 25.",
    )
    summarize_parser.add_argument(
        "--min-completed-runs",
        type=int,
        default=2,
        help="Warn when completed runs are below this count. Defaults to 2.",
    )
    summarize_parser.set_defaults(func=portfolio_batch_summarize_command)


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

    show_data_source_parser = subparsers.add_parser(
        "show-data-source",
        help="Inspect one cached OHLCV CSV and its provenance sidecar.",
    )
    show_data_source_parser.add_argument("--data", required=True, help="Path to a daily OHLCV CSV file.")
    show_data_source_parser.set_defaults(func=show_data_source_command)

    list_data_cache_parser = subparsers.add_parser(
        "list-data-cache",
        help="List cached OHLCV CSV files and provenance status.",
    )
    list_data_cache_parser.add_argument(
        "--data-dir",
        default="data/cache",
        help="Directory containing cached OHLCV CSV files. Defaults to data/cache.",
    )
    list_data_cache_parser.set_defaults(func=list_data_cache_command)

    audit_adjusted_parser = subparsers.add_parser(
        "audit-adjusted-prices",
        help="Compare provider adjusted prices against raw provider Adj Close and action rows.",
    )
    audit_adjusted_parser.add_argument("--symbol", required=True, help="Ticker symbol, such as SPY or QQQ.")
    audit_adjusted_parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format.")
    audit_adjusted_parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format.")
    audit_adjusted_parser.add_argument(
        "--out",
        required=True,
        help="Directory where adjusted_price_audit artifacts are written.",
    )
    audit_adjusted_parser.add_argument(
        "--expected-dividend-date",
        action="append",
        default=[],
        help="Dividend date expected in provider action rows. May be repeated.",
    )
    audit_adjusted_parser.add_argument(
        "--expected-dividend",
        action="append",
        default=[],
        help="Expected dividend in YYYY-MM-DD=amount form. May be repeated.",
    )
    audit_adjusted_parser.add_argument(
        "--expected-split-date",
        action="append",
        default=[],
        help="Split date expected in provider action rows. May be repeated.",
    )
    audit_adjusted_parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Maximum allowed absolute close difference. Defaults to 0.01.",
    )
    audit_adjusted_parser.set_defaults(func=audit_adjusted_prices_command)

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
    new_strategy_parser.add_argument(
        "--length",
        type=int,
        default=None,
        help="Indicator length for templates that support one lookback, such as sma-long-cash.",
    )
    new_strategy_parser.add_argument("--force", action="store_true", help="Overwrite --out if it already exists.")
    new_strategy_parser.set_defaults(func=new_strategy_command)


def register_health_commands(subparsers) -> None:
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check whether the local environment is ready to run research workflows.",
    )
    doctor_parser.add_argument(
        "--repo-root",
        default=".",
        help="Project root to inspect. Defaults to the current directory.",
    )
    doctor_parser.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Artifacts directory to check for write access. Defaults to artifacts.",
    )
    doctor_parser.add_argument(
        "--data-cache-dir",
        default="data/cache",
        help="Data cache directory to inspect. Defaults to data/cache.",
    )
    doctor_parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    doctor_parser.set_defaults(func=doctor_command)

    smoke_parser = subparsers.add_parser(
        "smoke-test",
        help="Run an offline sample workflow and write artifacts for inspection.",
    )
    smoke_parser.add_argument(
        "--repo-root",
        default=".",
        help="Project root to use for tracked sample inputs. Defaults to the current directory.",
    )
    smoke_parser.add_argument(
        "--out",
        default="artifacts/smoke-test",
        help="Directory where smoke-test artifacts are written. Defaults to artifacts/smoke-test.",
    )
    smoke_parser.add_argument("--force", action="store_true", help="Replace the output directory if it already exists.")
    smoke_parser.add_argument(
        "--agent-cycle",
        action="store_true",
        help="Also verify the deterministic local-agent dry-run path.",
    )
    smoke_parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    smoke_parser.set_defaults(func=smoke_test_command)


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

    portfolio_trust_parser = subparsers.add_parser(
        "summarize-portfolio-data-trust",
        help="Write a Markdown data trust report for one saved portfolio run.",
    )
    portfolio_trust_parser.add_argument("--metadata", required=True, help="Path to a portfolio_metadata.json file.")
    portfolio_trust_parser.add_argument(
        "--out",
        default=None,
        help="Optional output path. Defaults to portfolio_data_trust_report.md beside the metadata file.",
    )
    portfolio_trust_parser.set_defaults(func=summarize_portfolio_data_trust_command)

    verify_parser = subparsers.add_parser(
        "verify-run",
        help="Check whether a saved run still matches its local input data file.",
    )
    verify_parser.add_argument("--metadata", required=True, help="Path to a run_metadata.json file.")
    verify_parser.set_defaults(func=verify_run_command)

    run_trust_parser = subparsers.add_parser(
        "summarize-run-trust",
        help="Write a Markdown data trust report for one saved run.",
    )
    run_trust_parser.add_argument("--metadata", required=True, help="Path to a run_metadata.json file.")
    run_trust_parser.add_argument(
        "--out",
        default=None,
        help="Optional output path. Defaults to run_trust_report.md beside the metadata file.",
    )
    run_trust_parser.set_defaults(func=summarize_run_trust_command)

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
        "--session-manifest",
        default=None,
        help="Optional session_manifest.json to update after recording the decision.",
    )
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
    summarize_experiment_parser.add_argument(
        "--out",
        default=None,
        help="Optional markdown path to write. Defaults to printing to stdout.",
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

    conclude_experiment_parser = subparsers.add_parser(
        "conclude-experiment",
        help="Write canonical conclusion artifacts for one experiment.",
    )
    add_experiment_registry_argument(conclude_experiment_parser)
    add_index_argument(conclude_experiment_parser)
    conclude_experiment_parser.add_argument("--experiment-id", required=True, help="Experiment id, such as EXP-001.")
    conclude_experiment_parser.add_argument(
        "--out",
        required=True,
        help="Directory where experiment_conclusion files are written.",
    )
    conclude_experiment_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing conclusion artifacts.",
    )
    conclude_experiment_parser.set_defaults(func=conclude_experiment_command)

    draft_decision_parser = subparsers.add_parser(
        "draft-decision",
        help="Draft a conservative experiment decision without writing to the registry.",
    )
    add_experiment_registry_argument(draft_decision_parser)
    add_index_argument(draft_decision_parser)
    draft_decision_parser.add_argument("--experiment-id", required=True, help="Experiment id, such as EXP-001.")
    draft_decision_parser.set_defaults(func=draft_decision_command)


def register_default_experiment_commands(subparsers) -> None:
    experiment_parser = subparsers.add_parser(
        "experiment",
        help="Run higher-level experiment workflows.",
    )
    experiment_subparsers = experiment_parser.add_subparsers(dest="experiment_command", required=True)

    run_default_parser = experiment_subparsers.add_parser(
        "run-default",
        help="Run the normal single-strategy workflow from baseline to conclusion.",
    )
    run_default_parser.add_argument("--title", required=True, help="Short experiment title.")
    run_default_parser.add_argument("--hypothesis", required=True, help="Research hypothesis being tested.")
    run_default_parser.add_argument("--strategy", required=True, help="Path to a v1 strategy JSON file.")
    run_default_parser.add_argument("--data", required=True, help="Path to a daily OHLCV CSV file.")
    run_default_parser.add_argument("--symbol", required=True, help="Market symbol, such as SPY or QQQ.")
    run_default_parser.add_argument("--out", required=True, help="Directory where workflow artifacts are written.")
    run_default_parser.add_argument(
        "--experiment-id",
        default=None,
        help="Optional explicit id such as EXP-001. Defaults to the next local id.",
    )
    run_default_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Experiment tag. May be repeated or comma-separated.",
    )
    run_default_parser.add_argument(
        "--param",
        action="append",
        required=True,
        help="Parameter sweep in path=value1,value2 form. May be repeated.",
    )
    run_default_parser.add_argument("--train-end", required=True, help="Final train date for train/test validation.")
    run_default_parser.add_argument("--test-start", required=True, help="First test date for train/test validation.")
    run_default_parser.add_argument(
        "--select-by",
        choices=["total_return", "sharpe_ratio"],
        default="sharpe_ratio",
        help="Metric used to select the train winner. Defaults to sharpe_ratio.",
    )
    run_default_parser.add_argument(
        "--date-window",
        action="append",
        required=True,
        help="Date sensitivity window in start,end form. May be repeated.",
    )
    run_default_parser.add_argument(
        "--cost-sensitivity-preset",
        action="append",
        default=[],
        choices=sorted(COST_PRESETS),
        help="Cost preset for cost sensitivity. Defaults to base preset plus stricter presets.",
    )
    run_default_parser.add_argument(
        "--decision",
        choices=["conservative", "continue", "none"],
        default="conservative",
        help="Whether to record a deterministic decision. Defaults to conservative.",
    )
    add_investment_objective_arguments(run_default_parser)
    run_default_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash. Defaults to 100000.",
    )
    run_default_parser.add_argument(
        "--quantity",
        type=float,
        default=1.0,
        help="Order quantity for fixed-shares sizing. Defaults to 1.",
    )
    run_default_parser.add_argument(
        "--sizing",
        choices=["fixed-shares", "percent-equity"],
        default="percent-equity",
        help="Position sizing mode. Defaults to percent-equity.",
    )
    run_default_parser.add_argument(
        "--allocation",
        type=float,
        default=1.0,
        help="Cash fraction to invest for percent-equity buys. Defaults to 1.0.",
    )
    run_default_parser.add_argument("--run-name", default=None, help="Optional baseline report title.")
    add_cost_arguments(run_default_parser)
    add_benchmark_argument(run_default_parser)
    add_experiment_registry_argument(run_default_parser)
    add_index_argument(run_default_parser)
    run_default_parser.set_defaults(func=run_default_experiment_command)


def run_default_experiment_command(args: argparse.Namespace) -> int:
    validate_default_experiment_args(args)
    result = run_default_experiment(args)
    print(f"Default experiment complete: {result.experiment_id}")
    print(f"read_first: {result.read_first_path}")
    print(f"conclusion: {result.conclusion_path}")
    print(f"evidence_summary: {result.evidence_summary_path}")
    print(f"decision: {result.decision_outcome or 'not recorded'}")
    return 0


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
    add_investment_objective_arguments(init_parser)
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


def register_session_commands(subparsers) -> None:
    session_parser = subparsers.add_parser(
        "session",
        help="Inspect and resume research session manifests.",
    )
    session_subparsers = session_parser.add_subparsers(dest="session_command", required=True)

    status_parser = session_subparsers.add_parser(
        "status",
        help="Print compact orientation from session_manifest.json.",
    )
    status_parser.add_argument("--manifest", required=True, help="Path to session_manifest.json.")
    status_parser.set_defaults(func=session_status_command)

    replay_parser = session_subparsers.add_parser(
        "replay-plan",
        help="Print saved planned/suggested commands without executing them.",
    )
    replay_parser.add_argument("--manifest", required=True, help="Path to session_manifest.json.")
    replay_parser.add_argument(
        "--include-executed",
        action="store_true",
        help="Also print commands marked executed. Defaults to pending commands only.",
    )
    replay_parser.set_defaults(func=session_replay_plan_command)

    refresh_parser = session_subparsers.add_parser(
        "refresh",
        help="Create or update session manifests from research_plan.json and known artifacts.",
    )
    refresh_parser.add_argument("--plan", required=True, help="Path to research_plan.json.")
    refresh_parser.set_defaults(func=session_refresh_command)


def register_agent_commands(subparsers) -> None:
    agent_parser = subparsers.add_parser(
        "agent",
        help="Prepare bounded local-agent advisor inputs.",
    )
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command", required=True)

    context_parser = agent_subparsers.add_parser(
        "context",
        help="Build an agent-readable context bundle from a session manifest.",
    )
    context_parser.add_argument("--manifest", required=True, help="Path to session_manifest.json.")
    context_parser.add_argument(
        "--out-dir",
        default=None,
        help="Directory where context artifacts are written. Defaults to the manifest output directory.",
    )
    context_parser.add_argument(
        "--max-chars-per-file",
        type=int,
        default=12_000,
        help="Maximum text characters to embed from each file. Defaults to 12000.",
    )
    context_parser.add_argument("--json", action="store_true", help="Print the context bundle JSON after writing files.")
    context_parser.set_defaults(func=agent_context_command)

    suggest_parser = agent_subparsers.add_parser(
        "suggest",
        help="Write a deterministic next-step recommendation from a session manifest.",
    )
    add_agent_manifest_argument(suggest_parser)
    add_agent_provider_arguments(suggest_parser)
    suggest_parser.add_argument(
        "--out-dir",
        default=None,
        help="Directory where recommendation artifacts are written. Defaults to the manifest output directory.",
    )
    suggest_parser.add_argument("--json", action="store_true", help="Print recommendation JSON after writing files.")
    suggest_parser.add_argument("--markdown", action="store_true", help="Print recommendation Markdown after writing files.")
    suggest_parser.set_defaults(func=agent_suggest_command)

    cycle_parser = agent_subparsers.add_parser(
        "cycle",
        help="Create one human-gated local-agent cycle without executing commands.",
    )
    add_agent_manifest_argument(cycle_parser)
    cycle_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Required for now. Writes cycle artifacts and stops before execution.",
    )
    add_agent_provider_arguments(cycle_parser)
    cycle_parser.add_argument(
        "--out-dir",
        default=None,
        help="Directory where cycle artifacts are written. Defaults to <manifest output>/agent_cycle.",
    )
    cycle_parser.add_argument("--json", action="store_true", help="Print cycle JSON after writing files.")
    cycle_parser.add_argument("--markdown", action="store_true", help="Print cycle Markdown after writing files.")
    cycle_parser.set_defaults(func=agent_cycle_command)

    validate_parser = agent_subparsers.add_parser(
        "validate-recommendation",
        help="Validate an agent_recommendation.v1 JSON file.",
    )
    validate_parser.add_argument("--recommendation", required=True, help="Path to agent_recommendation.json.")
    validate_parser.add_argument(
        "--out-dir",
        default=None,
        help="Optional directory where normalized recommendation JSON and Markdown are written.",
    )
    validate_parser.add_argument("--json", action="store_true", help="Print normalized recommendation JSON.")
    validate_parser.add_argument("--markdown", action="store_true", help="Print normalized Markdown after validation.")
    validate_parser.set_defaults(func=agent_validate_recommendation_command)


def register_campaign_commands(subparsers) -> None:
    campaign_parser = subparsers.add_parser(
        "campaign",
        help="Run bounded multi-cycle research campaigns.",
    )
    campaign_subparsers = campaign_parser.add_subparsers(dest="campaign_command", required=True)

    init_parser = campaign_subparsers.add_parser(
        "init",
        help="Create campaign_config.json, campaign_state.json, and campaign_state.md.",
    )
    init_parser.add_argument("--config", required=True, help="Path to input campaign config JSON.")
    init_parser.add_argument("--out", required=True, help="Campaign output directory.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing campaign state files.")
    init_parser.set_defaults(func=campaign_init_command)

    status_parser = campaign_subparsers.add_parser(
        "status",
        help="Print compact status for an initialized campaign.",
    )
    status_parser.add_argument("--campaign", required=True, help="Campaign output directory.")
    status_parser.set_defaults(func=campaign_status_command)


def add_agent_manifest_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True, help="Path to session_manifest.json.")


def add_agent_provider_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        choices=["deterministic", "openai-compatible"],
        default="deterministic",
        help="Recommendation provider. Defaults to deterministic.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434/v1",
        help="OpenAI-compatible base URL. Defaults to Ollama's local v1 endpoint.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name for --provider openai-compatible, such as llama3.1:8b.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="Provider request timeout in seconds. Defaults to 60.",
    )


def register_ideas_commands(subparsers) -> None:
    ideas_parser = subparsers.add_parser(
        "ideas",
        help="Suggest the next conceptual strategy idea from the catalog and prior conclusions.",
    )
    ideas_subparsers = ideas_parser.add_subparsers(dest="ideas_command", required=True)

    suggest_parser = ideas_subparsers.add_parser(
        "suggest",
        help="Propose one hypothesis and draft experiment config without creating strategy JSON.",
    )
    suggest_parser.add_argument(
        "--catalog-dir",
        default="data/strategy_catalog",
        help="Directory containing conceptual strategy catalog JSON files. Defaults to data/strategy_catalog.",
    )
    suggest_parser.add_argument(
        "--conclusions-dir",
        default="artifacts/research",
        help="Directory searched recursively for experiment_conclusion.json files. Defaults to artifacts/research.",
    )
    suggest_parser.add_argument(
        "--experiments-path",
        default="artifacts/experiments.jsonl",
        help="Experiment registry JSONL path used for decision memory. Defaults to artifacts/experiments.jsonl.",
    )
    suggest_parser.add_argument(
        "--handoffs-dir",
        default="docs/experiments",
        help="Directory of tracked experiment handoff Markdown files. Defaults to docs/experiments.",
    )
    suggest_parser.set_defaults(func=ideas_suggest_command)


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


def register_sweep_guardrail_commands(subparsers) -> None:
    guardrail_parser = subparsers.add_parser(
        "summarize-sweep-guardrails",
        help="Write a guardrail report for an existing sweep summary.csv.",
    )
    guardrail_parser.add_argument("--summary", required=True, help="Path to a sweep summary.csv file.")
    guardrail_parser.add_argument(
        "--out",
        default=None,
        help="Markdown report path. Defaults to sweep_guardrails.md beside the summary.",
    )
    guardrail_parser.add_argument(
        "--max-rows",
        type=int,
        default=25,
        help="Warn when the sweep has more rows than this. Defaults to 25.",
    )
    guardrail_parser.add_argument(
        "--min-trades",
        type=int,
        default=5,
        help="Warn when runs have fewer trades than this. Defaults to 5.",
    )
    guardrail_parser.set_defaults(func=summarize_sweep_guardrails_command)


def register_robustness_commands(subparsers) -> None:
    robustness_parser = subparsers.add_parser(
        "robustness",
        help="Run controlled robustness checks for promising research ideas.",
    )
    robustness_subparsers = robustness_parser.add_subparsers(dest="robustness_command", required=True)

    cost_parser = robustness_subparsers.add_parser(
        "cost-sensitivity",
        help="Rerun one strategy setup across cost presets.",
    )
    cost_parser.add_argument("--strategy", required=True, help="Path to a v1 strategy JSON file.")
    cost_parser.add_argument("--data", required=True, help="Path to a daily OHLCV CSV file.")
    cost_parser.add_argument("--out", required=True, help="Directory where robustness artifacts are written.")
    cost_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash. Defaults to 100000.",
    )
    cost_parser.add_argument(
        "--quantity",
        type=float,
        default=1,
        help="Order quantity for fixed-shares sizing. Defaults to 1.",
    )
    cost_parser.add_argument(
        "--sizing",
        choices=["fixed-shares", "percent-equity"],
        default="fixed-shares",
        help="Position sizing mode. Defaults to fixed-shares.",
    )
    cost_parser.add_argument(
        "--allocation",
        type=float,
        default=1.0,
        help="Cash fraction to invest for percent-equity buys. Defaults to 1.0.",
    )
    cost_parser.add_argument(
        "--cost-preset",
        action="append",
        choices=sorted(COST_PRESETS),
        required=True,
        help="Cost preset to test. Repeat for multiple presets.",
    )
    add_benchmark_argument(cost_parser)
    add_experiment_registry_argument(cost_parser)
    add_experiment_link_argument(cost_parser)
    add_index_argument(cost_parser)
    cost_parser.set_defaults(func=cost_sensitivity_command)

    date_parser = robustness_subparsers.add_parser(
        "date-sensitivity",
        help="Rerun one strategy setup over explicit date windows.",
    )
    date_parser.add_argument("--strategy", required=True, help="Path to a v1 strategy JSON file.")
    date_parser.add_argument("--data", required=True, help="Path to a daily OHLCV CSV file.")
    date_parser.add_argument("--out", required=True, help="Directory where robustness artifacts are written.")
    date_parser.add_argument(
        "--window",
        action="append",
        required=True,
        help="Date window in start,end form. Repeat for multiple windows.",
    )
    date_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash. Defaults to 100000.",
    )
    date_parser.add_argument(
        "--quantity",
        type=float,
        default=1,
        help="Order quantity for fixed-shares sizing. Defaults to 1.",
    )
    date_parser.add_argument(
        "--sizing",
        choices=["fixed-shares", "percent-equity"],
        default="fixed-shares",
        help="Position sizing mode. Defaults to fixed-shares.",
    )
    date_parser.add_argument(
        "--allocation",
        type=float,
        default=1.0,
        help="Cash fraction to invest for percent-equity buys. Defaults to 1.0.",
    )
    add_cost_arguments(date_parser)
    add_benchmark_argument(date_parser)
    add_experiment_registry_argument(date_parser)
    add_experiment_link_argument(date_parser)
    add_index_argument(date_parser)
    date_parser.set_defaults(func=date_sensitivity_command)

    benchmark_parser = robustness_subparsers.add_parser(
        "benchmark-sensitivity",
        help="Rerun one strategy setup against multiple benchmarks.",
    )
    benchmark_parser.add_argument("--strategy", required=True, help="Path to a v1 strategy JSON file.")
    benchmark_parser.add_argument("--data", required=True, help="Path to a daily OHLCV CSV file.")
    benchmark_parser.add_argument("--out", required=True, help="Directory where robustness artifacts are written.")
    benchmark_parser.add_argument(
        "--benchmark",
        action="append",
        choices=["buy-and-hold", "cash"],
        required=True,
        help="Benchmark to test. Repeat for multiple benchmarks.",
    )
    benchmark_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash. Defaults to 100000.",
    )
    benchmark_parser.add_argument(
        "--quantity",
        type=float,
        default=1,
        help="Order quantity for fixed-shares sizing. Defaults to 1.",
    )
    benchmark_parser.add_argument(
        "--sizing",
        choices=["fixed-shares", "percent-equity"],
        default="fixed-shares",
        help="Position sizing mode. Defaults to fixed-shares.",
    )
    benchmark_parser.add_argument(
        "--allocation",
        type=float,
        default=1.0,
        help="Cash fraction to invest for percent-equity buys. Defaults to 1.0.",
    )
    add_cost_arguments(benchmark_parser)
    add_experiment_registry_argument(benchmark_parser)
    add_experiment_link_argument(benchmark_parser)
    add_index_argument(benchmark_parser)
    benchmark_parser.set_defaults(func=benchmark_sensitivity_command)

    neighborhood_parser = robustness_subparsers.add_parser(
        "parameter-neighborhood",
        help="Summarize whether nearby sweep parameters also beat the benchmark.",
    )
    neighborhood_parser.add_argument("--summary", required=True, help="Path to a sweep summary.csv file.")
    neighborhood_parser.add_argument(
        "--out",
        default=None,
        help="Directory for parameter neighborhood artifacts. Defaults beside the summary.",
    )
    neighborhood_parser.set_defaults(func=parameter_neighborhood_command)


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


def add_investment_objective_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--intended-benefit",
        default=None,
        help="Prespecified investment benefit, such as lower drawdown or return retention.",
    )
    parser.add_argument(
        "--primary-metric",
        default=None,
        help="Primary metric used for strategy-hypothesis status, such as max_drawdown or cagr.",
    )
    parser.add_argument(
        "--minimum-acceptable-performance",
        default=None,
        help="Plain-English prespecified minimum acceptable strategy performance.",
    )
    parser.add_argument(
        "--tradeoff",
        action="append",
        default=[],
        help="Important accepted trade-off. May be repeated.",
    )
    parser.add_argument(
        "--success-criterion",
        action="append",
        default=[],
        help="Success criterion JSON object with name, metric, comparison, operator, and threshold.",
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
