"""Data-quality summaries for research artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
PRICE_COLUMNS = ("open", "high", "low", "close")
LARGE_GAP_THRESHOLD = 0.20
CALENDAR_GAP_DAYS = 5
SEVERITY_ORDER = {"none": 0, "info": 1, "warning": 2, "critical": 3}


@dataclass(frozen=True)
class DataQualityReport:
    row_count: int
    start: str | None
    end: str | None
    duplicate_dates: int
    missing_ohlcv_values: int
    zero_volume_rows: int
    non_positive_price_rows: int
    large_gap_warnings: list[str] = field(default_factory=list)
    calendar_gap_warnings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    findings: list[dict[str, str]] = field(default_factory=list)
    worst_severity: str = "none"

    def to_dict(self) -> dict:
        return asdict(self)


def build_data_quality_report(data: pd.DataFrame) -> DataQualityReport:
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")

    row_count = int(len(data))
    date_series = _date_series(data)
    start = _date_value(date_series.min()) if not date_series.empty else None
    end = _date_value(date_series.max()) if not date_series.empty else None
    duplicate_dates = int(date_series.duplicated().sum()) if not date_series.empty else 0

    present_ohlcv = [column for column in OHLCV_COLUMNS if column in data.columns]
    missing_ohlcv_values = int(data[present_ohlcv].isna().sum().sum()) if present_ohlcv else 0

    volume = pd.to_numeric(data["volume"], errors="coerce") if "volume" in data.columns else pd.Series(dtype="float64")
    zero_volume_rows = int((volume == 0).sum()) if not volume.empty else 0

    present_prices = [column for column in PRICE_COLUMNS if column in data.columns]
    price_frame = data[present_prices].apply(pd.to_numeric, errors="coerce") if present_prices else pd.DataFrame()
    non_positive_price_rows = int((price_frame <= 0).any(axis=1).sum()) if not price_frame.empty else 0

    large_gap_warnings = _large_gap_warnings(data, date_series)
    calendar_gap_warnings = _calendar_gap_warnings(date_series)
    findings = _summary_findings(
        duplicate_dates=duplicate_dates,
        missing_ohlcv_values=missing_ohlcv_values,
        zero_volume_rows=zero_volume_rows,
        non_positive_price_rows=non_positive_price_rows,
        large_gap_warnings=large_gap_warnings,
        calendar_gap_warnings=calendar_gap_warnings,
    )
    warnings = [finding["message"] for finding in findings if finding["severity"] in {"warning", "critical"}]
    worst_severity = _worst_severity(findings)

    return DataQualityReport(
        row_count=row_count,
        start=start,
        end=end,
        duplicate_dates=duplicate_dates,
        missing_ohlcv_values=missing_ohlcv_values,
        zero_volume_rows=zero_volume_rows,
        non_positive_price_rows=non_positive_price_rows,
        large_gap_warnings=large_gap_warnings,
        calendar_gap_warnings=calendar_gap_warnings,
        warnings=warnings,
        findings=findings,
        worst_severity=worst_severity,
    )


def save_data_quality_report(report: DataQualityReport, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "data_quality.json"
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(report_path)


def data_quality_report_section(report: DataQualityReport) -> str:
    finding_lines = (
        "\n".join(f"- {finding['severity']}: {finding['message']}" for finding in report.findings)
        if report.findings
        else "- None"
    )
    return f"""## Data Quality

| Check | Value |
| --- | ---: |
| Worst Severity | {report.worst_severity} |
| Rows | {report.row_count} |
| Start | {report.start or "N/A"} |
| End | {report.end or "N/A"} |
| Duplicate Dates | {report.duplicate_dates} |
| Missing OHLCV Values | {report.missing_ohlcv_values} |
| Zero Volume Rows | {report.zero_volume_rows} |
| Non-Positive Price Rows | {report.non_positive_price_rows} |
| Large Gap Warnings | {len(report.large_gap_warnings)} |
| Calendar Gap Warnings | {len(report.calendar_gap_warnings)} |

Findings:

{finding_lines}
"""


def append_data_quality_section(report_markdown: str, data_quality: DataQualityReport) -> str:
    return report_markdown.rstrip() + "\n\n" + data_quality_report_section(data_quality)


def _date_series(data: pd.DataFrame) -> pd.Series:
    if "date" not in data.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(data["date"], errors="coerce")


def _date_value(value: pd.Timestamp) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def _large_gap_warnings(data: pd.DataFrame, date_series: pd.Series) -> list[str]:
    if "close" not in data.columns or date_series.empty:
        return []

    closes = pd.to_numeric(data["close"], errors="coerce")
    warnings: list[str] = []
    for index in range(1, len(closes)):
        previous_close = closes.iloc[index - 1]
        current_close = closes.iloc[index]
        if pd.isna(previous_close) or pd.isna(current_close) or previous_close <= 0:
            continue
        gap = (current_close / previous_close) - 1.0
        if abs(gap) >= LARGE_GAP_THRESHOLD:
            warnings.append(
                f"{_date_value(date_series.iloc[index]) or 'unknown date'} close changed {gap:.2%} from prior row"
            )
    return warnings


def _calendar_gap_warnings(date_series: pd.Series) -> list[str]:
    if date_series.empty:
        return []

    sorted_dates = date_series.dropna().sort_values().reset_index(drop=True)
    warnings: list[str] = []
    for previous, current in zip(sorted_dates, sorted_dates[1:]):
        gap_days = int((current - previous).days)
        if gap_days > CALENDAR_GAP_DAYS:
            warnings.append(
                f"{previous.date().isoformat()} to {current.date().isoformat()} spans {gap_days} calendar days"
            )
    return warnings


def _summary_findings(
    *,
    duplicate_dates: int,
    missing_ohlcv_values: int,
    zero_volume_rows: int,
    non_positive_price_rows: int,
    large_gap_warnings: list[str],
    calendar_gap_warnings: list[str],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if duplicate_dates:
        findings.append(_finding("warning", f"{duplicate_dates} duplicate date rows found."))
    if missing_ohlcv_values:
        findings.append(_finding("warning", f"{missing_ohlcv_values} missing OHLCV values found."))
    if zero_volume_rows:
        findings.append(_finding("info", f"{zero_volume_rows} zero-volume rows found."))
    if non_positive_price_rows:
        findings.append(_finding("critical", f"{non_positive_price_rows} rows contain non-positive prices."))
    if large_gap_warnings:
        findings.append(_finding("warning", f"{len(large_gap_warnings)} large close-to-close gaps found."))
    if calendar_gap_warnings:
        findings.append(_finding("info", f"{len(calendar_gap_warnings)} large calendar gaps found."))
    return findings


def _finding(severity: str, message: str) -> dict[str, str]:
    return {"severity": severity, "message": message}


def _worst_severity(findings: list[dict[str, str]]) -> str:
    if not findings:
        return "none"
    return max((finding["severity"] for finding in findings), key=lambda severity: SEVERITY_ORDER[severity])
