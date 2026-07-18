"""Build trust reports for saved single-strategy runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_source import inspect_data_source
from .run_inspection import verify_run_input_file
from .trust_common import classify_trust_warnings, plain, read_json


RUN_TRUST_REPORT_FILENAME = "run_trust_report.md"


@dataclass(frozen=True)
class RunTrustReport:
    metadata_path: str
    report_path: str
    result: str
    worst_warning: str
    warnings: list[str]
    markdown: str


def summarize_run_trust(
    metadata_path: str | Path,
    output_path: str | Path | None = None,
) -> RunTrustReport:
    metadata_file = Path(metadata_path)
    if not metadata_file.exists():
        raise FileNotFoundError(f"metadata file not found: {metadata_file}")

    metadata = read_json(metadata_file)
    verification = verify_run_input_file(metadata_file)
    data_path = verification.get("data_path")
    data_source = _inspect_existing_data_source(data_path)
    data_quality = _read_optional_artifact(metadata, "data_quality")

    warnings = _trust_warnings(
        verification=verification,
        data_source_warnings=data_source.warnings if data_source else [],
        data_quality=data_quality,
    )
    worst_warning = classify_trust_warnings(warnings)
    report_file = Path(output_path) if output_path is not None else metadata_file.parent / RUN_TRUST_REPORT_FILENAME
    markdown = _render_run_trust_report(
        metadata=metadata,
        metadata_file=metadata_file,
        verification=verification,
        data_source=data_source,
        data_quality=data_quality,
        warnings=warnings,
        worst_warning=worst_warning,
    )
    report_file.write_text(markdown, encoding="utf-8")

    return RunTrustReport(
        metadata_path=str(metadata_file),
        report_path=str(report_file),
        result=str(verification.get("result")),
        worst_warning=worst_warning,
        warnings=warnings,
        markdown=markdown,
    )


def _render_run_trust_report(
    *,
    metadata: dict[str, Any],
    metadata_file: Path,
    verification: dict[str, Any],
    data_source,
    data_quality: dict[str, Any] | None,
    warnings: list[str],
    worst_warning: str,
) -> str:
    data = metadata.get("data", {})
    strategy = metadata.get("strategy", {})

    lines = [
        "# Run Trust Report",
        "",
        "## Summary",
        "",
        f"- Metadata: `{metadata_file}`",
        f"- Strategy: {plain(strategy.get('strategy_id'))}",
        f"- Symbol: {plain(data.get('symbol'))}",
        f"- Verification result: {verification.get('result')}",
        f"- Worst warning: {worst_warning}",
        "",
        "## Data Verification",
        "",
        "| Check | Status | Metadata | Current |",
        "| --- | --- | --- | --- |",
    ]
    for check_name, check in verification.get("checks", {}).items():
        lines.append(
            f"| {check_name} | {check.get('status')} | {plain(check.get('expected'))} | {plain(check.get('actual'))} |"
        )

    if data_source is not None:
        provenance = data_source.provenance
        lines.extend(
            [
                "",
                "## Data Source",
                "",
                f"- Data path: `{data_source.csv_path}`",
                f"- Rows: {data_source.row_count}",
                f"- Date range: {data_source.data_start} to {data_source.data_end}",
                f"- File SHA256: `{data_source.file_sha256}`",
                f"- Provenance path: `{data_source.provenance_path}`",
                f"- Provenance status: {'found' if data_source.provenance_found else 'missing'}",
            ]
        )
        if provenance:
            lines.extend(
                [
                    f"- Provider: {plain(provenance.get('provider'))}",
                    f"- Requested range: {plain(provenance.get('requested_start'))} to {plain(provenance.get('requested_end'))}",
                    f"- Actual range: {plain(provenance.get('data_start'))} to {plain(provenance.get('data_end'))}",
                    f"- Fetched at UTC: {plain(provenance.get('fetched_at_utc'))}",
                    f"- Provenance schema: {plain(provenance.get('provenance_schema_version'))}",
                ]
            )

    lines.extend(["", "## Data Quality", ""])
    if data_quality:
        lines.extend(
            [
                f"- Worst severity: {plain(data_quality.get('worst_severity'))}",
                f"- Rows: {plain(data_quality.get('row_count'))}",
                f"- Duplicate dates: {plain(data_quality.get('duplicate_dates'))}",
                f"- Missing OHLCV values: {plain(data_quality.get('missing_ohlcv_values'))}",
                f"- Zero-volume rows: {plain(data_quality.get('zero_volume_rows'))}",
                f"- Non-positive price rows: {plain(data_quality.get('non_positive_price_rows'))}",
                "",
                "Findings:",
            ]
        )
        findings = data_quality.get("findings") or []
        lines.extend(
            f"- {finding.get('severity')}: {finding.get('message')}" for finding in findings
        )
        if not findings:
            lines.append("- None")
    else:
        lines.append("- Data quality artifact missing.")

    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _trust_warnings(
    *,
    verification: dict[str, Any],
    data_source_warnings: list[str],
    data_quality: dict[str, Any] | None,
) -> list[str]:
    warnings: list[str] = []
    result = verification.get("result")
    if result != "reproducible input file":
        warnings.append(str(result))

    warnings.extend(data_source_warnings)

    if data_quality is None:
        warnings.append("data quality artifact missing")
    else:
        severity = data_quality.get("worst_severity")
        if severity and severity != "none":
            warnings.append(f"data quality severity is {severity}")
    return warnings


def _read_optional_artifact(metadata: dict[str, Any], artifact_name: str) -> dict[str, Any] | None:
    artifact_path = metadata.get("artifacts", {}).get(artifact_name)
    if not artifact_path:
        return None
    path = Path(artifact_path)
    if not path.exists():
        return None
    return read_json(path)


def _inspect_existing_data_source(data_path: object):
    if not data_path:
        return None
    path = Path(str(data_path))
    if not path.exists():
        return None
    return inspect_data_source(path)
