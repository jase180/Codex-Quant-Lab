"""Structured metadata for portfolio research runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

from quant_lab.costs import CostAssumptions
from quant_lab.portfolio_benchmarks import PortfolioBenchmarkComparison
from quant_lab.portfolio_data import MultiAssetDataSet
from quant_lab.portfolio_spec import PortfolioSpec
from quant_lab.run_artifacts import current_git_commit
from quant_lab.run_metadata import fingerprint_file


@dataclass(frozen=True)
class PortfolioSpecMetadata:
    path: str | None
    file_sha256: str | None
    file_size_bytes: int | None
    modified_at_utc: str | None


@dataclass(frozen=True)
class PortfolioSymbolMetadata:
    symbol: str
    path: str
    target_weight: float
    row_count: int
    aligned_row_count: int
    dropped_rows: int
    start: str | None
    end: str | None
    file_sha256: str | None
    file_size_bytes: int | None
    modified_at_utc: str | None
    quality_severity: str | None


@dataclass(frozen=True)
class PortfolioCostMetadata:
    preset: str
    commission_fixed: float
    commission_rate: float
    slippage_bps: float


@dataclass(frozen=True)
class PortfolioEnvironmentMetadata:
    git_commit: str


@dataclass(frozen=True)
class PortfolioBenchmarkMetadata:
    symbol: str
    data_path: str
    file_sha256: str
    file_size_bytes: int
    modified_at_utc: str
    ending_equity: float
    total_return: float
    cagr: float | None
    sharpe_ratio: float | None
    max_drawdown: float
    excess_total_return: float


@dataclass(frozen=True)
class PortfolioMetadata:
    metadata_schema_version: str
    run_type: str
    created_at_utc: str
    command: list[str]
    portfolio_id: str
    name: str
    schema_version: str
    alignment_policy: str
    rebalance_frequency: str
    initial_cash: float
    benchmark_symbol: str
    benchmark_data: str
    portfolio_spec: PortfolioSpecMetadata
    symbols: list[PortfolioSymbolMetadata]
    costs: PortfolioCostMetadata
    environment: PortfolioEnvironmentMetadata
    benchmark: PortfolioBenchmarkMetadata | None = None
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def build_portfolio_metadata(
    *,
    portfolio: PortfolioSpec,
    dataset: MultiAssetDataSet,
    initial_cash: float,
    cost_assumptions: CostAssumptions,
    benchmark_comparison: PortfolioBenchmarkComparison | None = None,
    artifact_paths: Mapping[str, str],
    command: Sequence[str] = (),
) -> PortfolioMetadata:
    return PortfolioMetadata(
        metadata_schema_version="portfolio_metadata.v1",
        run_type="portfolio_run",
        created_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        command=[str(token) for token in command],
        portfolio_id=portfolio.portfolio_id,
        name=portfolio.name,
        schema_version=portfolio.schema_version,
        alignment_policy=dataset.alignment_policy,
        rebalance_frequency=portfolio.rebalance.frequency,
        initial_cash=float(initial_cash),
        benchmark_symbol=portfolio.benchmark.symbol,
        benchmark_data=portfolio.benchmark.data,
        portfolio_spec=_portfolio_spec_metadata(portfolio),
        symbols=_symbol_metadata(portfolio, dataset),
        costs=PortfolioCostMetadata(
            preset=cost_assumptions.preset,
            commission_fixed=float(cost_assumptions.commission_fixed),
            commission_rate=float(cost_assumptions.commission_rate),
            slippage_bps=float(cost_assumptions.slippage_bps),
        ),
        environment=PortfolioEnvironmentMetadata(git_commit=current_git_commit()),
        benchmark=_benchmark_metadata(benchmark_comparison),
        artifacts=dict(artifact_paths),
    )


def save_portfolio_metadata(metadata: PortfolioMetadata, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    metadata_path = destination / "portfolio_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(metadata_path)


def _portfolio_spec_metadata(portfolio: PortfolioSpec) -> PortfolioSpecMetadata:
    if portfolio.source_path is None:
        return PortfolioSpecMetadata(
            path=None,
            file_sha256=None,
            file_size_bytes=None,
            modified_at_utc=None,
        )

    fingerprint = fingerprint_file(portfolio.source_path)
    return PortfolioSpecMetadata(
        path=str(portfolio.source_path),
        file_sha256=str(fingerprint["file_sha256"]),
        file_size_bytes=int(fingerprint["file_size_bytes"]),
        modified_at_utc=str(fingerprint["modified_at_utc"]),
    )


def _symbol_metadata(
    portfolio: PortfolioSpec,
    dataset: MultiAssetDataSet,
) -> list[PortfolioSymbolMetadata]:
    metadata: list[PortfolioSymbolMetadata] = []
    for symbol in portfolio.symbols:
        quality = dataset.data_quality[symbol.symbol]
        fingerprint = dataset.fingerprints[symbol.symbol]
        metadata.append(
            PortfolioSymbolMetadata(
                symbol=symbol.symbol,
                path=symbol.data,
                target_weight=float(symbol.target_weight),
                row_count=quality.row_count,
                aligned_row_count=int(len(dataset.symbols[symbol.symbol])),
                dropped_rows=dataset.dropped_rows_by_symbol[symbol.symbol],
                start=quality.start,
                end=quality.end,
                file_sha256=str(fingerprint.get("file_sha256")),
                file_size_bytes=int(fingerprint["file_size_bytes"]),
                modified_at_utc=str(fingerprint.get("modified_at_utc")),
                quality_severity=quality.worst_severity,
            )
        )
    return metadata


def _benchmark_metadata(
    benchmark: PortfolioBenchmarkComparison | None,
) -> PortfolioBenchmarkMetadata | None:
    if benchmark is None:
        return None
    return PortfolioBenchmarkMetadata(
        symbol=benchmark.symbol,
        data_path=benchmark.data_path,
        file_sha256=benchmark.file_sha256,
        file_size_bytes=benchmark.file_size_bytes,
        modified_at_utc=benchmark.modified_at_utc,
        ending_equity=benchmark.metrics.ending_equity,
        total_return=benchmark.metrics.total_return,
        cagr=benchmark.metrics.cagr,
        sharpe_ratio=benchmark.metrics.sharpe_ratio,
        max_drawdown=benchmark.metrics.max_drawdown,
        excess_total_return=benchmark.excess_total_return,
    )
