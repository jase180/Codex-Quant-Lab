"""CLI command handlers for robustness checks."""

from __future__ import annotations

import argparse

from .robustness import run_benchmark_sensitivity, run_cost_sensitivity, run_date_sensitivity


def cost_sensitivity_command(args: argparse.Namespace) -> int:
    result = run_cost_sensitivity(args)
    print(f"Cost sensitivity complete: {len(result.rows)} runs")
    print(f"summary: {result.summary_path}")
    print(f"report: {result.report_path}")
    if result.rows:
        weakest = min(result.rows, key=lambda row: float(row["excess_total_return"]))
        print(f"weakest_cost_preset: {weakest['cost_preset']}")
        print(f"weakest_excess_total_return: {float(weakest['excess_total_return']):.2%}")
    return 0


def date_sensitivity_command(args: argparse.Namespace) -> int:
    result = run_date_sensitivity(args)
    print(f"Date sensitivity complete: {len(result.rows)} runs")
    print(f"summary: {result.summary_path}")
    print(f"report: {result.report_path}")
    if result.rows:
        weakest = min(result.rows, key=lambda row: float(row["excess_total_return"]))
        print(f"weakest_window: {weakest['window_start']} to {weakest['window_end']}")
        print(f"weakest_excess_total_return: {float(weakest['excess_total_return']):.2%}")
    return 0


def benchmark_sensitivity_command(args: argparse.Namespace) -> int:
    result = run_benchmark_sensitivity(args)
    print(f"Benchmark sensitivity complete: {len(result.rows)} runs")
    print(f"summary: {result.summary_path}")
    print(f"report: {result.report_path}")
    if result.rows:
        weakest = min(result.rows, key=lambda row: float(row["excess_total_return"]))
        print(f"weakest_benchmark: {weakest['benchmark_name']}")
        print(f"weakest_excess_total_return: {float(weakest['excess_total_return']):.2%}")
    return 0
