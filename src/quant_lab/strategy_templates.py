"""Reusable starter strategies for the v1 JSON schema."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .strategy_schema import parse_strategy

TEMPLATE_NAMES = (
    "sma-crossover",
    "ema-trend-follow",
    "rsi-reversion",
)


def available_strategy_templates() -> tuple[str, ...]:
    return TEMPLATE_NAMES


def build_strategy_template(
    template_name: str,
    *,
    symbol: str,
    strategy_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Return a validated v1 strategy JSON payload from a named template."""

    if template_name == "sma-crossover":
        payload = _sma_crossover_template(symbol)
    elif template_name == "ema-trend-follow":
        payload = _ema_trend_follow_template(symbol)
    elif template_name == "rsi-reversion":
        payload = _rsi_reversion_template(symbol)
    else:
        raise ValueError(f"Unknown strategy template: {template_name}")

    payload = copy.deepcopy(payload)
    if strategy_id is not None:
        payload["strategy_id"] = strategy_id
    if name is not None:
        payload["name"] = name

    # Validate before returning so template callers cannot accidentally write a
    # file that the rest of the lab rejects later.
    parse_strategy(payload)
    return payload


def write_strategy_template(
    payload: dict[str, Any],
    output_path: str | Path,
    *,
    force: bool = False,
) -> str:
    path = Path(output_path)
    if path.exists() and not force:
        raise FileExistsError(f"Strategy file already exists: {path}. Use --force to overwrite it.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def _sma_crossover_template(symbol: str) -> dict[str, Any]:
    return {
        "schema_version": "v1",
        "strategy_id": "sma_crossover",
        "name": "Simple SMA Crossover",
        "description": "Enter on a fast SMA crossing above a slow SMA and exit on the opposite crossover.",
        "strategy_type": "rule_based",
        "position_mode": "long_only",
        "market": {"symbol": symbol.upper(), "timeframe": "1d"},
        "indicators": [
            {"id": "sma_20", "kind": "sma", "inputs": {"source": "close", "length": 20}},
            {"id": "sma_50", "kind": "sma", "inputs": {"source": "close", "length": 50}},
        ],
        "entry": {
            "when": "all",
            "conditions": [
                {
                    "left": {"indicator": "sma_20"},
                    "operator": "crosses_above",
                    "right": {"indicator": "sma_50"},
                }
            ],
        },
        "exit": {
            "when": "all",
            "conditions": [
                {
                    "left": {"indicator": "sma_20"},
                    "operator": "crosses_below",
                    "right": {"indicator": "sma_50"},
                }
            ],
        },
    }


def _ema_trend_follow_template(symbol: str) -> dict[str, Any]:
    return {
        "schema_version": "v1",
        "strategy_id": "ema_trend_follow",
        "name": "EMA Trend Follow",
        "description": (
            "Enter when price is above the trend EMA and RSI confirms strength; "
            "exit on either momentum weakness or price trend failure."
        ),
        "strategy_type": "rule_based",
        "position_mode": "long_only",
        "market": {"symbol": symbol.upper(), "timeframe": "1d"},
        "indicators": [
            {"id": "ema_50", "kind": "ema", "inputs": {"source": "close", "length": 50}},
            {"id": "rsi_14", "kind": "rsi", "inputs": {"source": "close", "length": 14}},
        ],
        "entry": {
            "when": "all",
            "conditions": [
                {"left": {"price": "close"}, "operator": "gt", "right": {"indicator": "ema_50"}},
                {"left": {"indicator": "rsi_14"}, "operator": "gt", "right": {"value": 55}},
            ],
        },
        "exit": {
            "when": "any",
            "conditions": [
                {"left": {"price": "close"}, "operator": "lt", "right": {"indicator": "ema_50"}},
                {"left": {"indicator": "rsi_14"}, "operator": "lt", "right": {"value": 45}},
            ],
        },
    }


def _rsi_reversion_template(symbol: str) -> dict[str, Any]:
    return {
        "schema_version": "v1",
        "strategy_id": "rsi_reversion",
        "name": "RSI Mean Reversion",
        "description": "Enter when RSI is oversold and exit when momentum normalizes.",
        "strategy_type": "rule_based",
        "position_mode": "long_only",
        "market": {"symbol": symbol.upper(), "timeframe": "1d"},
        "indicators": [
            {"id": "rsi_14", "kind": "rsi", "inputs": {"source": "close", "length": 14}},
        ],
        "entry": {
            "when": "all",
            "conditions": [
                {"left": {"indicator": "rsi_14"}, "operator": "lt", "right": {"value": 30}},
            ],
        },
        "exit": {
            "when": "all",
            "conditions": [
                {"left": {"indicator": "rsi_14"}, "operator": "gte", "right": {"value": 55}},
            ],
        },
    }
