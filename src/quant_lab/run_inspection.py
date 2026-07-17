"""Helpers for inspecting saved run artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .research_index import load_research_index
from .run_metadata import fingerprint_file


def load_run_summary(metadata_path: str | Path) -> dict:
    metadata_file = Path(metadata_path)
    if not metadata_file.exists():
        raise FileNotFoundError(f"metadata file not found: {metadata_file}")

    metadata = _read_json(metadata_file)
    metrics_path = metadata.get("artifacts", {}).get("metrics")
    if not metrics_path:
        raise ValueError(f"metadata file does not include a metrics artifact: {metadata_file}")

    metrics_file = Path(metrics_path)
    if not metrics_file.exists():
        raise FileNotFoundError(f"metrics file not found: {metrics_file}")

    warnings_path = metadata.get("artifacts", {}).get("research_warnings")
    warnings = _read_json(Path(warnings_path)) if warnings_path and Path(warnings_path).exists() else None
    index_record = _find_index_record(metadata)
    return {
        "metadata_path": str(metadata_file),
        "metadata": metadata,
        "metrics": _read_json(metrics_file),
        "research_warnings": warnings,
        "index_record": index_record,
    }


def format_run_summary(summary: dict) -> str:
    metadata = summary["metadata"]
    metrics = summary["metrics"]
    research_warnings = summary.get("research_warnings") or {}
    index_record = summary["index_record"] or {}
    artifacts = metadata.get("artifacts", {})

    lines = [
        "Run Summary",
        "===========",
        "",
        "Identity",
        f"  Run type: {metadata.get('run_type', '-')}",
        f"  Run id: {_format_plain(metadata.get('run_id'))}",
        f"  Created UTC: {_format_plain(metadata.get('created_at_utc'))}",
        f"  Git commit: {_format_plain(metadata.get('environment', {}).get('git_commit'))}",
        "",
        "Strategy And Data",
        f"  Strategy: {_format_plain(metadata.get('strategy', {}).get('strategy_id'))}",
        f"  Name: {_format_plain(metadata.get('strategy', {}).get('name'))}",
        f"  Symbol: {_format_plain(metadata.get('data', {}).get('symbol'))}",
        f"  Timeframe: {_format_plain(metadata.get('data', {}).get('timeframe'))}",
        (
            f"  Data range: {_format_plain(metadata.get('data', {}).get('start'))} "
            f"to {_format_plain(metadata.get('data', {}).get('end'))}"
        ),
        f"  Rows: {_format_plain(metadata.get('data', {}).get('row_count'))}",
        "",
        "Results",
        f"  Final equity: {_format_money(metrics.get('ending_equity'))}",
        f"  Total return: {_format_percent(metrics.get('total_return'))}",
        f"  Benchmark: {_format_plain(_benchmark_name(metadata, index_record))}",
        f"  Benchmark return: {_format_percent(index_record.get('benchmark_total_return'))}",
        f"  Excess return: {_format_percent(index_record.get('excess_total_return'))}",
        f"  CAGR: {_format_percent(metrics.get('cagr'))}",
        f"  Sharpe: {_format_decimal(metrics.get('sharpe_ratio'))}",
        f"  Max drawdown: {_format_percent(metrics.get('max_drawdown'))}",
        f"  Trades: {_format_plain(index_record.get('trade_count'))}",
        "",
        "Research Warnings",
        *_warning_lines(research_warnings),
        "",
        "Sizing And Costs",
        f"  Sizing: {_format_plain(metadata.get('sizing', {}).get('mode'))}",
        f"  Initial cash: {_format_money(metadata.get('sizing', {}).get('initial_cash'))}",
        f"  Quantity: {_format_plain(metadata.get('sizing', {}).get('quantity'))}",
        f"  Allocation: {_format_plain(metadata.get('sizing', {}).get('allocation'))}",
        f"  Cost preset: {_format_plain(metadata.get('costs', {}).get('preset'))}",
        f"  Commission fixed: {_format_money(metadata.get('costs', {}).get('commission_fixed'))}",
        f"  Commission rate: {_format_decimal(metadata.get('costs', {}).get('commission_rate'))}",
        f"  Slippage bps: {_format_plain(metadata.get('costs', {}).get('slippage_bps'))}",
        "",
        "Artifacts",
    ]

    for artifact_name in sorted(artifacts):
        lines.append(f"  {artifact_name}: {artifacts[artifact_name]}")

    command = metadata.get("command", [])
    if command:
        lines.extend(["", "Command", f"  {' '.join(str(token) for token in command)}"])

    return "\n".join(lines)


def load_run_summaries(metadata_paths: list[str | Path]) -> list[dict]:
    if len(metadata_paths) < 2:
        raise ValueError("compare-runs requires at least two --metadata paths")
    return [load_run_summary(path) for path in metadata_paths]


def verify_run_input_file(metadata_path: str | Path) -> dict:
    metadata_file = Path(metadata_path)
    if not metadata_file.exists():
        raise FileNotFoundError(f"metadata file not found: {metadata_file}")

    metadata = _read_json(metadata_file)
    expected_data = metadata.get("data", {})
    data_path = Path(str(expected_data.get("path") or ""))
    verification = {
        "metadata_path": str(metadata_file),
        "data_path": str(data_path) if expected_data.get("path") else None,
        "checks": {},
        "result": "reproducible input file",
    }

    if not expected_data.get("path"):
        verification["result"] = "metadata missing data path"
        return verification
    if not data_path.exists():
        verification["checks"]["file_exists"] = {"status": "missing"}
        verification["result"] = "data file missing"
        return verification

    actual_fingerprint = fingerprint_file(data_path)
    actual_data = pd.read_csv(data_path)
    actual_dates = pd.to_datetime(actual_data["date"]) if "date" in actual_data.columns and not actual_data.empty else None
    actual_start = _metadata_date(actual_dates.min()) if actual_dates is not None else None
    actual_end = _metadata_date(actual_dates.max()) if actual_dates is not None else None

    checks = {
        "file_sha256": _verification_check(expected_data.get("file_sha256"), actual_fingerprint["file_sha256"]),
        "file_size_bytes": _verification_check(expected_data.get("file_size_bytes"), actual_fingerprint["file_size_bytes"]),
        "row_count": _verification_check(expected_data.get("row_count"), int(len(actual_data))),
        "date_range": _verification_check(
            _range_value(expected_data.get("start"), expected_data.get("end")),
            _range_value(actual_start, actual_end),
        ),
    }
    verification["checks"] = checks
    if any(check["status"] != "match" for check in checks.values()):
        verification["result"] = "input file differs from metadata"
    return verification


def format_run_verification(verification: dict) -> str:
    checks = verification.get("checks", {})
    lines = [
        "Run Verification",
        "================",
        "",
        f"metadata: {_format_plain(verification.get('metadata_path'))}",
        f"data_path: {_format_plain(verification.get('data_path'))}",
    ]
    if not checks:
        lines.append(f"result: {_format_plain(verification.get('result'))}")
        return "\n".join(lines)

    for check_name in ["file_sha256", "file_size_bytes", "row_count", "date_range", "file_exists"]:
        if check_name not in checks:
            continue
        check = checks[check_name]
        lines.append(
            f"{check_name}: {check['status']} "
            f"(metadata={_format_plain(check.get('expected'))}, current={_format_plain(check.get('actual'))})"
        )
    lines.append(f"result: {_format_plain(verification.get('result'))}")
    return "\n".join(lines)


def format_run_comparison(summaries: list[dict]) -> str:
    rows = [_comparison_row(summary) for summary in summaries]
    columns = [
        ("run", "run"),
        ("symbol", "symbol"),
        ("strategy", "strategy"),
        ("return", "total_return"),
        ("bench_name", "benchmark_name"),
        ("bench", "benchmark_total_return"),
        ("excess", "excess_total_return"),
        ("dd", "max_drawdown"),
        ("sharpe", "sharpe_ratio"),
        ("trades", "trade_count"),
        ("comm", "commission_rate"),
        ("slip", "slippage_bps"),
        ("out", "output_dir"),
    ]
    table_rows = [
        [_format_comparison_value(row.get(field), field) for _, field in columns]
        for row in rows
    ]
    header = [label for label, _ in columns]
    widths = [
        max(len(header[index]), *[len(row[index]) for row in table_rows])
        for index in range(len(header))
    ]
    lines = [
        "  ".join(header[index].ljust(widths[index]) for index in range(len(header))),
        "  ".join("-" * widths[index] for index in range(len(header))),
    ]
    for row in table_rows:
        lines.append("  ".join(row[index].ljust(widths[index]) for index in range(len(row))))
    return "\n".join(lines)


def _comparison_row(summary: dict) -> dict:
    metadata = summary["metadata"]
    metrics = summary["metrics"]
    index_record = summary["index_record"] or {}
    artifacts = metadata.get("artifacts", {})
    return {
        "run": metadata.get("run_id") or Path(summary["metadata_path"]).parent.name,
        "symbol": metadata.get("data", {}).get("symbol"),
        "strategy": metadata.get("strategy", {}).get("strategy_id"),
        "total_return": metrics.get("total_return"),
        "benchmark_name": _benchmark_name(metadata, index_record),
        "benchmark_total_return": index_record.get("benchmark_total_return"),
        "excess_total_return": index_record.get("excess_total_return"),
        "max_drawdown": metrics.get("max_drawdown"),
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "trade_count": index_record.get("trade_count"),
        "commission_rate": metadata.get("costs", {}).get("commission_rate"),
        "slippage_bps": metadata.get("costs", {}).get("slippage_bps"),
        "output_dir": Path(artifacts.get("metadata", summary["metadata_path"])).parent,
    }


def _find_index_record(metadata: dict) -> dict | None:
    artifacts = metadata.get("artifacts", {})
    index_path = artifacts.get("research_index")
    metadata_path = artifacts.get("metadata")
    if not index_path or not metadata_path:
        return None

    for record in load_research_index(index_path):
        if record.get("metadata_path") == metadata_path:
            return record
    return None


def _benchmark_name(metadata: dict, index_record: dict) -> str | None:
    return index_record.get("benchmark_name") or metadata.get("benchmark", {}).get("name")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _metadata_date(value: pd.Timestamp) -> str:
    return value.date().isoformat()


def _range_value(start: object, end: object) -> str:
    return f"{start} to {end}"


def _verification_check(expected: object, actual: object) -> dict:
    return {
        "expected": expected,
        "actual": actual,
        "status": "match" if expected == actual else "mismatch",
    }


def _warning_lines(research_warnings: dict) -> list[str]:
    warnings = research_warnings.get("warnings") or []
    if not warnings:
        return ["  None"]
    return [f"  - {warning}" for warning in warnings]


def _format_plain(value: object) -> str:
    if value is None:
        return "-"
    return str(value)


def _format_money(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}"


def _format_percent(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2%}"


def _format_decimal(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.4f}"


def _format_comparison_value(value: object, field: str) -> str:
    if value is None:
        return "-"
    if field in {"total_return", "benchmark_total_return", "excess_total_return", "max_drawdown"}:
        return _format_percent(value)
    if field in {"sharpe_ratio", "commission_rate"}:
        return _format_decimal(value)
    return str(value)
