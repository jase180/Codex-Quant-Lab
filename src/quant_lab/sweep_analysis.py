"""Markdown analysis helpers for parameter sweep results."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Sequence

from .summary_rows import SummaryValue


@dataclass(frozen=True)
class StabilityAssessment:
    best_run_id: str
    best_total_return: float
    neighbor_count: int
    strong_neighbor_count: int
    threshold_total_return: float
    assessment: str
    explanation: str


def format_sweep_analysis_section(
    rows: Sequence[Mapping[str, SummaryValue]],
    *,
    top_n: int = 5,
) -> str:
    if not rows:
        return "## Sweep Analysis\n\nNo sweep rows were produced.\n"

    return (
        "## Top Runs\n\n"
        + _format_top_runs_table(rows, top_n=top_n)
        + "\n\n"
        + "## Parameter Stability\n\n"
        + _format_stability_assessment(analyze_parameter_stability(rows))
        + "\n"
    )


def analyze_parameter_stability(rows: Sequence[Mapping[str, SummaryValue]]) -> StabilityAssessment:
    if not rows:
        raise ValueError("At least one sweep row is required.")

    best = rows[0]
    best_params = _row_params(best)
    best_total_return = float(best["total_return"])
    threshold = _strong_neighbor_threshold(best_total_return)
    neighbors = [
        row
        for row in rows[1:]
        if _is_one_parameter_neighbor(best_params, _row_params(row))
    ]
    strong_neighbors = [
        row
        for row in neighbors
        if float(row["total_return"]) >= threshold
    ]

    if not neighbors:
        assessment = "grid_too_sparse"
        explanation = "No one-parameter neighbors were found for the best run, so stability cannot be judged."
    elif not strong_neighbors:
        assessment = "isolated"
        explanation = "The best run is isolated: no one-parameter neighbor stayed near its total return."
    elif len(strong_neighbors) / len(neighbors) <= 0.5:
        assessment = "mixed"
        explanation = "No more than half of one-parameter neighbors stayed near the best run."
    else:
        assessment = "supported"
        explanation = "Most one-parameter neighbors stayed near the best run."

    return StabilityAssessment(
        best_run_id=str(best["run_id"]),
        best_total_return=best_total_return,
        neighbor_count=len(neighbors),
        strong_neighbor_count=len(strong_neighbors),
        threshold_total_return=threshold,
        assessment=assessment,
        explanation=explanation,
    )


def _format_top_runs_table(
    rows: Sequence[Mapping[str, SummaryValue]],
    *,
    top_n: int,
) -> str:
    lines = [
        "| Rank | Run | Total Return | Excess Return | Sharpe | Trades | Params |",
        "| ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for rank, row in enumerate(rows[:top_n], start=1):
        lines.append(
            "| "
            f"{rank} | "
            f"`{row['run_id']}` | "
            f"{float(row['total_return']):.2%} | "
            f"{_format_optional_percent(row.get('excess_total_return'))} | "
            f"{_format_optional_decimal(row.get('sharpe_ratio'))} | "
            f"{int(row['trade_count'])} | "
            f"`{row['params']}` |"
        )
    return "\n".join(lines)


def _format_stability_assessment(assessment: StabilityAssessment) -> str:
    return "\n".join(
        [
            f"- Best run: `{assessment.best_run_id}`",
            f"- Best total return: {assessment.best_total_return:.2%}",
            f"- Strong-neighbor threshold: {assessment.threshold_total_return:.2%}",
            f"- One-parameter neighbors: {assessment.neighbor_count}",
            f"- Strong one-parameter neighbors: {assessment.strong_neighbor_count}",
            f"- Assessment: `{assessment.assessment}`",
            f"- Interpretation: {assessment.explanation}",
            "",
            (
                "This is a deterministic heuristic, not statistical proof. "
                "Use it to decide what deserves deeper testing."
            ),
        ]
    )


def _row_params(row: Mapping[str, SummaryValue]) -> dict[str, Any]:
    raw_params = row.get("params")
    if not isinstance(raw_params, str):
        return {}
    parsed = json.loads(raw_params)
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _is_one_parameter_neighbor(best_params: dict[str, Any], candidate_params: dict[str, Any]) -> bool:
    if set(best_params) != set(candidate_params):
        return False
    differing_keys = [
        key
        for key, best_value in best_params.items()
        if candidate_params[key] != best_value
    ]
    return len(differing_keys) == 1


def _strong_neighbor_threshold(best_total_return: float) -> float:
    # A neighbor is "strong" if it is within 5 percentage points of the best run
    # or within 25% of the best return magnitude, whichever is wider.
    margin = max(0.05, abs(best_total_return) * 0.25)
    return best_total_return - margin


def _format_optional_percent(value: object) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.2%}"


def _format_optional_decimal(value: object) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.4f}"
