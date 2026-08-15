"""Generated event calendars for mechanism-first research.

These helpers deliberately operate on trading dates only. They should not read
returns, prices, or indicators when deciding which rows belong in an event
calendar; otherwise the calendar could quietly become data-mined.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable

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


@dataclass(frozen=True)
class EventStudyResult:
    output_dir: Path
    json_path: Path
    markdown_path: Path
    event_returns_path: Path
    symbol_count: int
    event_count: int
    event_type_count: int


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


def run_event_study(
    *,
    calendar_path: str | Path,
    data_specs: list[str],
    out_dir: str | Path,
    close_column: str = "close",
    force: bool = False,
) -> EventStudyResult:
    inspection = inspect_event_calendar(calendar_path)
    if not inspection.is_valid:
        raise ValueError("Event calendar is invalid; run event-calendar inspect first")

    destination = Path(out_dir)
    if destination.exists() and any(destination.iterdir()) and not force:
        raise FileExistsError(f"Output directory is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    calendar_rows = _read_event_calendar_rows(Path(calendar_path))
    symbol_frames = [_load_symbol_returns(spec, close_column=close_column) for spec in data_specs]
    if not symbol_frames:
        raise ValueError("At least one --data SYMBOL=CSV input is required")

    event_return_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, Any]] = []
    for symbol, frame in symbol_frames:
        symbol_event_rows = _event_returns_for_symbol(symbol, frame, calendar_rows)
        event_return_rows.extend(symbol_event_rows)
        summary_rows.extend(_summarize_symbol_event_rows(symbol, symbol_event_rows, frame))

    event_returns_path = destination / "event_returns.csv"
    _write_dict_csv(event_returns_path, event_return_rows, fieldnames=EVENT_STUDY_RETURN_COLUMNS)

    payload = {
        "schema_version": "event_study.v1",
        "calendar_path": Path(calendar_path).as_posix(),
        "close_column": close_column,
        "symbols": [symbol for symbol, _frame in symbol_frames],
        "event_count": len(calendar_rows),
        "event_type_count": len({row["event_type"] for row in calendar_rows}),
        "method": {
            "return_definition": (
                "Daily close-to-close returns are measured for pre-event, event-day, post-event, "
                "and full event windows. No trades, fills, costs, or position sizing are simulated."
            ),
            "event_selection": "Events come from the supplied event calendar and are not selected from returns.",
            "non_event_comparison": "Mean daily close-to-close returns outside any event window for the same symbol.",
        },
        "summary": summary_rows,
        "artifacts": {
            "markdown_report": "event_study_report.md",
            "event_returns": "event_returns.csv",
        },
    }
    json_path = destination / "event_study.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    markdown_path = destination / "event_study_report.md"
    markdown_path.write_text(_render_event_study_markdown(payload), encoding="utf-8")

    return EventStudyResult(
        output_dir=destination,
        json_path=json_path,
        markdown_path=markdown_path,
        event_returns_path=event_returns_path,
        symbol_count=len(symbol_frames),
        event_count=len(calendar_rows),
        event_type_count=len({row["event_type"] for row in calendar_rows}),
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


def format_event_study_result(result: EventStudyResult) -> str:
    return "\n".join(
        [
            "# Event Study Written",
            "",
            f"- Output directory: `{result.output_dir}`",
            f"- Report: `{result.markdown_path}`",
            f"- JSON: `{result.json_path}`",
            f"- Event returns: `{result.event_returns_path}`",
            f"- Symbols: {result.symbol_count}",
            f"- Events: {result.event_count}",
            f"- Event types: {result.event_type_count}",
        ]
    )


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


EVENT_STUDY_RETURN_COLUMNS = [
    "symbol",
    "event_id",
    "event_type",
    "event_date",
    "window_start",
    "window_end",
    "window_trading_days",
    "window_return",
    "pre_event_return",
    "event_day_return",
    "post_event_return",
]


def _load_symbol_returns(data_spec: str, *, close_column: str) -> tuple[str, pd.DataFrame]:
    symbol, path = _parse_data_spec(data_spec)
    data_path = Path(path)
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found for {symbol}: {data_path}")

    frame = pd.read_csv(data_path)
    date_column = _find_date_column(frame.columns)
    if date_column is None:
        raise ValueError(f"Data file for {symbol} must include a date column: {data_path}")
    actual_close_column = _find_column(frame.columns, close_column)
    if actual_close_column is None:
        raise ValueError(f"Data file for {symbol} must include close column {close_column}: {data_path}")

    loaded = pd.DataFrame(
        {
            "date": pd.to_datetime(frame[date_column], errors="raise").dt.date,
            "close": pd.to_numeric(frame[actual_close_column], errors="raise"),
        }
    ).sort_values("date")
    if loaded["date"].duplicated().any():
        raise ValueError(f"Data file for {symbol} contains duplicate dates: {data_path}")

    loaded["daily_return"] = loaded["close"].pct_change()
    return symbol, loaded


def _parse_data_spec(data_spec: str) -> tuple[str, str]:
    if "=" not in data_spec:
        raise ValueError("--data values must use SYMBOL=CSV_PATH")
    symbol, path = data_spec.split("=", 1)
    symbol = symbol.strip().upper()
    path = path.strip()
    if not symbol or not path:
        raise ValueError("--data values must use SYMBOL=CSV_PATH")
    return symbol, path


def _find_column(columns: Iterable[object], requested_name: str) -> str | None:
    requested = requested_name.lower()
    for column in columns:
        if str(column).lower() == requested:
            return str(column)
    return None


def _event_returns_for_symbol(
    symbol: str,
    frame: pd.DataFrame,
    calendar_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    indexed = frame.set_index("date", drop=False)
    available_dates = set(indexed.index)
    for event in calendar_rows:
        window_start = _parse_date(str(event["window_start"]), "window_start")
        event_date = _parse_date(str(event["event_date"]), "event_date")
        window_end = _parse_date(str(event["window_end"]), "window_end")
        if window_start not in available_dates or event_date not in available_dates or window_end not in available_dates:
            continue

        window = frame[(frame["date"] >= window_start) & (frame["date"] <= window_end)]
        pre_event = frame[(frame["date"] >= window_start) & (frame["date"] < event_date)]
        event_day = frame[frame["date"] == event_date]
        post_event = frame[(frame["date"] > event_date) & (frame["date"] <= window_end)]
        rows.append(
            {
                "symbol": symbol,
                "event_id": str(event["event_id"]),
                "event_type": str(event["event_type"]),
                "event_date": event_date.isoformat(),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "window_trading_days": str(len(window)),
                "window_return": _format_float(_compound_returns(window["daily_return"].dropna())),
                "pre_event_return": _format_float(_compound_returns(pre_event["daily_return"].dropna())),
                "event_day_return": _format_float(_compound_returns(event_day["daily_return"].dropna())),
                "post_event_return": _format_float(_compound_returns(post_event["daily_return"].dropna())),
            }
        )
    return rows


def _summarize_symbol_event_rows(
    symbol: str,
    event_rows: list[dict[str, str]],
    frame: pd.DataFrame,
) -> list[dict[str, Any]]:
    event_dates: set[date] = set()
    for row in event_rows:
        start = _parse_date(row["window_start"], "window_start")
        end = _parse_date(row["window_end"], "window_end")
        event_dates.update(frame[(frame["date"] >= start) & (frame["date"] <= end)]["date"].tolist())

    non_event = frame[~frame["date"].isin(event_dates)]["daily_return"].dropna()
    non_event_mean = float(non_event.mean()) if len(non_event) else math.nan
    summary_rows: list[dict[str, Any]] = []
    quarter_end_dates = {row["event_date"] for row in event_rows if row["event_type"] == "quarter_end"}
    event_views = sorted(
        {
            view
            for row in event_rows
            for view in _summary_views_for_event_row(row, quarter_end_dates)
        }
    )
    for event_view in event_views:
        typed = [
            row
            for row in event_rows
            if event_view in _summary_views_for_event_row(row, quarter_end_dates)
        ]
        window_returns = [float(row["window_return"]) for row in typed]
        pre_returns = [float(row["pre_event_return"]) for row in typed]
        event_day_returns = [float(row["event_day_return"]) for row in typed]
        post_returns = [float(row["post_event_return"]) for row in typed]
        summary_rows.append(
            {
                "symbol": symbol,
                "event_type": event_view,
                "event_count": len(typed),
                "mean_window_return": _mean(window_returns),
                "median_window_return": _median(window_returns),
                "positive_window_rate": _positive_rate(window_returns),
                "mean_pre_event_return": _mean(pre_returns),
                "mean_event_day_return": _mean(event_day_returns),
                "mean_post_event_return": _mean(post_returns),
                "non_event_mean_daily_return": non_event_mean,
                "interpretation": _event_study_interpretation(typed, window_returns, non_event_mean),
            }
        )
    return summary_rows


def _summary_views_for_event_row(row: dict[str, str], quarter_end_dates: set[str]) -> list[str]:
    event_type = row["event_type"]
    views = [event_type]
    if event_type == "month_end" and row["event_date"] not in quarter_end_dates:
        views.append("month_end_excluding_quarter_end")
    return views


def _compound_returns(returns: Iterable[float]) -> float:
    cumulative = 1.0
    for value in returns:
        if pd.isna(value):
            continue
        cumulative *= 1.0 + float(value)
    return cumulative - 1.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else math.nan


def _median(values: list[float]) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _positive_rate(values: list[float]) -> float:
    return sum(1 for value in values if value > 0) / len(values) if values else math.nan


def _event_study_interpretation(
    event_rows: list[dict[str, str]],
    window_returns: list[float],
    non_event_mean_daily_return: float,
) -> str:
    if not window_returns or math.isnan(non_event_mean_daily_return):
        return "insufficient_data"
    mean_window_days = _mean([float(row["window_trading_days"]) for row in event_rows])
    event_mean_daily_proxy = _mean(window_returns) / mean_window_days
    difference = event_mean_daily_proxy - non_event_mean_daily_return
    if abs(difference) < 0.0001:
        return "similar_to_non_event_days"
    if difference > 0:
        return "event_windows_higher_than_non_event_days"
    return "event_windows_lower_than_non_event_days"


def _write_dict_csv(path: Path, rows: list[dict[str, str]], *, fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _render_event_study_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Event Study Report",
        "",
        "Role: No-trade mechanism diagnostic.",
        "",
        "This report joins a prebuilt event calendar to close-to-close returns. It does not simulate entries, exits, costs, sizing, or benchmark-relative strategy performance.",
        "",
        f"- Calendar: `{payload['calendar_path']}`",
        f"- Symbols: {', '.join(payload['symbols'])}",
        f"- Events in calendar: {payload['event_count']}",
        "",
        "## Method",
        "",
        f"- Return definition: {payload['method']['return_definition']}",
        f"- Event selection: {payload['method']['event_selection']}",
        f"- Non-event comparison: {payload['method']['non_event_comparison']}",
        "",
        "## Summary",
        "",
        "| Symbol | Event View | Events | Mean Window Return | Median Window Return | Positive Rate | Mean Pre | Mean Event Day | Mean Post | Non-Event Mean Daily | Interpretation |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["summary"]:
        lines.append(
            "| {symbol} | {event_type} | {event_count} | {mean_window_return} | {median_window_return} | {positive_window_rate} | {mean_pre_event_return} | {mean_event_day_return} | {mean_post_event_return} | {non_event_mean_daily_return} | {interpretation} |".format(
                symbol=row["symbol"],
                event_type=row["event_type"],
                event_count=row["event_count"],
                mean_window_return=_format_percent(row["mean_window_return"]),
                median_window_return=_format_percent(row["median_window_return"]),
                positive_window_rate=_format_percent(row["positive_window_rate"]),
                mean_pre_event_return=_format_percent(row["mean_pre_event_return"]),
                mean_event_day_return=_format_percent(row["mean_event_day_return"]),
                mean_post_event_return=_format_percent(row["mean_post_event_return"]),
                non_event_mean_daily_return=_format_percent(row["non_event_mean_daily_return"]),
                interpretation=row["interpretation"],
            )
        )
    lines.extend(
        [
            "",
            "## Read This Carefully",
            "",
            "- A higher event-window average is only a clue, not a trading edge.",
            "- `month_end_excluding_quarter_end` is a derived summary view; raw event rows are unchanged.",
            "- Quarter-end rows overlap month-end rows, so they are related views of the same calendar, not independent samples.",
            "- Any strategy built from this must still define success criteria before execution.",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_float(value: float) -> str:
    return f"{value:.10f}"


def _format_percent(value: float) -> str:
    if value is None or math.isnan(float(value)):
        return "n/a"
    return f"{float(value) * 100:.2f}%"


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
