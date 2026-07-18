"""Inspect local market-data CSV files and their provenance sidecars."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd

from backtester_core.data import validate_ohlcv_data

from .run_metadata import fingerprint_file


@dataclass(frozen=True)
class DataSourceInspection:
    csv_path: str
    row_count: int
    data_start: str
    data_end: str
    file_sha256: str
    file_size_bytes: int
    modified_at_utc: str
    provenance_path: str
    provenance_found: bool
    provenance: dict[str, Any]
    warnings: list[str]


def inspect_data_source(csv_path: str | Path) -> DataSourceInspection:
    """Summarize one local OHLCV CSV and its optional provenance JSON.

    This function intentionally validates the CSV through the same OHLCV helper
    used by backtests. That keeps this inspection command from blessing data the
    engine itself would later reject.
    """

    source_path = Path(csv_path)
    if not source_path.exists():
        raise FileNotFoundError(f"data CSV not found: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"data path is not a file: {source_path}")

    data = pd.read_csv(source_path)
    normalized = validate_ohlcv_data(data)
    fingerprint = fingerprint_file(source_path)
    provenance_path = source_path.with_suffix(".provenance.json")
    provenance: dict[str, Any] = {}
    warnings: list[str] = []

    if provenance_path.exists():
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            warnings.append(f"provenance file is not valid JSON: {exc.msg}")
    else:
        warnings.append("missing provenance sidecar")

    return DataSourceInspection(
        csv_path=str(source_path),
        row_count=int(len(normalized)),
        data_start=normalized.index.min().date().isoformat(),
        data_end=normalized.index.max().date().isoformat(),
        file_sha256=str(fingerprint["file_sha256"]),
        file_size_bytes=int(fingerprint["file_size_bytes"]),
        modified_at_utc=str(fingerprint["modified_at_utc"]),
        provenance_path=str(provenance_path),
        provenance_found=provenance_path.exists(),
        provenance=provenance,
        warnings=warnings,
    )


def format_data_source_inspection(inspection: DataSourceInspection) -> str:
    lines = [
        f"data: {inspection.csv_path}",
        f"rows: {inspection.row_count}",
        f"date_range: {inspection.data_start} to {inspection.data_end}",
        f"file_sha256: {inspection.file_sha256[:12]}...",
        f"file_size_bytes: {inspection.file_size_bytes}",
        f"modified_at_utc: {inspection.modified_at_utc}",
        f"provenance: {inspection.provenance_path}",
    ]

    if inspection.provenance_found and inspection.provenance:
        provenance = inspection.provenance
        lines.extend(
            [
                f"provenance_schema_version: {provenance.get('provenance_schema_version', 'unknown')}",
                f"provider: {provenance.get('provider', 'unknown')}",
                f"symbol: {provenance.get('symbol', 'unknown')}",
                f"requested_range: {provenance.get('requested_start', 'unknown')} to {provenance.get('requested_end', 'unknown')}",
                f"actual_range: {provenance.get('data_start', 'unknown')} to {provenance.get('data_end', 'unknown')}",
                f"fetched_at_utc: {provenance.get('fetched_at_utc', 'unknown')}",
                f"provenance_rows: {provenance.get('row_count', 'unknown')}",
            ]
        )
    elif not inspection.provenance_found:
        lines.append("provenance_status: missing")
    else:
        lines.append("provenance_status: unreadable")

    if inspection.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in inspection.warnings)
    else:
        lines.append("warnings: none")

    return "\n".join(lines)
