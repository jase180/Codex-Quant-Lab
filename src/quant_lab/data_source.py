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


@dataclass(frozen=True)
class DataCacheEntry:
    csv_path: str
    symbol: str
    row_count: int | None
    data_start: str | None
    data_end: str | None
    file_sha256_prefix: str | None
    provenance_found: bool
    warnings: list[str]
    error: str | None = None


@dataclass(frozen=True)
class DataCacheInventory:
    data_dir: str
    entries: list[DataCacheEntry]
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


def list_data_cache(data_dir: str | Path) -> DataCacheInventory:
    cache_dir = Path(data_dir)
    if not cache_dir.exists():
        raise FileNotFoundError(f"data cache directory not found: {cache_dir}")
    if not cache_dir.is_dir():
        raise ValueError(f"data cache path is not a directory: {cache_dir}")

    entries = [_cache_entry(path) for path in sorted(cache_dir.glob("*.csv"))]
    warnings = _duplicate_cache_warnings(entries)
    return DataCacheInventory(data_dir=str(cache_dir), entries=entries, warnings=warnings)


def format_data_cache_inventory(inventory: DataCacheInventory) -> str:
    lines = [
        f"data_dir: {inventory.data_dir}",
        f"csv_files: {len(inventory.entries)}",
        "",
        "symbol  rows  date_range                 sha           provenance  path",
        "------  ----  -------------------------  ------------  ----------  ----",
    ]
    for entry in inventory.entries:
        rows = str(entry.row_count) if entry.row_count is not None else "-"
        date_range = (
            f"{entry.data_start} to {entry.data_end}"
            if entry.data_start and entry.data_end
            else "-"
        )
        sha = entry.file_sha256_prefix or "-"
        provenance = "yes" if entry.provenance_found else "no"
        lines.append(
            f"{entry.symbol:<6}  {rows:<4}  {date_range:<25}  {sha:<12}  {provenance:<10}  {entry.csv_path}"
        )

    entry_warnings = [
        f"{Path(entry.csv_path).name}: {warning}"
        for entry in inventory.entries
        for warning in entry.warnings
    ]
    all_warnings = [*inventory.warnings, *entry_warnings]
    lines.append("")
    if all_warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in all_warnings)
    else:
        lines.append("warnings: none")
    return "\n".join(lines)


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


def _cache_entry(path: Path) -> DataCacheEntry:
    try:
        inspection = inspect_data_source(path)
    except Exception as exc:
        return DataCacheEntry(
            csv_path=str(path),
            symbol=_symbol_from_filename(path),
            row_count=None,
            data_start=None,
            data_end=None,
            file_sha256_prefix=None,
            provenance_found=path.with_suffix(".provenance.json").exists(),
            warnings=["unreadable CSV"],
            error=str(exc),
        )

    symbol = str(inspection.provenance.get("symbol") or _symbol_from_filename(path)).upper()
    return DataCacheEntry(
        csv_path=inspection.csv_path,
        symbol=symbol,
        row_count=inspection.row_count,
        data_start=inspection.data_start,
        data_end=inspection.data_end,
        file_sha256_prefix=inspection.file_sha256[:12],
        provenance_found=inspection.provenance_found,
        warnings=[*inspection.warnings],
    )


def _duplicate_cache_warnings(entries: list[DataCacheEntry]) -> list[str]:
    groups: dict[tuple[str, str | None, str | None], list[DataCacheEntry]] = {}
    for entry in entries:
        if entry.error is not None:
            continue
        key = (entry.symbol, entry.data_start, entry.data_end)
        groups.setdefault(key, []).append(entry)

    warnings: list[str] = []
    for (symbol, start, end), grouped_entries in sorted(groups.items()):
        if len(grouped_entries) < 2:
            continue
        paths = ", ".join(Path(entry.csv_path).name for entry in grouped_entries)
        warnings.append(f"duplicate-looking cache files for {symbol} {start} to {end}: {paths}")
    return warnings


def _symbol_from_filename(path: Path) -> str:
    name = path.stem
    if "_" not in name:
        return name.upper()
    return name.split("_", 1)[0].upper()
