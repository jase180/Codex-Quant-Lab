"""CLI command handlers for inspecting saved run artifacts."""

from __future__ import annotations

import argparse

from .run_inspection import (
    format_run_comparison,
    format_run_summary,
    format_run_verification,
    load_run_summaries,
    load_run_summary,
    verify_run_input_file,
)
from .run_trust import summarize_run_trust
from .portfolio_inspection import (
    format_portfolio_run_comparison,
    format_portfolio_run_summary,
    load_portfolio_run_summaries,
    load_portfolio_run_summary,
)


def show_run_command(args: argparse.Namespace) -> int:
    summary = load_run_summary(args.metadata)
    print(format_run_summary(summary))
    return 0


def show_portfolio_run_command(args: argparse.Namespace) -> int:
    summary = load_portfolio_run_summary(args.metadata)
    print(format_portfolio_run_summary(summary))
    return 0


def compare_portfolio_runs_command(args: argparse.Namespace) -> int:
    summaries = load_portfolio_run_summaries(args.metadata)
    print(format_portfolio_run_comparison(summaries))
    return 0


def verify_run_command(args: argparse.Namespace) -> int:
    verification = verify_run_input_file(args.metadata)
    print(format_run_verification(verification))
    return 0


def summarize_run_trust_command(args: argparse.Namespace) -> int:
    report = summarize_run_trust(args.metadata, output_path=args.out)
    print(f"Run trust report written: {report.report_path}")
    print(f"verification_result: {report.result}")
    print(f"worst_warning: {report.worst_warning}")
    return 0


def compare_runs_command(args: argparse.Namespace) -> int:
    summaries = load_run_summaries(args.metadata)
    print(format_run_comparison(summaries))
    return 0
