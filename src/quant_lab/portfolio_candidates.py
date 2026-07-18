"""Generate small static-weight portfolio candidate specs on a coarse grid."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .portfolio_generation import validate_rebalance_frequency, weight_suffix, write_portfolio_json
from .portfolio_spec import parse_portfolio_spec

_WEIGHT_TOLERANCE = 1e-9


@dataclass(frozen=True)
class PortfolioCandidateWriteResult:
    portfolio_id: str
    path: str


@dataclass(frozen=True)
class PortfolioCandidateGenerationResult:
    written: list[PortfolioCandidateWriteResult]
    skipped_count: int


def parse_candidate_symbols(raw_symbols: str) -> list[str]:
    symbols: list[str] = []
    for raw_symbol in raw_symbols.split(","):
        symbol = raw_symbol.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    if len(symbols) < 2:
        raise ValueError("portfolio-candidates requires at least two symbols.")
    return symbols


def generate_weight_grid(symbols: list[str], step: float) -> list[dict[str, float]]:
    if step <= 0.0 or step >= 1.0:
        raise ValueError("--step must be greater than 0 and less than 1.")
    units = round(1.0 / step)
    if abs(units * step - 1.0) > _WEIGHT_TOLERANCE:
        raise ValueError("--step must divide 1.0 evenly, such as 0.5, 0.25, or 0.1.")

    combinations: list[dict[str, float]] = []
    for unit_weights in _positive_integer_partitions(total=units, parts=len(symbols)):
        combinations.append(
            {
                symbol: round(unit_weight * step, 10)
                for symbol, unit_weight in zip(symbols, unit_weights)
            }
        )
    return combinations


def write_portfolio_candidates(
    *,
    symbols: str | Iterable[str],
    step: float,
    data_dir: str | Path,
    output_dir: str | Path,
    max_candidates: int = 100,
    rebalance_frequency: str = "monthly",
    benchmark_symbol: str | None = None,
    force: bool = False,
) -> PortfolioCandidateGenerationResult:
    parsed_symbols = parse_candidate_symbols(symbols if isinstance(symbols, str) else ",".join(symbols))
    if max_candidates < 1:
        raise ValueError("--max-candidates must be at least 1.")
    rebalance = validate_rebalance_frequency(rebalance_frequency)
    benchmark = (benchmark_symbol or parsed_symbols[0]).strip().upper()
    if benchmark not in parsed_symbols:
        raise ValueError("--benchmark-symbol must be one of the candidate symbols.")

    data_paths = {symbol: _resolve_symbol_data_path(Path(data_dir), symbol) for symbol in parsed_symbols}
    weight_grid = generate_weight_grid(parsed_symbols, step)
    if not weight_grid:
        raise ValueError("--step is too coarse to assign every symbol a positive weight.")
    selected_weights = weight_grid[:max_candidates]
    skipped_count = max(0, len(weight_grid) - len(selected_weights))

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    written: list[PortfolioCandidateWriteResult] = []
    base_id = "_".join(symbol.lower() for symbol in parsed_symbols)
    for weights in selected_weights:
        payload = _candidate_payload(
            symbols=parsed_symbols,
            weights=weights,
            data_paths=data_paths,
            base_id=base_id,
            rebalance_frequency=rebalance,
            benchmark_symbol=benchmark,
        )
        path = output_path / f"{payload['portfolio_id']}.json"
        if path.exists() and not force:
            raise FileExistsError(f"Portfolio candidate already exists: {path}. Use --force to overwrite it.")
        write_portfolio_json(path, payload)
        written.append(PortfolioCandidateWriteResult(portfolio_id=payload["portfolio_id"], path=str(path)))
    return PortfolioCandidateGenerationResult(written=written, skipped_count=skipped_count)


def _positive_integer_partitions(*, total: int, parts: int) -> list[tuple[int, ...]]:
    # The portfolio schema does not allow zero target weights, so each part of
    # the integer partition starts at 1 instead of 0.
    if parts == 1:
        return [(total,)] if total > 0 else []
    partitions: list[tuple[int, ...]] = []
    for first in range(1, total - parts + 2):
        for rest in _positive_integer_partitions(total=total - first, parts=parts - 1):
            partitions.append((first, *rest))
    return partitions


def _resolve_symbol_data_path(data_dir: Path, symbol: str) -> str:
    exact_path = data_dir / f"{symbol}.csv"
    if exact_path.exists():
        return str(exact_path)

    matches = sorted(data_dir.glob(f"{symbol}_*.csv"))
    if not matches:
        raise FileNotFoundError(f"No CSV data file found for {symbol} in {data_dir}.")
    if len(matches) > 1:
        raise ValueError(f"Multiple CSV data files found for {symbol} in {data_dir}; use one exact {symbol}.csv file.")
    return str(matches[0])


def _candidate_payload(
    *,
    symbols: list[str],
    weights: dict[str, float],
    data_paths: dict[str, str],
    base_id: str,
    rebalance_frequency: str,
    benchmark_symbol: str,
) -> dict:
    suffix = weight_suffix(weights, symbols)
    portfolio_id = f"{base_id}_{suffix}_rebalance_{rebalance_frequency}"
    payload = {
        "schema_version": "portfolio_plan.v1",
        "portfolio_id": portfolio_id,
        "name": f"{' '.join(symbols)} Candidate {suffix.replace('_', ' ')}",
        "description": "Static-weight candidate generated by portfolio-candidates.",
        "symbols": [
            {
                "symbol": symbol,
                "data": data_paths[symbol],
                "target_weight": weights[symbol],
            }
            for symbol in symbols
        ],
        "rebalance": {"frequency": rebalance_frequency},
        "benchmark": {
            "symbol": benchmark_symbol,
            "data": data_paths[benchmark_symbol],
        },
    }
    parse_portfolio_spec(payload)
    return payload
