"""Reusable starter portfolios for the portfolio_plan.v1 JSON schema."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .portfolio_spec import parse_portfolio_spec

TEMPLATE_NAMES = ("qqq-spy-60-40",)


def available_portfolio_templates() -> tuple[str, ...]:
    return TEMPLATE_NAMES


def build_portfolio_template(template_name: str) -> dict[str, Any]:
    """Return a validated portfolio_plan.v1 JSON payload from a named template."""

    if template_name == "qqq-spy-60-40":
        payload = _qqq_spy_60_40_template()
    else:
        raise ValueError(f"Unknown portfolio template: {template_name}")

    # Return a deep copy so callers can safely mutate the payload later without
    # changing the reusable template data in this module.
    payload = copy.deepcopy(payload)

    # Validate before returning so the generator cannot write a portfolio file
    # that the strict loader rejects during the actual portfolio-run command.
    parse_portfolio_spec(payload)
    return payload


def write_portfolio_template(
    payload: dict[str, Any],
    output_path: str | Path,
    *,
    force: bool = False,
) -> str:
    path = Path(output_path)
    if path.exists() and not force:
        raise FileExistsError(f"Portfolio file already exists: {path}. Use --force to overwrite it.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def _qqq_spy_60_40_template() -> dict[str, Any]:
    return {
        "schema_version": "portfolio_plan.v1",
        "portfolio_id": "qqq_spy_static_60_40",
        "name": "QQQ SPY Static 60/40",
        "description": "Static two-symbol allocation example for portfolio research.",
        "symbols": [
            {
                "symbol": "QQQ",
                "data": "../cache/QQQ_2015-01-01_2025-12-31.csv",
                "target_weight": 0.6,
            },
            {
                "symbol": "SPY",
                "data": "../cache/SPY_2015-01-01_2025-12-31.csv",
                "target_weight": 0.4,
            },
        ],
        "rebalance": {"frequency": "monthly"},
        "benchmark": {
            "symbol": "SPY",
            "data": "../cache/SPY_2015-01-01_2025-12-31.csv",
        },
    }
