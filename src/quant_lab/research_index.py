"""Append-only research run registry."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from metrics_reporting import RunMetrics

from .run_metadata import RunMetadata


@dataclass(frozen=True)
class RunIndexRecord:
    """One searchable row in the local research index.

    The index is intentionally flat even though `run_metadata.json` is nested.
    Flat JSONL records are easier to scan, filter, and later load into pandas.
    """

    index_schema_version: str
    created_at_utc: str
    run_type: str
    run_id: str | None
    strategy_id: str
    strategy_name: str
    symbol: str | None
    timeframe: str | None
    data_start: str | None
    data_end: str | None
    final_equity: float
    total_return: float
    cagr: float | None
    sharpe_ratio: float | None
    max_drawdown: float
    trade_count: int
    benchmark_total_return: float
    benchmark_max_drawdown: float
    excess_total_return: float
    sizing: str
    initial_cash: float
    quantity: float
    allocation: float
    commission_fixed: float
    commission_rate: float
    slippage_bps: float
    output_dir: str
    metadata_path: str
    git_commit: str

    def to_dict(self) -> dict:
        return asdict(self)


def build_run_index_record(
    *,
    metadata: RunMetadata,
    metrics: RunMetrics,
    benchmark_metrics: RunMetrics,
    excess_return: float,
    trade_count: int,
    output_dir: str | Path,
) -> RunIndexRecord:
    return RunIndexRecord(
        index_schema_version="research_index.v1",
        created_at_utc=metadata.created_at_utc,
        run_type=metadata.run_type,
        run_id=metadata.run_id,
        strategy_id=metadata.strategy.strategy_id,
        strategy_name=metadata.strategy.name,
        symbol=metadata.data.symbol,
        timeframe=metadata.data.timeframe,
        data_start=metadata.data.start,
        data_end=metadata.data.end,
        final_equity=metrics.ending_equity,
        total_return=metrics.total_return,
        cagr=metrics.cagr,
        sharpe_ratio=metrics.sharpe_ratio,
        max_drawdown=metrics.max_drawdown,
        trade_count=trade_count,
        benchmark_total_return=benchmark_metrics.total_return,
        benchmark_max_drawdown=benchmark_metrics.max_drawdown,
        excess_total_return=excess_return,
        sizing=metadata.sizing.mode,
        initial_cash=metadata.sizing.initial_cash,
        quantity=metadata.sizing.quantity,
        allocation=metadata.sizing.allocation,
        commission_fixed=metadata.costs.commission_fixed,
        commission_rate=metadata.costs.commission_rate,
        slippage_bps=metadata.costs.slippage_bps,
        output_dir=str(output_dir),
        metadata_path=metadata.artifacts["metadata"],
        git_commit=metadata.environment.git_commit,
    )


def append_research_index_record(record: RunIndexRecord, index_path: str | Path) -> str:
    destination = Path(index_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    return str(destination)
