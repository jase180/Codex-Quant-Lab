"""Shared helpers for generated portfolio_plan.v1 files."""

from __future__ import annotations

import json
from pathlib import Path

ALLOWED_REBALANCE_FREQUENCIES = ("none", "monthly", "quarterly", "annually")


def validate_rebalance_frequency(frequency: str) -> str:
    normalized = str(frequency).strip().lower()
    if normalized not in ALLOWED_REBALANCE_FREQUENCIES:
        raise ValueError(
            f"Unsupported rebalance frequency '{frequency}'. "
            f"Expected one of {list(ALLOWED_REBALANCE_FREQUENCIES)}."
        )
    return normalized


def weight_suffix(weights: dict[str, float], ordered_symbols: list[str]) -> str:
    parts = []
    for symbol in ordered_symbols:
        # Portfolio ids must match ^[a-z][a-z0-9_]*$, so use lowercase symbols
        # and integer basis points instead of decimal punctuation.
        basis_points = int(round(weights[symbol] * 10_000))
        parts.append(f"{symbol.lower()}_{basis_points:04d}bp")
    return "_".join(parts)


def write_portfolio_json(path: str | Path, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
