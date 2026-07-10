"""Typed row models for sweep summary CSV outputs."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass


SummaryValue = str | int | float | None


SWEEP_SUMMARY_FIELDNAMES = [
    "run_id",
    "strategy_id",
    "params",
    "final_equity",
    "total_return",
    "cagr",
    "sharpe_ratio",
    "max_drawdown",
    "trade_count",
    "sizing",
    "quantity",
    "allocation",
    "cost_preset",
    "commission_fixed",
    "commission_rate",
    "slippage_bps",
    "benchmark_name",
    "benchmark_final_equity",
    "benchmark_total_return",
    "benchmark_cagr",
    "benchmark_sharpe_ratio",
    "benchmark_max_drawdown",
    "excess_total_return",
    "output_dir",
]


WALK_FORWARD_SUMMARY_FIELDNAMES = [
    "window_id",
    "train_start",
    "train_end",
    "test_start",
    "test_end",
    "selected_train_run_id",
    "selected_train_params",
    "selected_train_total_return",
    "selected_train_sharpe_ratio",
    "test_run_id",
    "test_total_return",
    "test_excess_total_return",
    "test_sharpe_ratio",
    "test_trade_count",
    "train_summary_path",
    "test_summary_path",
    "test_output_dir",
]


class SummaryRowMapping(Mapping[str, SummaryValue]):
    """Mapping behavior lets existing report formatters read rows by column name."""

    def to_dict(self) -> dict[str, SummaryValue]:
        raise NotImplementedError

    def __getitem__(self, key: str) -> SummaryValue:
        return self.to_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())


@dataclass(frozen=True)
class SweepSummaryRow(SummaryRowMapping):
    run_id: str
    strategy_id: str
    params: str
    final_equity: float
    total_return: float
    cagr: float | None
    sharpe_ratio: float | None
    max_drawdown: float
    trade_count: int
    sizing: str
    quantity: float
    allocation: float
    cost_preset: str
    commission_fixed: float
    commission_rate: float
    slippage_bps: float
    benchmark_name: str
    benchmark_final_equity: float
    benchmark_total_return: float
    benchmark_cagr: float | None
    benchmark_sharpe_ratio: float | None
    benchmark_max_drawdown: float
    excess_total_return: float
    output_dir: str

    def to_dict(self) -> dict[str, SummaryValue]:
        return {
            "run_id": self.run_id,
            "strategy_id": self.strategy_id,
            "params": self.params,
            "final_equity": self.final_equity,
            "total_return": self.total_return,
            "cagr": self.cagr,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "trade_count": self.trade_count,
            "sizing": self.sizing,
            "quantity": self.quantity,
            "allocation": self.allocation,
            "cost_preset": self.cost_preset,
            "commission_fixed": self.commission_fixed,
            "commission_rate": self.commission_rate,
            "slippage_bps": self.slippage_bps,
            "benchmark_name": self.benchmark_name,
            "benchmark_final_equity": self.benchmark_final_equity,
            "benchmark_total_return": self.benchmark_total_return,
            "benchmark_cagr": self.benchmark_cagr,
            "benchmark_sharpe_ratio": self.benchmark_sharpe_ratio,
            "benchmark_max_drawdown": self.benchmark_max_drawdown,
            "excess_total_return": self.excess_total_return,
            "output_dir": self.output_dir,
        }


@dataclass(frozen=True)
class WalkForwardSummaryRow(SummaryRowMapping):
    window_id: str
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    selected_train_run_id: str
    selected_train_params: str
    selected_train_total_return: float
    selected_train_sharpe_ratio: float | None
    test_run_id: str
    test_total_return: float
    test_excess_total_return: float
    test_sharpe_ratio: float | None
    test_trade_count: int
    train_summary_path: str
    test_summary_path: str
    test_output_dir: str

    def to_dict(self) -> dict[str, SummaryValue]:
        return {
            "window_id": self.window_id,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "selected_train_run_id": self.selected_train_run_id,
            "selected_train_params": self.selected_train_params,
            "selected_train_total_return": self.selected_train_total_return,
            "selected_train_sharpe_ratio": self.selected_train_sharpe_ratio,
            "test_run_id": self.test_run_id,
            "test_total_return": self.test_total_return,
            "test_excess_total_return": self.test_excess_total_return,
            "test_sharpe_ratio": self.test_sharpe_ratio,
            "test_trade_count": self.test_trade_count,
            "train_summary_path": self.train_summary_path,
            "test_summary_path": self.test_summary_path,
            "test_output_dir": self.test_output_dir,
        }
