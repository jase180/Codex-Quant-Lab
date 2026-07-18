"""Robustness checks that rerun normal backtests under controlled changes."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd

from .costs import resolve_cost_assumptions
from .data_quality import build_data_quality_report
from .research_registry import require_experiment
from .run_artifacts import RunArtifactResult, run_single_backtest
from .run_config import RunExecutionConfig
from .strategy_schema import load_strategy


COST_SENSITIVITY_SUMMARY_FILENAME = "cost_sensitivity_summary.csv"
COST_SENSITIVITY_REPORT_FILENAME = "cost_sensitivity_report.md"
COST_SENSITIVITY_FIELDNAMES = [
    "run_id",
    "cost_preset",
    "commission_fixed",
    "commission_rate",
    "slippage_bps",
    "final_equity",
    "total_return",
    "cagr",
    "sharpe_ratio",
    "max_drawdown",
    "trade_count",
    "benchmark_name",
    "benchmark_total_return",
    "excess_total_return",
    "output_dir",
    "metadata_path",
]


@dataclass(frozen=True)
class CostSensitivityResult:
    rows: list[dict[str, str | int | float | None]]
    summary_path: str
    report_path: str


def run_cost_sensitivity(args) -> CostSensitivityResult:
    """Run one strategy setup once per cost preset and summarize the damage."""

    require_experiment(args.experiments_path, args.experiment_id)
    strategy_spec = load_strategy(args.strategy)
    data = pd.read_csv(args.data)
    data_quality = build_data_quality_report(data)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str | int | float | None]] = []
    for index, cost_preset in enumerate(args.cost_preset, start=1):
        cost_assumptions = resolve_cost_assumptions(
            cost_preset=cost_preset,
            commission_fixed=None,
            commission_rate=None,
            slippage_bps=None,
        )
        run_id = f"cost_{index:03d}_{_slug(cost_preset)}"
        run_output_dir = output_dir / run_id
        config = RunExecutionConfig.from_values(
            data_path=args.data,
            index_path=args.index_path,
            initial_cash=args.initial_cash,
            quantity=args.quantity,
            sizing=args.sizing,
            allocation=args.allocation,
            benchmark=args.benchmark,
            cost_assumptions=cost_assumptions,
            command_tokens=args.command_tokens,
            experiment_id=args.experiment_id,
            experiments_path=args.experiments_path,
        )
        run_output = run_single_backtest(
            config=config,
            data=data,
            data_quality=data_quality,
            strategy_spec=strategy_spec,
            output_dir=run_output_dir,
            run_name=f"{strategy_spec.name} Cost Sensitivity {cost_preset}",
            run_type="cost_sensitivity_run",
            run_id=run_id,
            parameters={"cost_preset": cost_preset},
        )
        rows.append(_cost_sensitivity_row(run_id, cost_assumptions, run_output, run_output_dir))

    summary_path = save_cost_sensitivity_summary(rows, output_dir)
    report_path = save_cost_sensitivity_report(
        rows,
        output_dir,
        strategy_id=strategy_spec.strategy_id,
        benchmark=args.benchmark,
    )
    return CostSensitivityResult(rows=rows, summary_path=summary_path, report_path=report_path)


def save_cost_sensitivity_summary(
    rows: Sequence[dict[str, str | int | float | None]],
    output_dir: str | Path,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary_path = destination / COST_SENSITIVITY_SUMMARY_FILENAME
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COST_SENSITIVITY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return str(summary_path)


def save_cost_sensitivity_report(
    rows: Sequence[dict[str, str | int | float | None]],
    output_dir: str | Path,
    *,
    strategy_id: str,
    benchmark: str,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / COST_SENSITIVITY_REPORT_FILENAME
    report_path.write_text(
        _format_cost_sensitivity_report(rows, strategy_id=strategy_id, benchmark=benchmark),
        encoding="utf-8",
    )
    return str(report_path)


def _cost_sensitivity_row(
    run_id: str,
    cost_assumptions,
    run_output: RunArtifactResult,
    output_dir: Path,
) -> dict[str, str | int | float | None]:
    return {
        "run_id": run_id,
        "cost_preset": cost_assumptions.preset,
        "commission_fixed": cost_assumptions.commission_fixed,
        "commission_rate": cost_assumptions.commission_rate,
        "slippage_bps": cost_assumptions.slippage_bps,
        "final_equity": run_output.final_equity,
        "total_return": run_output.total_return,
        "cagr": run_output.cagr,
        "sharpe_ratio": run_output.sharpe_ratio,
        "max_drawdown": run_output.max_drawdown,
        "trade_count": run_output.trade_count,
        "benchmark_name": run_output.benchmark_name,
        "benchmark_total_return": run_output.benchmark_total_return,
        "excess_total_return": run_output.excess_total_return,
        "output_dir": str(output_dir),
        "metadata_path": run_output.artifact_paths["metadata"],
    }


def _format_cost_sensitivity_report(
    rows: Sequence[dict[str, str | int | float | None]],
    *,
    strategy_id: str,
    benchmark: str,
) -> str:
    lines = [
        "# Cost Sensitivity Report",
        "",
        f"- Strategy: `{strategy_id}`",
        f"- Benchmark: `{benchmark}`",
        f"- Runs: `{len(rows)}`",
        "",
        "## Verdict",
        "",
        f"- {_cost_sensitivity_verdict(rows)}",
        "",
        "## Results",
        "",
        "| run | cost preset | return | excess | drawdown | sharpe | trades | metadata |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    f"| `{row['run_id']}`",
                    f"`{row['cost_preset']}`",
                    _format_percent(row["total_return"]),
                    _format_percent(row["excess_total_return"]),
                    _format_percent(row["max_drawdown"]),
                    _format_decimal(row["sharpe_ratio"]),
                    str(row["trade_count"]),
                    f"`{row['metadata_path']}` |",
                ]
            )
        )
    lines.extend(
        [
            "",
            "## Skeptical Notes",
            "",
            "- Cost sensitivity is a stress check, not proof of future performance.",
            "- If excess return turns negative under stricter costs, treat the idea as fragile.",
            "- Inspect child run reports before using this result in a decision draft.",
            "",
        ]
    )
    return "\n".join(lines)


def _cost_sensitivity_verdict(rows: Sequence[dict[str, str | int | float | None]]) -> str:
    if not rows:
        return "No cost sensitivity runs were produced."
    excess_values = [_numeric(row["excess_total_return"]) for row in rows]
    if all(value > 0 for value in excess_values):
        return "Result survived all requested cost presets on benchmark excess return."
    if any(value > 0 for value in excess_values):
        return "Result is cost fragile: some presets beat the benchmark and some did not."
    return "Result did not survive cost sensitivity: no requested preset beat the benchmark."


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_").lower()


def _numeric(value: object, *, missing: float = float("-inf")) -> float:
    if value is None:
        return missing
    try:
        return float(value)
    except (TypeError, ValueError):
        return missing


def _format_percent(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2%}"


def _format_decimal(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}"
