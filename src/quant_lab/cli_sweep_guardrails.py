"""CLI handlers for strategy sweep guardrail reports."""

from __future__ import annotations

import argparse

from .sweep_guardrails import summarize_sweep_guardrails


def summarize_sweep_guardrails_command(args: argparse.Namespace) -> int:
    report = summarize_sweep_guardrails(
        summary_path=args.summary,
        output_path=args.out,
        max_rows=args.max_rows,
        min_trades=args.min_trades,
    )
    print(f"Sweep guardrail report written: {report.report_path}")
    print(f"rows: {report.row_count}")
    print(f"warnings: {len(report.warnings)}")
    for warning in report.warnings:
        print(f"- {warning}")
    return 0
