"""Shared helpers for local trust-report commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_CRITICAL_WARNING_FRAGMENTS = (
    "input file differs",
    "data file missing",
    "metadata missing data path",
    "data quality severity is critical",
    "quality severity is critical",
)


def classify_trust_warnings(
    warnings: list[str],
    *,
    critical_fragments: tuple[str, ...] = DEFAULT_CRITICAL_WARNING_FRAGMENTS,
) -> str:
    """Return the highest warning level for a trust report.

    Missing provenance is useful friction but not a disaster. Missing or changed
    input files are more serious because the saved result can no longer be
    reproduced from the local data described in metadata.
    """

    if not warnings:
        return "none"
    if any(any(fragment in warning for fragment in critical_fragments) for warning in warnings):
        return "critical"
    if any("warning" in warning or "missing" in warning for warning in warnings):
        return "warning"
    return "info"


def verification_check(expected: object, actual: object) -> dict[str, object]:
    return {
        "expected": expected,
        "actual": actual,
        "status": "match" if expected == actual else "mismatch",
    }


def range_value(start: object, end: object) -> str:
    return f"{start} to {end}"


def metadata_date(value: pd.Timestamp) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def plain(value: object) -> str:
    if value is None:
        return "-"
    return str(value)
