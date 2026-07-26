"""CLI command handlers for local environment health checks."""

from __future__ import annotations

import argparse

from .health import format_health_report, health_report_to_json, run_doctor
from .smoke_test import format_smoke_test_result, run_smoke_test, smoke_test_result_to_json


def doctor_command(args: argparse.Namespace) -> int:
    report = run_doctor(
        repo_root=args.repo_root,
        artifacts_dir=args.artifacts_dir,
        data_cache_dir=args.data_cache_dir,
    )
    if args.json:
        print(health_report_to_json(report))
    else:
        print(format_health_report(report))
    return 1 if report.status == "fail" else 0


def smoke_test_command(args: argparse.Namespace) -> int:
    result = run_smoke_test(
        repo_root=args.repo_root,
        output_dir=args.out,
        force=args.force,
    )
    if args.json:
        print(smoke_test_result_to_json(result))
    else:
        print(format_smoke_test_result(result))
    return 0
