"""Research warning summaries for weak or fragile backtest evidence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from metrics_reporting import RunMetrics

SHORT_SAMPLE_OBSERVATIONS = 252
MIN_TRADE_COUNT = 5
HIGH_DRAWDOWN_THRESHOLD = -0.20


@dataclass(frozen=True)
class ResearchWarnings:
    short_sample: bool
    too_few_trades: bool
    no_trades: bool
    no_completed_exits: bool
    high_drawdown_relative_to_return: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def build_research_warnings(metrics: RunMetrics, trades: pd.DataFrame) -> ResearchWarnings:
    trade_count = int(len(trades))
    no_trades = trade_count == 0
    too_few_trades = 0 < trade_count < MIN_TRADE_COUNT
    short_sample = metrics.observations < SHORT_SAMPLE_OBSERVATIONS
    no_completed_exits = _has_entries_without_exits(trades)
    high_drawdown_relative_to_return = (
        metrics.max_drawdown <= HIGH_DRAWDOWN_THRESHOLD
        and metrics.total_return <= abs(metrics.max_drawdown)
    )

    warnings: list[str] = []
    if no_trades:
        warnings.append("Strategy did not trade.")
    elif too_few_trades:
        warnings.append(f"Only {trade_count} trades; results may be dominated by a small sample.")
    if no_completed_exits:
        warnings.append("Trade log has entries but no completed exits.")
    if short_sample:
        warnings.append(
            f"Only {metrics.observations} equity observations; sample is shorter than {SHORT_SAMPLE_OBSERVATIONS} trading days."
        )
    if high_drawdown_relative_to_return:
        warnings.append("Max drawdown is large relative to total return.")

    return ResearchWarnings(
        short_sample=short_sample,
        too_few_trades=too_few_trades,
        no_trades=no_trades,
        no_completed_exits=no_completed_exits,
        high_drawdown_relative_to_return=high_drawdown_relative_to_return,
        warnings=warnings,
    )


def save_research_warnings(warnings: ResearchWarnings, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    warnings_path = destination / "research_warnings.json"
    warnings_path.write_text(
        json.dumps(warnings.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(warnings_path)


def research_warnings_section(warnings: ResearchWarnings) -> str:
    warning_lines = "\n".join(f"- {warning}" for warning in warnings.warnings) if warnings.warnings else "- None"
    return f"""## Research Warnings

{warning_lines}
"""


def append_research_warnings_section(report_markdown: str, warnings: ResearchWarnings) -> str:
    return report_markdown.rstrip() + "\n\n" + research_warnings_section(warnings)


def _has_entries_without_exits(trades: pd.DataFrame) -> bool:
    if trades.empty or "side" not in trades.columns:
        return False
    sides = set(str(side) for side in trades["side"])
    return "buy" in sides and "sell" not in sides
