"""Append-only research run registry."""

from __future__ import annotations

import json
import csv
import io
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

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
    experiment_id: str | None
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
    benchmark_name: str
    benchmark_total_return: float
    benchmark_max_drawdown: float
    excess_total_return: float
    sizing: str
    initial_cash: float
    quantity: float
    allocation: float
    cost_preset: str
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
        experiment_id=metadata.experiment_id,
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
        benchmark_name=metadata.benchmark.name,
        benchmark_total_return=benchmark_metrics.total_return,
        benchmark_max_drawdown=benchmark_metrics.max_drawdown,
        excess_total_return=excess_return,
        sizing=metadata.sizing.mode,
        initial_cash=metadata.sizing.initial_cash,
        quantity=metadata.sizing.quantity,
        allocation=metadata.sizing.allocation,
        cost_preset=metadata.costs.preset,
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


def load_research_index(index_path: str | Path) -> list[dict]:
    path = Path(index_path)
    if not path.exists():
        return []

    records: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in research index {path} on line {line_number}") from exc
    return records


INDEX_TABLE_COLUMNS = [
    ("created", "created_at_utc"),
    ("symbol", "symbol"),
    ("strategy", "strategy_id"),
    ("type", "run_type"),
    ("run", "run_id"),
    ("return", "total_return"),
    ("bench_name", "benchmark_name"),
    ("bench", "benchmark_total_return"),
    ("excess", "excess_total_return"),
    ("sharpe", "sharpe_ratio"),
    ("dd", "max_drawdown"),
    ("trades", "trade_count"),
    ("out", "output_dir"),
]


def filter_index_records(
    records: Iterable[dict],
    symbol: str | None = None,
    strategy_id: str | None = None,
    run_type: str | None = None,
    experiment_id: str | None = None,
) -> list[dict]:
    filtered = list(records)
    if symbol is not None:
        requested_symbol = symbol.upper()
        filtered = [record for record in filtered if str(record.get("symbol", "")).upper() == requested_symbol]
    if strategy_id is not None:
        filtered = [record for record in filtered if record.get("strategy_id") == strategy_id]
    if run_type is not None:
        filtered = [record for record in filtered if record.get("run_type") == run_type]
    if experiment_id is not None:
        filtered = [record for record in filtered if record.get("experiment_id") == experiment_id]
    return filtered


def sort_index_records(records: Iterable[dict], sort_key: str, descending: bool = True) -> list[dict]:
    sortable_records = list(records)
    return sorted(
        sortable_records,
        key=lambda record: _sortable_value(record, sort_key),
        reverse=descending,
    )


def format_index_table(records: list[dict]) -> str:
    table_rows = [
        [_format_table_value(record.get(field), field) for _, field in INDEX_TABLE_COLUMNS]
        for record in records
    ]
    header = [label for label, _ in INDEX_TABLE_COLUMNS]
    widths = [
        max(len(header[index]), *[len(row[index]) for row in table_rows]) if table_rows else len(header[index])
        for index in range(len(header))
    ]
    lines = [
        "  ".join(header[index].ljust(widths[index]) for index in range(len(header))),
        "  ".join("-" * widths[index] for index in range(len(header))),
    ]
    for row in table_rows:
        lines.append("  ".join(row[index].ljust(widths[index]) for index in range(len(row))))
    return "\n".join(lines)


def format_index_csv(records: list[dict]) -> str:
    output = io.StringIO()
    fieldnames = [label for label, _ in INDEX_TABLE_COLUMNS]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                label: _format_table_value(record.get(field), field)
                for label, field in INDEX_TABLE_COLUMNS
            }
        )
    return output.getvalue().rstrip("\n")


def _sortable_value(record: dict, sort_key: str) -> tuple[bool, object]:
    value = record.get(sort_key)
    return (value is None, value)


def _format_table_value(value: object, field: str) -> str:
    if value is None:
        return "-"
    if field == "created_at_utc":
        return str(value).replace("T", " ")[:19]
    if field in {"total_return", "benchmark_total_return", "excess_total_return", "max_drawdown"}:
        return f"{float(value):.2%}"
    if field == "sharpe_ratio":
        return f"{float(value):.2f}"
    return str(value)
