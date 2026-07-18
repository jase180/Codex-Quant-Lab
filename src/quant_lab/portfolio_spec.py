"""Strict schema for simple multi-asset portfolio research plans."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_ALLOWED_REBALANCE_FREQUENCIES = {"none", "monthly", "quarterly", "annually"}
_WEIGHT_TOLERANCE = 1e-9


class PortfolioSpecError(ValueError):
    """Raised when a portfolio document violates the portfolio_plan.v1 schema."""


@dataclass(frozen=True)
class PortfolioSymbolSpec:
    symbol: str
    data: str
    target_weight: float


@dataclass(frozen=True)
class RebalanceSpec:
    frequency: Literal["none", "monthly", "quarterly", "annually"]


@dataclass(frozen=True)
class PortfolioBenchmarkSpec:
    symbol: str
    data: str


@dataclass(frozen=True)
class PortfolioSpec:
    schema_version: Literal["portfolio_plan.v1"]
    portfolio_id: str
    name: str
    description: str
    symbols: list[PortfolioSymbolSpec]
    rebalance: RebalanceSpec
    benchmark: PortfolioBenchmarkSpec
    source_path: str | None = None


def load_portfolio_spec(path: str | Path) -> PortfolioSpec:
    """Load and validate a portfolio spec from a JSON file."""

    spec_path = Path(path)
    if spec_path.suffix.lower() != ".json":
        raise PortfolioSpecError(
            f"Unsupported portfolio file format '{spec_path.suffix}'. "
            "portfolio_plan.v1 accepts JSON files."
        )

    try:
        payload = json.loads(spec_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PortfolioSpecError(f"Portfolio file does not exist: {spec_path}") from exc
    except json.JSONDecodeError as exc:
        raise PortfolioSpecError(
            f"Invalid JSON in portfolio file '{spec_path}': {exc.msg}"
        ) from exc

    parsed = parse_portfolio_spec(payload)
    return PortfolioSpec(
        schema_version=parsed.schema_version,
        portfolio_id=parsed.portfolio_id,
        name=parsed.name,
        description=parsed.description,
        symbols=parsed.symbols,
        rebalance=parsed.rebalance,
        benchmark=parsed.benchmark,
        source_path=str(spec_path),
    )


def parse_portfolio_spec(payload: dict[str, Any]) -> PortfolioSpec:
    """Validate an in-memory portfolio document and convert it into Python objects."""

    if not isinstance(payload, dict):
        raise PortfolioSpecError("Portfolio document must be a JSON object.")

    schema_version = _require_literal(payload, "schema_version", {"portfolio_plan.v1"})
    portfolio_id = _require_identifier(payload, "portfolio_id")
    name = _require_non_empty_string(payload, "name")
    description = _require_non_empty_string(payload, "description")
    symbols = _parse_symbols(_require_list(payload, "symbols"))
    rebalance = _parse_rebalance(_require_mapping(payload, "rebalance"))
    benchmark = _parse_benchmark(_require_mapping(payload, "benchmark"))

    _reject_unknown_keys(
        payload,
        allowed={
            "schema_version",
            "portfolio_id",
            "name",
            "description",
            "symbols",
            "rebalance",
            "benchmark",
        },
        context="portfolio",
    )

    return PortfolioSpec(
        schema_version=schema_version,
        portfolio_id=portfolio_id,
        name=name,
        description=description,
        symbols=symbols,
        rebalance=rebalance,
        benchmark=benchmark,
    )


def _parse_symbols(payload: list[Any]) -> list[PortfolioSymbolSpec]:
    if len(payload) < 2:
        raise PortfolioSpecError(
            "symbols must contain at least two symbols for portfolio research."
        )

    symbols: list[PortfolioSymbolSpec] = []
    seen_symbols: set[str] = set()
    total_weight = 0.0

    for index, raw_symbol in enumerate(payload):
        context = f"symbols[{index}]"
        if not isinstance(raw_symbol, dict):
            raise PortfolioSpecError(f"{context} must be an object.")

        symbol = _require_non_empty_string(raw_symbol, "symbol", context).upper()
        if symbol in seen_symbols:
            raise PortfolioSpecError(f"Duplicate portfolio symbol '{symbol}'.")
        seen_symbols.add(symbol)

        data = _require_non_empty_string(raw_symbol, "data", context)
        target_weight = _require_weight(raw_symbol, "target_weight", context)
        total_weight += target_weight
        _reject_unknown_keys(raw_symbol, {"symbol", "data", "target_weight"}, context)
        symbols.append(
            PortfolioSymbolSpec(
                symbol=symbol,
                data=data,
                target_weight=target_weight,
            )
        )

    if abs(total_weight - 1.0) > _WEIGHT_TOLERANCE:
        raise PortfolioSpecError(
            f"symbols target weights must sum to 1.0; got {total_weight:.12g}."
        )

    return symbols


def _parse_rebalance(payload: dict[str, Any]) -> RebalanceSpec:
    frequency = _require_literal(
        payload,
        "frequency",
        _ALLOWED_REBALANCE_FREQUENCIES,
        "rebalance",
    )
    _reject_unknown_keys(payload, {"frequency"}, "rebalance")
    return RebalanceSpec(frequency=frequency)


def _parse_benchmark(payload: dict[str, Any]) -> PortfolioBenchmarkSpec:
    symbol = _require_non_empty_string(payload, "symbol", "benchmark").upper()
    data = _require_non_empty_string(payload, "data", "benchmark")
    _reject_unknown_keys(payload, {"symbol", "data"}, "benchmark")
    return PortfolioBenchmarkSpec(symbol=symbol, data=data)


def _require_mapping(payload: dict[str, Any], key: str, context: str = "portfolio") -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise PortfolioSpecError(f"{context}.{key} must be an object.")
    return value


def _require_list(payload: dict[str, Any], key: str, context: str = "portfolio") -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise PortfolioSpecError(f"{context}.{key} must be a list.")
    return value


def _require_non_empty_string(payload: dict[str, Any], key: str, context: str = "portfolio") -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PortfolioSpecError(f"{context}.{key} must be a non-empty string.")
    return value.strip()


def _require_identifier(payload: dict[str, Any], key: str, context: str = "portfolio") -> str:
    value = _require_non_empty_string(payload, key, context)
    if not _ID_PATTERN.match(value):
        raise PortfolioSpecError(
            f"{context}.{key} must match pattern '{_ID_PATTERN.pattern}'."
        )
    return value


def _require_literal(
    payload: dict[str, Any], key: str, allowed: set[str], context: str = "portfolio"
) -> str:
    value = payload.get(key)
    if value not in allowed:
        raise PortfolioSpecError(f"{context}.{key} must be one of {sorted(allowed)}.")
    return value


def _require_weight(payload: dict[str, Any], key: str, context: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PortfolioSpecError(f"{context}.{key} must be numeric.")

    weight = float(value)
    if weight <= 0.0 or weight > 1.0:
        raise PortfolioSpecError(
            f"{context}.{key} must be greater than 0 and no more than 1."
        )
    return weight


def _reject_unknown_keys(payload: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(payload.keys()) - allowed)
    if unknown:
        raise PortfolioSpecError(f"{context} contains unsupported fields: {unknown}.")
