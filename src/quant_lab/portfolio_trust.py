"""Build data-trust reports for saved portfolio runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .data_source import inspect_data_source
from .run_metadata import fingerprint_file
from .trust_common import (
    classify_trust_warnings,
    metadata_date,
    plain,
    range_value,
    read_json,
    verification_check,
)


PORTFOLIO_DATA_TRUST_REPORT_FILENAME = "portfolio_data_trust_report.md"


@dataclass(frozen=True)
class PortfolioDataTrustReport:
    metadata_path: str
    report_path: str
    worst_warning: str
    warnings: list[str]
    markdown: str


def summarize_portfolio_data_trust(
    metadata_path: str | Path,
    output_path: str | Path | None = None,
) -> PortfolioDataTrustReport:
    metadata_file = Path(metadata_path)
    if not metadata_file.exists():
        raise FileNotFoundError(f"portfolio metadata file not found: {metadata_file}")

    metadata = read_json(metadata_file)
    symbol_base_dir = _portfolio_symbol_base_dir(metadata)
    symbol_checks = [
        _portfolio_symbol_check(symbol, base_dir=symbol_base_dir)
        for symbol in metadata.get("symbols", [])
    ]
    benchmark_check = _benchmark_check(metadata.get("benchmark"))
    warnings = _trust_warnings(symbol_checks=symbol_checks, benchmark_check=benchmark_check)
    worst_warning = classify_trust_warnings(warnings)
    report_file = (
        Path(output_path)
        if output_path is not None
        else metadata_file.parent / PORTFOLIO_DATA_TRUST_REPORT_FILENAME
    )
    markdown = _render_portfolio_data_trust_report(
        metadata=metadata,
        metadata_file=metadata_file,
        symbol_checks=symbol_checks,
        benchmark_check=benchmark_check,
        warnings=warnings,
        worst_warning=worst_warning,
    )
    report_file.write_text(markdown, encoding="utf-8")
    return PortfolioDataTrustReport(
        metadata_path=str(metadata_file),
        report_path=str(report_file),
        worst_warning=worst_warning,
        warnings=warnings,
        markdown=markdown,
    )


def _portfolio_symbol_check(symbol: dict[str, Any], *, base_dir: Path | None) -> dict[str, Any]:
    stored_path = str(symbol.get("path") or "")
    path = _resolve_metadata_path(stored_path, base_dir=base_dir)
    check = {
        "kind": "symbol",
        "symbol": symbol.get("symbol"),
        "path": stored_path or None,
        "resolved_path": str(path) if stored_path else None,
        "target_weight": symbol.get("target_weight"),
        "aligned_row_count": symbol.get("aligned_row_count"),
        "dropped_rows": symbol.get("dropped_rows"),
        "quality_severity": symbol.get("quality_severity"),
        "checks": {},
        "data_source": None,
        "result": "reproducible input file",
    }
    if not symbol.get("path"):
        check["result"] = "metadata missing data path"
        return check
    if not path.exists():
        check["checks"]["file_exists"] = {"status": "missing", "expected": "present", "actual": "missing"}
        check["result"] = "data file missing"
        return check

    fingerprint = fingerprint_file(path)
    data = pd.read_csv(path)
    dates = pd.to_datetime(data["date"]) if "date" in data.columns and not data.empty else None
    actual_start = metadata_date(dates.min()) if dates is not None else None
    actual_end = metadata_date(dates.max()) if dates is not None else None
    checks = {
        "file_sha256": verification_check(symbol.get("file_sha256"), fingerprint["file_sha256"]),
        "file_size_bytes": verification_check(symbol.get("file_size_bytes"), fingerprint["file_size_bytes"]),
        "row_count": verification_check(symbol.get("row_count"), int(len(data))),
        "date_range": verification_check(
            range_value(symbol.get("start"), symbol.get("end")),
            range_value(actual_start, actual_end),
        ),
    }
    check["checks"] = checks
    if any(item["status"] != "match" for item in checks.values()):
        check["result"] = "input file differs from metadata"
    check["data_source"] = _inspect_optional_data_source(path)
    return check


def _benchmark_check(benchmark: dict[str, Any] | None) -> dict[str, Any] | None:
    if not benchmark:
        return None
    path = Path(str(benchmark.get("data_path") or ""))
    check = {
        "kind": "benchmark",
        "symbol": benchmark.get("symbol"),
        "path": str(path) if benchmark.get("data_path") else None,
        "resolved_path": str(path) if benchmark.get("data_path") else None,
        "checks": {},
        "data_source": None,
        "result": "reproducible input file",
    }
    if not benchmark.get("data_path"):
        check["result"] = "metadata missing data path"
        return check
    if not path.exists():
        check["checks"]["file_exists"] = {"status": "missing", "expected": "present", "actual": "missing"}
        check["result"] = "data file missing"
        return check

    fingerprint = fingerprint_file(path)
    checks = {
        "file_sha256": verification_check(benchmark.get("file_sha256"), fingerprint["file_sha256"]),
        "file_size_bytes": verification_check(benchmark.get("file_size_bytes"), fingerprint["file_size_bytes"]),
    }
    check["checks"] = checks
    if any(item["status"] != "match" for item in checks.values()):
        check["result"] = "input file differs from metadata"
    check["data_source"] = _inspect_optional_data_source(path)
    return check


def _render_portfolio_data_trust_report(
    *,
    metadata: dict[str, Any],
    metadata_file: Path,
    symbol_checks: list[dict[str, Any]],
    benchmark_check: dict[str, Any] | None,
    warnings: list[str],
    worst_warning: str,
) -> str:
    lines = [
        "# Portfolio Data Trust Report",
        "",
        "## Summary",
        "",
        f"- Metadata: `{metadata_file}`",
        f"- Portfolio: {plain(metadata.get('portfolio_id'))}",
        f"- Name: {plain(metadata.get('name'))}",
        f"- Alignment policy: {plain(metadata.get('alignment_policy'))}",
        f"- Rebalance: {plain(metadata.get('rebalance_frequency'))}",
        f"- Worst warning: {worst_warning}",
        "",
        "## Symbol Inputs",
        "",
        "| Symbol | Result | Quality | Aligned Rows | Dropped Rows | Path |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for check in symbol_checks:
        lines.append(
            "| {symbol} | {result} | {quality} | {aligned} | {dropped} | `{path}` |".format(
                symbol=plain(check.get("symbol")),
                result=plain(check.get("result")),
                quality=plain(check.get("quality_severity")),
                aligned=plain(check.get("aligned_row_count")),
                dropped=plain(check.get("dropped_rows")),
                path=plain(check.get("path")),
            )
        )

    lines.extend(["", "## Symbol Verification", ""])
    for check in symbol_checks:
        lines.extend(_verification_section(check))

    if benchmark_check is not None:
        lines.extend(["", "## Benchmark Verification", ""])
        lines.extend(_verification_section(benchmark_check))

    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _verification_section(check: dict[str, Any]) -> list[str]:
    label = f"{check.get('kind')}: {check.get('symbol')}"
    lines = [
        f"### {label}",
        "",
        f"- Path: `{plain(check.get('path'))}`",
        f"- Resolved path: `{plain(check.get('resolved_path'))}`",
        f"- Result: {plain(check.get('result'))}",
    ]
    data_source = check.get("data_source")
    if data_source is not None:
        lines.extend(
            [
                f"- Date range: {data_source.data_start} to {data_source.data_end}",
                f"- Provenance: {'found' if data_source.provenance_found else 'missing'}",
            ]
        )
        provider = data_source.provenance.get("provider") if data_source.provenance else None
        if provider:
            lines.append(f"- Provider: {provider}")

    lines.extend(["", "| Check | Status | Metadata | Current |", "| --- | --- | --- | --- |"])
    for check_name, item in check.get("checks", {}).items():
        lines.append(
            f"| {check_name} | {item.get('status')} | {plain(item.get('expected'))} | {plain(item.get('actual'))} |"
        )
    if not check.get("checks"):
        lines.append("| - | - | - | - |")
    lines.append("")
    return lines


def _trust_warnings(
    *,
    symbol_checks: list[dict[str, Any]],
    benchmark_check: dict[str, Any] | None,
) -> list[str]:
    warnings: list[str] = []
    for check in symbol_checks:
        label = f"symbol {check.get('symbol')}"
        _append_check_warnings(warnings, label, check)
        severity = check.get("quality_severity")
        if severity and severity != "none":
            warnings.append(f"{label} data quality severity is {severity}")

    if benchmark_check is not None:
        _append_check_warnings(warnings, f"benchmark {benchmark_check.get('symbol')}", benchmark_check)
    return warnings


def _append_check_warnings(warnings: list[str], label: str, check: dict[str, Any]) -> None:
    if check.get("result") != "reproducible input file":
        warnings.append(f"{label}: {check.get('result')}")
    data_source = check.get("data_source")
    if data_source is not None:
        warnings.extend(f"{label}: {warning}" for warning in data_source.warnings)


def _inspect_optional_data_source(path: Path):
    if not path.exists():
        return None
    return inspect_data_source(path)


def _portfolio_symbol_base_dir(metadata: dict[str, Any]) -> Path | None:
    portfolio_spec_path = metadata.get("portfolio_spec", {}).get("path")
    if not portfolio_spec_path:
        return None
    return Path(str(portfolio_spec_path)).parent


def _resolve_metadata_path(path: str, *, base_dir: Path | None) -> Path:
    resolved = Path(path)
    if resolved.is_absolute() or base_dir is None:
        return resolved
    return base_dir / resolved
