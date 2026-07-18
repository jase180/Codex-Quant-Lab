"""Shared helpers for guided research plan modules."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


def utc_now_iso() -> str:
    """Return the project-standard UTC timestamp string.

    Python's `datetime.isoformat()` includes `+00:00` for UTC-aware datetimes.
    The rest of this project stores UTC timestamps with a trailing `Z`, so this
    helper keeps that convention in one place.
    """

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def normalize_recommended_steps(steps: Iterable[str]) -> list[str]:
    return [str(step).strip() for step in steps if str(step).strip()]


def validate_required_text_fields(fields: dict[str, object], *, context: str) -> None:
    for field_name, value in fields.items():
        if not str(value).strip():
            raise ValueError(f"{context} {field_name} must not be empty")


def write_json_payload(path: str | Path, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_optional_cost_overrides(
    command: list[str],
    commission_fixed: float | None,
    commission_rate: float | None,
    slippage_bps: float | None,
) -> None:
    if commission_fixed is not None:
        command.extend(["--commission-fixed", str(commission_fixed)])
    if commission_rate is not None:
        command.extend(["--commission-rate", str(commission_rate)])
    if slippage_bps is not None:
        command.extend(["--slippage-bps", str(slippage_bps)])
