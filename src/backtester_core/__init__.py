"""Backtester core package."""

from .engine import BacktestEngine, BacktestResult
from .execution import ExecutionModel, TransactionCostModel
from .portfolio import Portfolio, PortfolioSnapshot, Trade
from .strategy import Strategy

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "ExecutionModel",
    "Portfolio",
    "PortfolioSnapshot",
    "Strategy",
    "TransactionCostModel",
    "Trade",
]

try:
    from .reporting import (
        build_run_report,
        equity_curve_from_result,
        save_run_report_artifacts,
        summarize_run_metrics,
    )
except ModuleNotFoundError:
    # Keep the core importable even if optional reporting dependencies are unavailable.
    pass
else:
    __all__.extend(
        [
            "build_run_report",
            "equity_curve_from_result",
            "save_run_report_artifacts",
            "summarize_run_metrics",
        ]
    )
