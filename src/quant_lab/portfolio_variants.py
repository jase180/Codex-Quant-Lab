"""Generate auditable portfolio_plan.v1 variants from a base portfolio spec."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .portfolio_spec import PortfolioSpec, load_portfolio_spec, parse_portfolio_spec

_WEIGHT_TOLERANCE = 1e-9


@dataclass(frozen=True)
class PortfolioVariantWriteResult:
    portfolio_id: str
    path: str


def parse_weight_set(raw_weight_set: str, expected_symbols: Iterable[str]) -> dict[str, float]:
    """Parse `SYMBOL=weight,SYMBOL=weight` text into a normalized weight map."""

    expected = [symbol.upper() for symbol in expected_symbols]
    weights: dict[str, float] = {}
    for raw_part in raw_weight_set.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"Invalid weight entry '{part}'. Use SYMBOL=weight.")
        raw_symbol, raw_weight = part.split("=", 1)
        symbol = raw_symbol.strip().upper()
        if symbol not in expected:
            raise ValueError(f"Weight set includes unknown symbol '{symbol}'. Expected {expected}.")
        if symbol in weights:
            raise ValueError(f"Weight set repeats symbol '{symbol}'.")
        try:
            weight = float(raw_weight)
        except ValueError as exc:
            raise ValueError(f"Weight for {symbol} must be numeric.") from exc
        if weight <= 0.0 or weight > 1.0:
            raise ValueError(f"Weight for {symbol} must be greater than 0 and no more than 1.")
        weights[symbol] = weight

    missing = [symbol for symbol in expected if symbol not in weights]
    if missing:
        raise ValueError(f"Weight set is missing symbols: {missing}.")
    extra = sorted(set(weights) - set(expected))
    if extra:
        raise ValueError(f"Weight set includes unsupported symbols: {extra}.")
    total_weight = sum(weights.values())
    if abs(total_weight - 1.0) > _WEIGHT_TOLERANCE:
        raise ValueError(f"Weights must sum to 1.0; got {total_weight:.12g}.")
    return weights


def build_portfolio_variant_payload(base: PortfolioSpec, weights: dict[str, float]) -> dict:
    """Build and validate one portfolio_plan.v1 payload using a base spec."""

    weight_suffix = _weight_suffix(weights, [symbol.symbol for symbol in base.symbols])
    payload = {
        "schema_version": "portfolio_plan.v1",
        "portfolio_id": f"{base.portfolio_id}_{weight_suffix}",
        "name": f"{base.name} {weight_suffix.replace('_', ' ')}",
        "description": f"Weight variant generated from {base.portfolio_id}.",
        "symbols": [
            {
                "symbol": symbol.symbol,
                "data": symbol.data,
                "target_weight": weights[symbol.symbol],
            }
            for symbol in base.symbols
        ],
        "rebalance": {"frequency": base.rebalance.frequency},
        "benchmark": {
            "symbol": base.benchmark.symbol,
            "data": base.benchmark.data,
        },
    }
    parse_portfolio_spec(payload)
    return payload


def write_portfolio_variants(
    *,
    portfolio_path: str | Path,
    raw_weight_sets: Iterable[str],
    output_dir: str | Path,
    force: bool = False,
) -> list[PortfolioVariantWriteResult]:
    base = load_portfolio_spec(portfolio_path)
    raw_weight_list = list(raw_weight_sets)
    if not raw_weight_list:
        raise ValueError("portfolio-variants requires at least one --weights value.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    results: list[PortfolioVariantWriteResult] = []
    for raw_weight_set in raw_weight_list:
        weights = parse_weight_set(raw_weight_set, [symbol.symbol for symbol in base.symbols])
        payload = build_portfolio_variant_payload(base, weights)
        path = output_path / f"{payload['portfolio_id']}.json"
        if path.exists() and not force:
            raise FileExistsError(f"Portfolio variant already exists: {path}. Use --force to overwrite it.")
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        results.append(PortfolioVariantWriteResult(portfolio_id=payload["portfolio_id"], path=str(path)))
    return results


def _weight_suffix(weights: dict[str, float], ordered_symbols: list[str]) -> str:
    parts = []
    for symbol in ordered_symbols:
        # Portfolio ids must match ^[a-z][a-z0-9_]*$, so use lowercase symbols
        # and integer basis points instead of decimal punctuation.
        basis_points = int(round(weights[symbol] * 10_000))
        parts.append(f"{symbol.lower()}_{basis_points:04d}bp")
    return "_".join(parts)
