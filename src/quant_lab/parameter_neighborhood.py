"""Focused robustness reports for sweep parameter neighborhoods."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .summary_rows import SummaryValue
from .sweep_guardrails import load_sweep_summary_rows


PARAMETER_NEIGHBORHOOD_SUMMARY_FILENAME = "parameter_neighborhood_summary.csv"
PARAMETER_NEIGHBORHOOD_REPORT_FILENAME = "parameter_neighborhood_report.md"
PARAMETER_NEIGHBORHOOD_FIELDNAMES = [
    "parameter",
    "best_value",
    "neighbor_count",
    "benchmark_beating_neighbors",
    "best_neighbor_run_id",
    "best_neighbor_value",
    "best_neighbor_excess_total_return",
    "assessment",
]


@dataclass(frozen=True)
class ParameterNeighborhoodResult:
    summary_path: str
    report_path: str
    best_run_id: str | None
    assessment: str
    rows: list[dict[str, str | int | float | None]]
    skipped_parameters: list[str]
    incompatible_row_count: int


def summarize_parameter_neighborhood(
    *,
    summary_path: str | Path,
    output_dir: str | Path | None = None,
) -> ParameterNeighborhoodResult:
    """Write a focused neighborhood report for an existing sweep summary.

    The sweep summary is already sorted by total return when loaded. We use its
    first row as the winner, then ask a narrower question than the normal sweep
    analysis: did nearby numeric parameter values also beat the benchmark?
    """

    source = Path(summary_path)
    rows = load_sweep_summary_rows(source)
    destination = Path(output_dir) if output_dir is not None else source.parent
    destination.mkdir(parents=True, exist_ok=True)

    if not rows:
        result = ParameterNeighborhoodResult(
            summary_path=str(destination / PARAMETER_NEIGHBORHOOD_SUMMARY_FILENAME),
            report_path=str(destination / PARAMETER_NEIGHBORHOOD_REPORT_FILENAME),
            best_run_id=None,
            assessment="no_rows",
            rows=[],
            skipped_parameters=[],
            incompatible_row_count=0,
        )
        _write_summary(result.rows, result.summary_path)
        _write_report(result, source)
        return result

    best = rows[0]
    best_params = _parse_params(best)
    numeric_parameters = {
        key: value
        for key, value in best_params.items()
        if _is_numeric_parameter_value(value)
    }
    skipped_parameters = [
        key
        for key in best_params
        if key not in numeric_parameters
    ]
    incompatible_row_count = _incompatible_row_count(best_params, rows[1:])
    summary_rows = [
        _parameter_neighborhood_row(parameter, best_value, best_params, rows[1:])
        for parameter, best_value in sorted(numeric_parameters.items())
    ]
    assessment = _overall_assessment(summary_rows, skipped_parameters=skipped_parameters)
    result = ParameterNeighborhoodResult(
        summary_path=str(destination / PARAMETER_NEIGHBORHOOD_SUMMARY_FILENAME),
        report_path=str(destination / PARAMETER_NEIGHBORHOOD_REPORT_FILENAME),
        best_run_id=str(best["run_id"]),
        assessment=assessment,
        rows=summary_rows,
        skipped_parameters=skipped_parameters,
        incompatible_row_count=incompatible_row_count,
    )
    _write_summary(result.rows, result.summary_path)
    _write_report(result, source)
    return result


def _parameter_neighborhood_row(
    parameter: str,
    best_value: int | float,
    best_params: Mapping[str, Any],
    candidate_rows: Sequence[Mapping[str, SummaryValue]],
) -> dict[str, str | int | float | None]:
    neighbors = [
        row
        for row in candidate_rows
        if _differs_only_by_parameter(best_params, _parse_params(row), parameter)
    ]
    benchmark_beating = [
        row
        for row in neighbors
        if float(row["excess_total_return"]) > 0.0
    ]
    best_neighbor = max(neighbors, key=lambda row: float(row["excess_total_return"]), default=None)
    assessment = "isolated"
    if neighbors and len(benchmark_beating) == len(neighbors):
        assessment = "supported"
    elif benchmark_beating:
        assessment = "mixed"
    elif not neighbors:
        assessment = "missing_neighbors"

    return {
        "parameter": parameter,
        "best_value": best_value,
        "neighbor_count": len(neighbors),
        "benchmark_beating_neighbors": len(benchmark_beating),
        "best_neighbor_run_id": str(best_neighbor["run_id"]) if best_neighbor is not None else None,
        "best_neighbor_value": _parse_params(best_neighbor).get(parameter) if best_neighbor is not None else None,
        "best_neighbor_excess_total_return": (
            float(best_neighbor["excess_total_return"]) if best_neighbor is not None else None
        ),
        "assessment": assessment,
    }


def _write_summary(rows: Sequence[dict[str, str | int | float | None]], summary_path: str | Path) -> None:
    with Path(summary_path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PARAMETER_NEIGHBORHOOD_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(result: ParameterNeighborhoodResult, source: Path) -> None:
    Path(result.report_path).write_text(_format_report(result, source), encoding="utf-8")


def _format_report(result: ParameterNeighborhoodResult, source: Path) -> str:
    lines = [
        "# Parameter Neighborhood Report",
        "",
        f"- Source summary: `{source}`",
        f"- Best run: `{result.best_run_id or 'none'}`",
        f"- Assessment: `{result.assessment}`",
        f"- Incompatible rows skipped: `{result.incompatible_row_count}`",
        "",
        "## Results",
        "",
        "| parameter | best value | neighbors | beat benchmark | best neighbor | best neighbor excess | assessment |",
        "| --- | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for row in result.rows:
        lines.append(
            " | ".join(
                [
                    f"| `{row['parameter']}`",
                    str(row["best_value"]),
                    str(row["neighbor_count"]),
                    str(row["benchmark_beating_neighbors"]),
                    f"`{row['best_neighbor_run_id'] or '-'}`",
                    _format_percent(row["best_neighbor_excess_total_return"]),
                    f"`{row['assessment']}` |",
                ]
            )
        )
    if not result.rows:
        lines.append("| none | - | 0 | 0 | `-` | - | `no_numeric_parameters` |")

    skipped = ", ".join(f"`{parameter}`" for parameter in result.skipped_parameters) or "none"
    lines.extend(
        [
            "",
            "## Skipped Parameters",
            "",
            f"- {skipped}",
            "",
            "## Skeptical Notes",
            "",
            "- This report reads an existing sweep summary; it does not rerun the backtester.",
            "- A parameter is supported only when nearby numeric values also beat the benchmark.",
            "- Missing neighbors usually mean the sweep grid is too sparse to judge that parameter.",
            "- Non-numeric parameters are listed but skipped because distance is not meaningful.",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_params(row: Mapping[str, SummaryValue] | None) -> dict[str, Any]:
    if row is None:
        return {}
    raw_params = row.get("params")
    if not isinstance(raw_params, str):
        return {}
    parsed = json.loads(raw_params)
    return parsed if isinstance(parsed, dict) else {}


def _is_numeric_parameter_value(value: object) -> bool:
    # bool is a subclass of int in Python, but it represents a mode/flag here,
    # not a numeric sweep distance.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _differs_only_by_parameter(
    best_params: Mapping[str, Any],
    candidate_params: Mapping[str, Any],
    parameter: str,
) -> bool:
    if set(best_params) != set(candidate_params):
        return False
    differing_keys = [
        key
        for key, best_value in best_params.items()
        if candidate_params[key] != best_value
    ]
    return differing_keys == [parameter]


def _incompatible_row_count(best_params: Mapping[str, Any], candidate_rows: Sequence[Mapping[str, SummaryValue]]) -> int:
    return sum(1 for row in candidate_rows if set(_parse_params(row)) != set(best_params))


def _overall_assessment(
    rows: Sequence[dict[str, str | int | float | None]],
    *,
    skipped_parameters: Sequence[str],
) -> str:
    if not rows:
        return "no_numeric_parameters"
    row_assessments = {str(row["assessment"]) for row in rows}
    if row_assessments == {"supported"}:
        return "supported"
    if "supported" in row_assessments or "mixed" in row_assessments:
        return "mixed"
    if "isolated" in row_assessments:
        return "isolated"
    if skipped_parameters:
        return "partial_missing_neighbors"
    return "missing_neighbors"


def _format_percent(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2%}"
