"""Helpers for inspecting saved portfolio run artifacts."""

from __future__ import annotations

import json
from pathlib import Path


def load_portfolio_run_summary(metadata_path: str | Path) -> dict:
    metadata_file = Path(metadata_path)
    if not metadata_file.exists():
        raise FileNotFoundError(f"portfolio metadata file not found: {metadata_file}")

    metadata = _read_json(metadata_file)
    metrics_path = metadata.get("artifacts", {}).get("metrics")
    if not metrics_path:
        raise ValueError(f"metadata file does not include a metrics artifact: {metadata_file}")

    metrics_file = Path(metrics_path)
    if not metrics_file.exists():
        raise FileNotFoundError(f"portfolio metrics file not found: {metrics_file}")

    benchmark_metrics_path = metadata.get("artifacts", {}).get("benchmark_metrics")
    benchmark_metrics = (
        _read_json(Path(benchmark_metrics_path))
        if benchmark_metrics_path and Path(benchmark_metrics_path).exists()
        else None
    )
    return {
        "metadata_path": str(metadata_file),
        "metadata": metadata,
        "metrics": _read_json(metrics_file),
        "benchmark_metrics": benchmark_metrics,
    }


def format_portfolio_run_summary(summary: dict) -> str:
    metadata = summary["metadata"]
    metrics = summary["metrics"]
    benchmark = metadata.get("benchmark") or {}
    artifacts = metadata.get("artifacts", {})

    lines = [
        "Portfolio Run Summary",
        "=====================",
        "",
        "Identity",
        f"  Portfolio: {_format_plain(metadata.get('portfolio_id'))}",
        f"  Name: {_format_plain(metadata.get('name'))}",
        f"  Run type: {_format_plain(metadata.get('run_type'))}",
        f"  Created UTC: {_format_plain(metadata.get('created_at_utc'))}",
        f"  Git commit: {_format_plain(metadata.get('environment', {}).get('git_commit'))}",
        "",
        "Portfolio Setup",
        f"  Initial cash: {_format_money(metadata.get('initial_cash'))}",
        f"  Alignment: {_format_plain(metadata.get('alignment_policy'))}",
        f"  Rebalance: {_format_plain(metadata.get('rebalance_frequency'))}",
        f"  Cost preset: {_format_plain(metadata.get('costs', {}).get('preset'))}",
        f"  Commission fixed: {_format_money(metadata.get('costs', {}).get('commission_fixed'))}",
        f"  Commission rate: {_format_decimal(metadata.get('costs', {}).get('commission_rate'))}",
        f"  Slippage bps: {_format_plain(metadata.get('costs', {}).get('slippage_bps'))}",
        "",
        "Results",
        f"  Final equity: {_format_money(metrics.get('ending_equity'))}",
        f"  Total return: {_format_percent(metrics.get('total_return'))}",
        f"  CAGR: {_format_percent(metrics.get('cagr'))}",
        f"  Sharpe: {_format_decimal(metrics.get('sharpe_ratio'))}",
        f"  Max drawdown: {_format_percent(metrics.get('max_drawdown'))}",
        f"  Benchmark: {_benchmark_label(benchmark)}",
        f"  Benchmark return: {_format_percent(benchmark.get('total_return'))}",
        f"  Excess return: {_format_percent(benchmark.get('excess_total_return'))}",
        "",
        "Symbols",
        *_symbol_lines(metadata.get("symbols") or []),
        "",
        "Artifacts",
    ]

    for artifact_name in sorted(artifacts):
        lines.append(f"  {artifact_name}: {artifacts[artifact_name]}")

    command = metadata.get("command", [])
    if command:
        lines.extend(["", "Command", f"  {' '.join(str(token) for token in command)}"])

    return "\n".join(lines)


def load_portfolio_run_summaries(metadata_paths: list[str | Path]) -> list[dict]:
    if len(metadata_paths) < 2:
        raise ValueError("compare-portfolio-runs requires at least two --metadata paths")
    return [load_portfolio_run_summary(path) for path in metadata_paths]


def format_portfolio_run_comparison(summaries: list[dict]) -> str:
    rows = [_comparison_row(summary) for summary in summaries]
    columns = [
        ("portfolio", "portfolio_id"),
        ("symbols", "symbols"),
        ("rebalance", "rebalance_frequency"),
        ("return", "total_return"),
        ("bench", "benchmark_total_return"),
        ("excess", "excess_total_return"),
        ("dd", "max_drawdown"),
        ("sharpe", "sharpe_ratio"),
        ("cost", "cost_preset"),
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


def _symbol_lines(symbols: list[dict]) -> list[str]:
    if not symbols:
        return ["  None"]

    lines: list[str] = []
    for symbol in symbols:
        fingerprint = str(symbol.get("file_sha256") or "-")
        if fingerprint != "-":
            fingerprint = fingerprint[:12]
        lines.append(
            "  {symbol}: target={target}, aligned_rows={aligned}, dropped={dropped}, "
            "quality={quality}, sha={sha}".format(
                symbol=_format_plain(symbol.get("symbol")),
                target=_format_percent(symbol.get("target_weight")),
                aligned=_format_plain(symbol.get("aligned_row_count")),
                dropped=_format_plain(symbol.get("dropped_rows")),
                quality=_format_plain(symbol.get("quality_severity")),
                sha=fingerprint,
            )
        )
    return lines


def _benchmark_label(benchmark: dict) -> str:
    symbol = benchmark.get("symbol")
    if not symbol:
        return "-"
    return f"buy-and-hold {symbol}"


def _comparison_row(summary: dict) -> dict:
    metadata = summary["metadata"]
    metrics = summary["metrics"]
    benchmark = metadata.get("benchmark") or {}
    artifacts = metadata.get("artifacts") or {}
    return {
        "portfolio_id": metadata.get("portfolio_id"),
        "symbols": ",".join(symbol.get("symbol", "-") for symbol in metadata.get("symbols", [])),
        "rebalance_frequency": metadata.get("rebalance_frequency"),
        "total_return": metrics.get("total_return"),
        "benchmark_total_return": benchmark.get("total_return"),
        "excess_total_return": benchmark.get("excess_total_return"),
        "max_drawdown": metrics.get("max_drawdown"),
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "cost_preset": metadata.get("costs", {}).get("preset"),
        "output_dir": Path(artifacts.get("metadata", summary["metadata_path"])).parent,
    }


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    if field == "sharpe_ratio":
        return _format_decimal(value)
    return str(value)
