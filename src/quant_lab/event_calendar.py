"""Generated event calendars for mechanism-first research.

These helpers deliberately operate on trading dates only. They should not read
returns, prices, or indicators when deciding which rows belong in an event
calendar; otherwise the calendar could quietly become data-mined.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .run_metadata import fingerprint_file


EVENT_CALENDAR_SCHEMA_VERSION = "event_calendar.v1"
EVENT_CALENDAR_PROVENANCE_SCHEMA_VERSION = "event_calendar_provenance.v1"
EVENT_CALENDAR_COLUMNS = [
    "event_id",
    "event_type",
    "event_date",
    "window_start",
    "window_end",
    "source_name",
    "source_url_or_note",
    "generated_without_return_data",
    "created_at_utc",
]


@dataclass(frozen=True)
class EventCalendarGenerationResult:
    csv_path: Path
    provenance_path: Path
    event_count: int
    counts_by_type: dict[str, int]
    warnings: list[str]


@dataclass(frozen=True)
class EventCalendarInspection:
    csv_path: Path
    event_count: int
    counts_by_type: dict[str, int]
    date_start: str | None
    date_end: str | None
    invalid_rows: list[str]
    warnings: list[str]

    @property
    def is_valid(self) -> bool:
        return not self.invalid_rows


def generate_calendar_rebalance_event_calendar(
    *,
    reference_data_path: str | Path,
    out_path: str | Path,
    start: str,
    end: str,
    window_trading_days: int,
    created_at_utc: str | None = None,
    force: bool = False,
) -> EventCalendarGenerationResult:
    if window_trading_days < 0:
        raise ValueError("window_trading_days must be zero or greater")

    destination = Path(out_path)
    if destination.exists() and not force:
        raise FileExistsError(f"Event calendar already exists: {destination}")

    reference_path = Path(reference_data_path)
    trading_dates = _read_trading_dates(reference_path)
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")
    if start_date > end_date:
        raise ValueError("start must be on or before end")

    trading_dates = [day for day in trading_dates if start_date <= day <= end_date]
    if not trading_dates:
        raise ValueError(f"No trading dates found between {start} and {end}")

    created_at = created_at_utc or _utc_now_iso()
    rows, warnings = _build_calendar_rebalance_rows(
        trading_dates=trading_dates,
        window_trading_days=window_trading_days,
        created_at_utc=created_at,
        source_note=f"Generated from trading dates in {reference_path.as_posix()}; price and return columns were not used.",
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_event_calendar_csv(destination, rows)
    provenance_path = destination.with_suffix(".provenance.json")
    _write_provenance(
        provenance_path=provenance_path,
        reference_data_path=reference_path,
        out_path=destination,
        start=start,
        end=end,
        window_trading_days=window_trading_days,
        created_at_utc=created_at,
        event_count=len(rows),
        counts_by_type=dict(Counter(row["event_type"] for row in rows)),
        warnings=warnings,
    )

    return EventCalendarGenerationResult(
        csv_path=destination,
        provenance_path=provenance_path,
        event_count=len(rows),
        counts_by_type=dict(Counter(row["event_type"] for row in rows)),
        warnings=warnings,
    )


def inspect_event_calendar(path: str | Path) -> EventCalendarInspection:
    csv_path = Path(path)
    rows = _read_event_calendar_rows(csv_path)
    invalid_rows: list[str] = []
    warnings: list[str] = []

    event_ids: set[str] = set()
    event_dates: list[date] = []
    for row_number, row in enumerate(rows, start=2):
        missing_values = [column for column in EVENT_CALENDAR_COLUMNS if not row.get(column)]
        if missing_values:
            invalid_rows.append(f"row {row_number}: missing values for {', '.join(missing_values)}")
            continue

        event_id = str(row["event_id"])
        if event_id in event_ids:
            invalid_rows.append(f"row {row_number}: duplicate event_id {event_id}")
        event_ids.add(event_id)

        try:
            event_date = _parse_date(str(row["event_date"]), "event_date")
            window_start = _parse_date(str(row["window_start"]), "window_start")
            window_end = _parse_date(str(row["window_end"]), "window_end")
        except ValueError as exc:
            invalid_rows.append(f"row {row_number}: {exc}")
            continue

        if not window_start <= event_date <= window_end:
            invalid_rows.append(
                f"row {row_number}: expected window_start <= event_date <= window_end"
            )
        event_dates.append(event_date)

        if str(row["generated_without_return_data"]).lower() != "true":
            invalid_rows.append(
                f"row {row_number}: generated_without_return_data must be true"
            )

    provenance_path = csv_path.with_suffix(".provenance.json")
    if not provenance_path.exists():
        warnings.append(f"Missing provenance sidecar: {provenance_path}")

    counts = dict(Counter(row["event_type"] for row in rows))
    return EventCalendarInspection(
        csv_path=csv_path,
        event_count=len(rows),
        counts_by_type=counts,
        date_start=min(event_dates).isoformat() if event_dates else None,
        date_end=max(event_dates).isoformat() if event_dates else None,
        invalid_rows=invalid_rows,
        warnings=warnings,
    )


def format_event_calendar_generation(result: EventCalendarGenerationResult) -> str:
    lines = [
        "# Event Calendar Generated",
        "",
        f"- CSV: `{result.csv_path}`",
        f"- Provenance: `{result.provenance_path}`",
        f"- Events: {result.event_count}",
        "- Counts by type:",
        *_format_count_lines(result.counts_by_type),
    ]
    if result.warnings:
        lines.extend(["", "Warnings:", *_format_bullets(result.warnings)])
    return "\n".join(lines)


def format_event_calendar_inspection(inspection: EventCalendarInspection) -> str:
    status = "valid" if inspection.is_valid else "invalid"
    lines = [
        "# Event Calendar Inspection",
        "",
        f"- Path: `{inspection.csv_path}`",
        f"- Status: {status}",
        f"- Events: {inspection.event_count}",
        f"- Date range: {inspection.date_start or 'n/a'} to {inspection.date_end or 'n/a'}",
        "- Counts by type:",
        *_format_count_lines(inspection.counts_by_type),
    ]
    if inspection.invalid_rows:
        lines.extend(["", "Invalid rows:", *_format_bullets(inspection.invalid_rows)])
    if inspection.warnings:
        lines.extend(["", "Warnings:", *_format_bullets(inspection.warnings)])
    return "\n".join(lines)


def _read_trading_dates(path: Path) -> list[date]:
    if not path.exists():
        raise FileNotFoundError(f"Reference data not found: {path}")

    frame = pd.read_csv(path)
    date_column = _find_date_column(frame.columns)
    if date_column is None:
        raise ValueError(f"Reference data must include a date column: {path}")

    dates = pd.to_datetime(frame[date_column], errors="raise").dt.date.tolist()
    unique_dates = sorted(set(dates))
    if len(unique_dates) != len(dates):
        raise ValueError(f"Reference data contains duplicate trading dates: {path}")
    return unique_dates


def _find_date_column(columns: Iterable[object]) -> str | None:
    for column in columns:
        if str(column).lower() == "date":
            return str(column)
    return None


def _build_calendar_rebalance_rows(
    *,
    trading_dates: list[date],
    window_trading_days: int,
    created_at_utc: str,
    source_note: str,
) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    warnings: list[str] = []
    date_to_index = {trading_date: index for index, trading_date in enumerate(trading_dates)}

    month_ends = _last_trading_day_by_month(trading_dates)
    quarter_ends = _last_trading_day_by_quarter(trading_dates)
    event_specs: list[tuple[str, str, date]] = [
        *[(f"month_end_{day:%Y_%m}", "month_end", day) for day in month_ends],
        *[
            (f"quarter_end_{day.year}_q{((day.month - 1) // 3) + 1}", "quarter_end", day)
            for day in quarter_ends
        ],
    ]

    for event_id, event_type, event_date in sorted(event_specs, key=lambda item: (item[2], item[1])):
        event_index = date_to_index[event_date]
        window_start_index = event_index - window_trading_days
        window_end_index = event_index + window_trading_days
        if window_start_index < 0 or window_end_index >= len(trading_dates):
            warnings.append(
                f"Skipped {event_id}: full +/-{window_trading_days} trading-day window is outside the date range"
            )
            continue
        rows.append(
            {
                "event_id": event_id,
                "event_type": event_type,
                "event_date": event_date.isoformat(),
                "window_start": trading_dates[window_start_index].isoformat(),
                "window_end": trading_dates[window_end_index].isoformat(),
                "source_name": "deterministic_trading_calendar",
                "source_url_or_note": source_note,
                "generated_without_return_data": "true",
                "created_at_utc": created_at_utc,
            }
        )
    return rows, warnings


def _last_trading_day_by_month(trading_dates: list[date]) -> list[date]:
    latest: dict[tuple[int, int], date] = {}
    for trading_date in trading_dates:
        latest[(trading_date.year, trading_date.month)] = trading_date
    return [latest[key] for key in sorted(latest)]


def _last_trading_day_by_quarter(trading_dates: list[date]) -> list[date]:
    latest: dict[tuple[int, int], date] = {}
    for trading_date in trading_dates:
        quarter = ((trading_date.month - 1) // 3) + 1
        latest[(trading_date.year, quarter)] = trading_date
    return [latest[key] for key in sorted(latest)]


def _write_event_calendar_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_CALENDAR_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_event_calendar_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Event calendar not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EVENT_CALENDAR_COLUMNS:
            raise ValueError(
                "Event calendar columns must exactly match "
                f"{', '.join(EVENT_CALENDAR_COLUMNS)}"
            )
        return [dict(row) for row in reader]


def _write_provenance(
    *,
    provenance_path: Path,
    reference_data_path: Path,
    out_path: Path,
    start: str,
    end: str,
    window_trading_days: int,
    created_at_utc: str,
    event_count: int,
    counts_by_type: dict[str, int],
    warnings: list[str],
) -> None:
    payload = {
        "schema_version": EVENT_CALENDAR_PROVENANCE_SCHEMA_VERSION,
        "event_calendar_schema_version": EVENT_CALENDAR_SCHEMA_VERSION,
        "dataset_id": "calendar_rebalance_daily_proxy",
        "mechanism_id": "calendar_rebalance_effects",
        "csv_path": out_path.as_posix(),
        "reference_trading_calendar_path": reference_data_path.as_posix(),
        "reference_file_fingerprint": fingerprint_file(reference_data_path),
        "start": start,
        "end": end,
        "window_trading_days": window_trading_days,
        "event_types": ["month_end", "quarter_end"],
        "generated_without_return_data": True,
        "created_at_utc": created_at_utc,
        "event_count": event_count,
        "counts_by_type": counts_by_type,
        "warnings": warnings,
    }
    provenance_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date: {value}") from exc


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _format_count_lines(counts: dict[str, int]) -> list[str]:
    if not counts:
        return ["  - none"]
    return [f"  - `{key}`: {counts[key]}" for key in sorted(counts)]


def _format_bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]
