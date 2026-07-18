"""Guardrail reports for strategy sweep summaries."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .sweep_analysis import analyze_parameter_stability
from .summary_rows import SWEEP_SUMMARY_FIELDNAMES, SummaryValue

SWEEP_GUARDRAIL_REPORT_FILENAME = "sweep_guardrails.md"


@dataclass(frozen=True)
class SweepGuardrailReport:
    summary_path: str
    report_path: str
    row_count: int
    best_run_id: str | None
    best_total_return: float | None
    best_excess_total_return: float | None
    best_trade_count: int | None
    warnings: list[str]


def summarize_sweep_guardrails(
    *,
    summary_path: str | Path,
    output_path: str | Path | None = None,
    max_rows: int = 25,
    min_trades: int = 5,
) -> SweepGuardrailReport:
    """Write a markdown warning report for an existing sweep summary CSV."""

    source = Path(summary_path)
    rows = load_sweep_summary_rows(source)
    report_file = Path(output_path) if output_path is not None else source.parent / SWEEP_GUARDRAIL_REPORT_FILENAME
    warnings = _sweep_guardrail_warnings(rows, max_rows=max_rows, min_trades=min_trades)
    best = rows[0] if rows else None
    report = SweepGuardrailReport(
        summary_path=str(source),
        report_path=str(report_file),
        row_count=len(rows),
        best_run_id=str(best["run_id"]) if best is not None else None,
        best_total_return=float(best["total_return"]) if best is not None else None,
        best_excess_total_return=float(best["excess_total_return"]) if best is not None else None,
        best_trade_count=int(best["trade_count"]) if best is not None else None,
        warnings=warnings,
    )
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(_render_sweep_guardrail_report(report, rows), encoding="utf-8")
    return report


def load_sweep_summary_rows(summary_path: str | Path) -> list[dict[str, SummaryValue]]:
    with Path(summary_path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing_fields = [field for field in SWEEP_SUMMARY_FIELDNAMES if field not in (reader.fieldnames or [])]
        if missing_fields:
            raise ValueError(f"sweep summary missing required columns: {', '.join(missing_fields)}")
        rows = [_coerce_sweep_row(row) for row in reader]
    rows.sort(key=lambda row: float(row["total_return"]), reverse=True)
    return rows


def _coerce_sweep_row(row: dict[str, str]) -> dict[str, SummaryValue]:
    return {
        "run_id": row["run_id"],
        "strategy_id": row["strategy_id"],
        "params": row["params"],
        "final_equity": _float(row["final_equity"]),
        "total_return": _float(row["total_return"]),
        "cagr": _optional_float(row["cagr"]),
        "sharpe_ratio": _optional_float(row["sharpe_ratio"]),
        "max_drawdown": _float(row["max_drawdown"]),
        "trade_count": int(float(row["trade_count"])),
        "sizing": row["sizing"],
        "quantity": _float(row["quantity"]),
        "allocation": _float(row["allocation"]),
        "cost_preset": row["cost_preset"],
        "commission_fixed": _float(row["commission_fixed"]),
        "commission_rate": _float(row["commission_rate"]),
        "slippage_bps": _float(row["slippage_bps"]),
        "benchmark_name": row["benchmark_name"],
        "benchmark_final_equity": _float(row["benchmark_final_equity"]),
        "benchmark_total_return": _float(row["benchmark_total_return"]),
        "benchmark_cagr": _optional_float(row["benchmark_cagr"]),
        "benchmark_sharpe_ratio": _optional_float(row["benchmark_sharpe_ratio"]),
        "benchmark_max_drawdown": _float(row["benchmark_max_drawdown"]),
        "excess_total_return": _float(row["excess_total_return"]),
        "output_dir": row["output_dir"],
    }


def _float(value: str) -> float:
    return float(value)


def _optional_float(value: str) -> float | None:
    return None if value == "" else float(value)


def _sweep_guardrail_warnings(
    rows: list[dict[str, SummaryValue]],
    *,
    max_rows: int,
    min_trades: int,
) -> list[str]:
    warnings: list[str] = []
    if not rows:
        return ["No sweep rows were found; there is no evidence to interpret."]

    best = rows[0]
    if len(rows) > max_rows:
        warnings.append(f"Large parameter grid: {len(rows)} rows exceeds the configured cap of {max_rows}.")
    low_trade_rows = [row for row in rows if int(row["trade_count"]) < min_trades]
    if low_trade_rows:
        warnings.append(
            f"{len(low_trade_rows)} run(s) have fewer than {min_trades} trades; tiny trade counts make rankings fragile."
        )
    if int(best["trade_count"]) < min_trades:
        warnings.append(f"Best run has only {int(best['trade_count'])} trade(s); treat the winner as weak evidence.")
    if float(best["excess_total_return"]) <= 0.0:
        warnings.append("Best run did not beat its benchmark on total return.")

    stability = analyze_parameter_stability(rows)
    if stability.assessment in {"isolated", "mixed", "grid_too_sparse"}:
        warnings.append(
            f"Parameter stability is `{stability.assessment}`; the best row may be fragile rather than robust."
        )
    return warnings


def _render_sweep_guardrail_report(
    report: SweepGuardrailReport,
    rows: list[dict[str, SummaryValue]],
) -> str:
    warnings = "\n".join(f"- {warning}" for warning in report.warnings) if report.warnings else "- none"
    best_lines = "- Best run: `none`\n"
    if report.best_run_id is not None:
        best_lines = "\n".join(
            [
                f"- Best run: `{report.best_run_id}`",
                f"- Best total return: `{report.best_total_return:.2%}`",
                f"- Best excess total return: `{report.best_excess_total_return:.2%}`",
                f"- Best trade count: `{report.best_trade_count}`",
            ]
        )
    row_lines = "\n".join(
        f"- `{row['run_id']}` return `{float(row['total_return']):.2%}`, "
        f"excess `{float(row['excess_total_return']):.2%}`, trades `{int(row['trade_count'])}`"
        for row in rows[:5]
    )
    if not row_lines:
        row_lines = "- none"

    return f"""# Sweep Guardrails

## Source

- Summary: `{report.summary_path}`
- Rows: `{report.row_count}`

## Best Row

{best_lines}

## Warnings

{warnings}

## Top Rows

{row_lines}

These warnings are deterministic heuristics. They do not prove a strategy works
or fails; they highlight conditions that deserve skepticism before follow-up
research.
"""
