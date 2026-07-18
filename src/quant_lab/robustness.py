"""Robustness checks that rerun normal backtests under controlled changes."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd

from .costs import CostAssumptions, resolve_cost_assumptions
from .data_quality import build_data_quality_report
from .research_registry import require_experiment
from .run_artifacts import RunArtifactResult, run_single_backtest
from .run_config import RunExecutionConfig
from .strategy_schema import StrategySpec, load_strategy


COST_SENSITIVITY_SUMMARY_FILENAME = "cost_sensitivity_summary.csv"
COST_SENSITIVITY_REPORT_FILENAME = "cost_sensitivity_report.md"
DATE_SENSITIVITY_SUMMARY_FILENAME = "date_sensitivity_summary.csv"
DATE_SENSITIVITY_REPORT_FILENAME = "date_sensitivity_report.md"
BENCHMARK_SENSITIVITY_SUMMARY_FILENAME = "benchmark_sensitivity_summary.csv"
BENCHMARK_SENSITIVITY_REPORT_FILENAME = "benchmark_sensitivity_report.md"
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
DATE_SENSITIVITY_FIELDNAMES = [
    "run_id",
    "window_start",
    "window_end",
    "row_count",
    "cost_preset",
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
BENCHMARK_SENSITIVITY_FIELDNAMES = [
    "run_id",
    "benchmark_name",
    "cost_preset",
    "final_equity",
    "total_return",
    "cagr",
    "sharpe_ratio",
    "max_drawdown",
    "trade_count",
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


@dataclass(frozen=True)
class DateSensitivityWindow:
    window_id: str
    start: str
    end: str


@dataclass(frozen=True)
class DateSensitivityResult:
    rows: list[dict[str, str | int | float | None]]
    summary_path: str
    report_path: str


@dataclass(frozen=True)
class BenchmarkSensitivityResult:
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
        run_output = _run_robustness_child(
            args=args,
            data=data,
            data_quality=data_quality,
            strategy_spec=strategy_spec,
            cost_assumptions=cost_assumptions,
            benchmark=args.benchmark,
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


def run_date_sensitivity(args) -> DateSensitivityResult:
    """Run one strategy setup over explicit date windows."""

    require_experiment(args.experiments_path, args.experiment_id)
    windows = parse_date_sensitivity_windows(args.window)
    strategy_spec = load_strategy(args.strategy)
    data = pd.read_csv(args.data)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    cost_assumptions = resolve_cost_assumptions(
        cost_preset=args.cost_preset,
        commission_fixed=args.commission_fixed,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
    )

    rows: list[dict[str, str | int | float | None]] = []
    for window in windows:
        window_data = slice_date_sensitivity_data(data, window)
        data_quality = build_data_quality_report(window_data)
        run_output_dir = output_dir / window.window_id
        run_output = _run_robustness_child(
            args=args,
            data=window_data,
            data_quality=data_quality,
            strategy_spec=strategy_spec,
            cost_assumptions=cost_assumptions,
            benchmark=args.benchmark,
            output_dir=run_output_dir,
            run_name=f"{strategy_spec.name} Date Sensitivity {window.start} to {window.end}",
            run_type="date_sensitivity_run",
            run_id=window.window_id,
            parameters={
                "window_start": window.start,
                "window_end": window.end,
            },
        )
        rows.append(_date_sensitivity_row(window, cost_assumptions, run_output, run_output_dir, len(window_data)))

    summary_path = save_date_sensitivity_summary(rows, output_dir)
    report_path = save_date_sensitivity_report(
        rows,
        output_dir,
        strategy_id=strategy_spec.strategy_id,
        benchmark=args.benchmark,
    )
    return DateSensitivityResult(rows=rows, summary_path=summary_path, report_path=report_path)


def run_benchmark_sensitivity(args) -> BenchmarkSensitivityResult:
    """Run one strategy setup once per benchmark choice."""

    require_experiment(args.experiments_path, args.experiment_id)
    strategy_spec = load_strategy(args.strategy)
    data = pd.read_csv(args.data)
    data_quality = build_data_quality_report(data)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    cost_assumptions = resolve_cost_assumptions(
        cost_preset=args.cost_preset,
        commission_fixed=args.commission_fixed,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
    )

    rows: list[dict[str, str | int | float | None]] = []
    for index, benchmark in enumerate(args.benchmark, start=1):
        run_id = f"benchmark_{index:03d}_{_slug(benchmark)}"
        run_output_dir = output_dir / run_id
        run_output = _run_robustness_child(
            args=args,
            data=data,
            data_quality=data_quality,
            strategy_spec=strategy_spec,
            cost_assumptions=cost_assumptions,
            benchmark=benchmark,
            output_dir=run_output_dir,
            run_name=f"{strategy_spec.name} Benchmark Sensitivity {benchmark}",
            run_type="benchmark_sensitivity_run",
            run_id=run_id,
            parameters={"benchmark": benchmark},
        )
        rows.append(_benchmark_sensitivity_row(run_id, cost_assumptions, run_output, run_output_dir))

    summary_path = save_benchmark_sensitivity_summary(rows, output_dir)
    report_path = save_benchmark_sensitivity_report(
        rows,
        output_dir,
        strategy_id=strategy_spec.strategy_id,
    )
    return BenchmarkSensitivityResult(rows=rows, summary_path=summary_path, report_path=report_path)


def _run_robustness_child(
    *,
    args,
    data: pd.DataFrame,
    data_quality,
    strategy_spec: StrategySpec,
    cost_assumptions: CostAssumptions,
    benchmark: str,
    output_dir: Path,
    run_name: str,
    run_type: str,
    run_id: str,
    parameters: dict[str, str],
) -> RunArtifactResult:
    """Write one child backtest using the same artifact path as a normal run.

    Robustness commands differ in what they perturb: costs, dates, benchmarks, or
    later maybe sizing. The run metadata should still look like a normal
    backtest, so this helper centralizes the shared config fields and keeps each
    public robustness command focused on the one variable it is changing.
    """

    config = RunExecutionConfig.from_values(
        data_path=args.data,
        index_path=args.index_path,
        initial_cash=args.initial_cash,
        quantity=args.quantity,
        sizing=args.sizing,
        allocation=args.allocation,
        benchmark=benchmark,
        cost_assumptions=cost_assumptions,
        command_tokens=args.command_tokens,
        experiment_id=args.experiment_id,
        experiments_path=args.experiments_path,
    )
    return run_single_backtest(
        config=config,
        data=data,
        data_quality=data_quality,
        strategy_spec=strategy_spec,
        output_dir=output_dir,
        run_name=run_name,
        run_type=run_type,
        run_id=run_id,
        parameters=parameters,
    )


def parse_date_sensitivity_windows(raw_windows: Sequence[str]) -> list[DateSensitivityWindow]:
    if not raw_windows:
        raise ValueError("At least one --window is required.")

    windows: list[DateSensitivityWindow] = []
    for index, raw_window in enumerate(raw_windows, start=1):
        parts = [part.strip() for part in raw_window.split(",")]
        if len(parts) != 2 or any(not part for part in parts):
            raise ValueError("--window must use start,end format.")
        start, end = parts
        start_date = pd.Timestamp(start)
        end_date = pd.Timestamp(end)
        if start_date > end_date:
            raise ValueError(f"date sensitivity window {index} start must be on or before end.")
        windows.append(DateSensitivityWindow(window_id=f"window_{index:03d}", start=start, end=end))
    return windows


def slice_date_sensitivity_data(data: pd.DataFrame, window: DateSensitivityWindow) -> pd.DataFrame:
    if "date" not in data.columns:
        raise ValueError("date sensitivity requires a date column.")
    dates = pd.to_datetime(data["date"])
    sliced = data.loc[(dates >= pd.Timestamp(window.start)) & (dates <= pd.Timestamp(window.end))].copy()
    if sliced.empty:
        raise ValueError(f"{window.window_id} is empty: {window.start} to {window.end}.")
    if len(sliced) < 2:
        raise ValueError(f"{window.window_id} must contain at least two rows: {window.start} to {window.end}.")
    return sliced


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


def save_date_sensitivity_summary(
    rows: Sequence[dict[str, str | int | float | None]],
    output_dir: str | Path,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary_path = destination / DATE_SENSITIVITY_SUMMARY_FILENAME
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DATE_SENSITIVITY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return str(summary_path)


def save_benchmark_sensitivity_summary(
    rows: Sequence[dict[str, str | int | float | None]],
    output_dir: str | Path,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary_path = destination / BENCHMARK_SENSITIVITY_SUMMARY_FILENAME
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BENCHMARK_SENSITIVITY_FIELDNAMES)
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


def save_date_sensitivity_report(
    rows: Sequence[dict[str, str | int | float | None]],
    output_dir: str | Path,
    *,
    strategy_id: str,
    benchmark: str,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / DATE_SENSITIVITY_REPORT_FILENAME
    report_path.write_text(
        _format_date_sensitivity_report(rows, strategy_id=strategy_id, benchmark=benchmark),
        encoding="utf-8",
    )
    return str(report_path)


def save_benchmark_sensitivity_report(
    rows: Sequence[dict[str, str | int | float | None]],
    output_dir: str | Path,
    *,
    strategy_id: str,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / BENCHMARK_SENSITIVITY_REPORT_FILENAME
    report_path.write_text(
        _format_benchmark_sensitivity_report(rows, strategy_id=strategy_id),
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


def _date_sensitivity_row(
    window: DateSensitivityWindow,
    cost_assumptions,
    run_output: RunArtifactResult,
    output_dir: Path,
    row_count: int,
) -> dict[str, str | int | float | None]:
    return {
        "run_id": window.window_id,
        "window_start": window.start,
        "window_end": window.end,
        "row_count": row_count,
        "cost_preset": cost_assumptions.preset,
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


def _benchmark_sensitivity_row(
    run_id: str,
    cost_assumptions,
    run_output: RunArtifactResult,
    output_dir: Path,
) -> dict[str, str | int | float | None]:
    return {
        "run_id": run_id,
        "benchmark_name": run_output.benchmark_name,
        "cost_preset": cost_assumptions.preset,
        "final_equity": run_output.final_equity,
        "total_return": run_output.total_return,
        "cagr": run_output.cagr,
        "sharpe_ratio": run_output.sharpe_ratio,
        "max_drawdown": run_output.max_drawdown,
        "trade_count": run_output.trade_count,
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


def _format_date_sensitivity_report(
    rows: Sequence[dict[str, str | int | float | None]],
    *,
    strategy_id: str,
    benchmark: str,
) -> str:
    lines = [
        "# Date Sensitivity Report",
        "",
        f"- Strategy: `{strategy_id}`",
        f"- Benchmark: `{benchmark}`",
        f"- Windows: `{len(rows)}`",
        "",
        "## Verdict",
        "",
        f"- {_date_sensitivity_verdict(rows)}",
        "",
        "## Results",
        "",
        "| run | window | rows | return | excess | drawdown | sharpe | trades | metadata |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    f"| `{row['run_id']}`",
                    f"{row['window_start']} to {row['window_end']}",
                    str(row["row_count"]),
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
            "- Date sensitivity is a stress check, not proof that the strategy is regime-proof.",
            "- If a window underperforms the benchmark, read that child report before accepting the idea.",
            "- Do not move window dates after seeing the results.",
            "",
        ]
    )
    return "\n".join(lines)


def _format_benchmark_sensitivity_report(
    rows: Sequence[dict[str, str | int | float | None]],
    *,
    strategy_id: str,
) -> str:
    lines = [
        "# Benchmark Sensitivity Report",
        "",
        f"- Strategy: `{strategy_id}`",
        f"- Benchmarks: `{len(rows)}`",
        "",
        "## Verdict",
        "",
        f"- {_benchmark_sensitivity_verdict(rows)}",
        "",
        "## Results",
        "",
        "| run | benchmark | strategy return | benchmark return | excess | drawdown | sharpe | trades | metadata |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    f"| `{row['run_id']}`",
                    f"`{row['benchmark_name']}`",
                    _format_percent(row["total_return"]),
                    _format_percent(row["benchmark_total_return"]),
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
            "- Benchmark sensitivity is a comparison check, not proof of future performance.",
            "- Beating cash is useful, but beating buy-and-hold is a stronger hurdle for long-only equity ideas.",
            "- If the result only looks good against cash, treat it as weak evidence until tested against a market benchmark.",
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


def _date_sensitivity_verdict(rows: Sequence[dict[str, str | int | float | None]]) -> str:
    if not rows:
        return "No date sensitivity runs were produced."
    excess_values = [_numeric(row["excess_total_return"]) for row in rows]
    if all(value > 0 for value in excess_values):
        return "Result beat the benchmark in every requested date window."
    if any(value > 0 for value in excess_values):
        return "Result is date fragile: some windows beat the benchmark and some did not."
    return "Result did not survive date sensitivity: no requested window beat the benchmark."


def _benchmark_sensitivity_verdict(rows: Sequence[dict[str, str | int | float | None]]) -> str:
    if not rows:
        return "No benchmark sensitivity runs were produced."
    excess_by_benchmark = {
        str(row["benchmark_name"]): _numeric(row["excess_total_return"])
        for row in rows
    }
    buy_and_hold_excess = excess_by_benchmark.get("buy-and-hold")
    cash_excess = excess_by_benchmark.get("cash")
    if buy_and_hold_excess is not None and buy_and_hold_excess > 0:
        return "Result survived the buy-and-hold benchmark hurdle on excess return."
    if cash_excess is not None and cash_excess > 0:
        return "Result only cleared the cash hurdle; treat it as weak until it beats buy-and-hold."
    if any(value > 0 for value in excess_by_benchmark.values()):
        return "Result beat at least one requested benchmark but missed the strongest common hurdle."
    return "Result did not beat any requested benchmark on excess return."


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
