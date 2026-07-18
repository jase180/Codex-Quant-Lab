"""Sweep workflows for regular, train/test, and walk-forward research."""

from __future__ import annotations

import argparse
import copy
import csv
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd

from .benchmarks import build_benchmark
from .costs import resolve_cost_assumptions
from .data_quality import build_data_quality_report
from .research_registry import require_experiment
from .run_artifacts import current_git_commit, load_strategy_payload, run_sweep_variant
from .run_notes import load_research_note, note_command_lines, research_note_summary_line, save_research_note
from .strategy_schema import parse_strategy
from .summary_rows import (
    SWEEP_SUMMARY_FIELDNAMES,
    WALK_FORWARD_SUMMARY_FIELDNAMES,
    SweepSummaryRow,
    WalkForwardSummaryRow,
)
from .sweep_analysis import format_sweep_analysis_section


@dataclass(frozen=True)
class SweepSetup:
    """Inputs shared by every sweep workflow after CLI flags are resolved."""

    variants: list[dict]
    data: pd.DataFrame
    output_dir: Path
    research_note_path: str | None


@dataclass(frozen=True)
class TrainSweepResult:
    """Selected train-sweep evidence used before an out-of-sample test run."""

    rows: list[SweepSummaryRow]
    summary_path: str
    best_row: SweepSummaryRow
    best_variant: dict


def sweep_command(args: argparse.Namespace) -> int:
    args.cost_assumptions = resolve_cost_assumptions(
        cost_preset=args.cost_preset,
        commission_fixed=args.commission_fixed,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
    )
    require_experiment(args.experiments_path, args.experiment_id)

    if args.walk_forward_window:
        return walk_forward_sweep_command(args)
    if args.train_end or args.test_start:
        return train_test_sweep_command(args)

    setup = prepare_sweep_setup(args)
    data_quality = build_data_quality_report(setup.data)
    benchmark = build_benchmark(setup.data, args.initial_cash, args.benchmark)

    summary_rows: list[SweepSummaryRow] = []
    for index, variant in enumerate(setup.variants, start=1):
        run_id = f"run_{index:03d}"
        strategy_payload = variant["payload"]
        params = variant["params"]
        strategy_spec = parse_strategy(strategy_payload)
        run_name_prefix = args.run_name or strategy_spec.name
        summary_rows.append(
            run_sweep_variant(
                args=args,
                data=setup.data,
                benchmark_curve=benchmark.curve,
                benchmark_metrics=benchmark.metrics,
                benchmark_display_name=benchmark.display_name,
                data_quality=data_quality,
                strategy_spec=strategy_spec,
                strategy_payload=strategy_payload,
                run_dir=setup.output_dir / run_id,
                run_name=f"{run_name_prefix} {run_id}",
                parameters=params,
                run_type="sweep_run",
                run_id=run_id,
                research_note_path=setup.research_note_path,
            )
        )

    # Sorting after all runs keeps the run directories stable while making the
    # comparison table easy to scan from best to worst total return.
    summary_rows.sort(key=lambda row: float(row["total_return"]), reverse=True)
    summary_path = save_sweep_summary(summary_rows, setup.output_dir)
    research_path = save_research_summary(args, summary_rows, setup.output_dir)

    print(f"Sweep complete: {len(summary_rows)} runs")
    print(f"summary: {summary_path}")
    print(f"research: {research_path}")
    if summary_rows:
        best = summary_rows[0]
        print(f"best_run: {best['run_id']}")
        print(f"best_total_return: {float(best['total_return']):.2%}")
        print(f"best_excess_total_return: {float(best['excess_total_return']):.2%}")
    return 0


def walk_forward_sweep_command(args: argparse.Namespace) -> int:
    if args.train_end or args.test_start:
        raise ValueError("--walk-forward-window cannot be combined with --train-end or --test-start.")

    windows = parse_walk_forward_windows(args.walk_forward_window)
    setup = prepare_sweep_setup(args)

    summary_rows: list[WalkForwardSummaryRow] = []
    for window_index, window in enumerate(windows, start=1):
        window_id = f"window_{window_index:03d}"
        window_dir = setup.output_dir / window_id
        train_data = slice_date_range_data(setup.data, window["train_start"], window["train_end"], "train")
        test_data = slice_date_range_data(setup.data, window["test_start"], window["test_end"], "test")
        train_dir = window_dir / "train_sweep"
        test_dir = window_dir / "test_selected"

        train_result = run_train_sweep_variants(
            args=args,
            variants=setup.variants,
            train_data=train_data,
            train_dir=train_dir,
            run_type="walk_forward_train_run",
            run_id_prefix=f"{window_id}_",
            run_name_context=window_id,
            extra_params={
                "_workflow": "walk_forward",
                "_split_phase": "train",
                "_window_id": window_id,
                "_train_start": window["train_start"],
                "_train_end": window["train_end"],
                "_test_start": window["test_start"],
                "_test_end": window["test_end"],
                "_select_by": args.select_by,
            },
            research_note_path=setup.research_note_path,
        )
        best_train = train_result.best_row
        best_variant = train_result.best_variant

        test_benchmark = build_benchmark(test_data, args.initial_cash, args.benchmark)
        test_data_quality = build_data_quality_report(test_data)
        test_strategy_payload = best_variant["payload"]
        test_strategy_spec = parse_strategy(test_strategy_payload)
        test_params = {
            **best_variant["params"],
            "_workflow": "walk_forward",
            "_split_phase": "test",
            "_window_id": window_id,
            "_selected_train_run_id": best_train["run_id"],
            "_train_start": window["train_start"],
            "_train_end": window["train_end"],
            "_test_start": window["test_start"],
            "_test_end": window["test_end"],
            "_select_by": args.select_by,
        }
        test_row = run_sweep_variant(
            args=args,
            data=test_data,
            benchmark_curve=test_benchmark.curve,
            benchmark_metrics=test_benchmark.metrics,
            benchmark_display_name=test_benchmark.display_name,
            data_quality=test_data_quality,
            strategy_spec=test_strategy_spec,
            strategy_payload=test_strategy_payload,
            run_dir=test_dir,
            run_name=f"{args.run_name or test_strategy_spec.name} {window_id} test selected",
            parameters=test_params,
            run_type="walk_forward_test_run",
            run_id=f"{window_id}_test_selected",
            research_note_path=setup.research_note_path,
        )
        test_summary_path = save_sweep_summary([test_row], window_dir / "test_summary")
        summary_rows.append(
            build_walk_forward_summary_row(
                window_id=window_id,
                window=window,
                best_train=best_train,
                test_row=test_row,
                train_summary_path=train_result.summary_path,
                test_summary_path=test_summary_path,
            )
        )

    summary_path = save_walk_forward_summary(summary_rows, setup.output_dir)
    research_path = save_walk_forward_research_summary(args, summary_rows, setup.output_dir, summary_path)
    print(f"Walk-forward sweep complete: {len(summary_rows)} windows")
    print(f"summary: {summary_path}")
    print(f"research: {research_path}")
    return 0


def train_test_sweep_command(args: argparse.Namespace) -> int:
    if not args.train_end or not args.test_start:
        raise ValueError("--train-end and --test-start must be provided together.")

    setup = prepare_sweep_setup(args)
    train_data, test_data = split_train_test_data(setup.data, args.train_end, args.test_start)
    train_dir = setup.output_dir / "train_sweep"
    test_dir = setup.output_dir / "test_selected"

    train_result = run_train_sweep_variants(
        args=args,
        variants=setup.variants,
        train_data=train_data,
        train_dir=train_dir,
        run_type="train_sweep_run",
        run_id_prefix="",
        run_name_context="",
        extra_params={
            "_split_phase": "train",
            "_train_end": args.train_end,
            "_test_start": args.test_start,
            "_select_by": args.select_by,
        },
        research_note_path=setup.research_note_path,
    )
    best_train = train_result.best_row
    best_variant = train_result.best_variant

    test_benchmark = build_benchmark(test_data, args.initial_cash, args.benchmark)
    test_data_quality = build_data_quality_report(test_data)
    test_strategy_payload = best_variant["payload"]
    test_strategy_spec = parse_strategy(test_strategy_payload)
    test_params = {
        **best_variant["params"],
        "_split_phase": "test",
        "_selected_train_run_id": best_train["run_id"],
        "_train_end": args.train_end,
        "_test_start": args.test_start,
        "_select_by": args.select_by,
    }
    test_row = run_sweep_variant(
        args=args,
        data=test_data,
        benchmark_curve=test_benchmark.curve,
        benchmark_metrics=test_benchmark.metrics,
        benchmark_display_name=test_benchmark.display_name,
        data_quality=test_data_quality,
        strategy_spec=test_strategy_spec,
        strategy_payload=test_strategy_payload,
        run_dir=test_dir,
        run_name=f"{args.run_name or test_strategy_spec.name} test selected",
        parameters=test_params,
        run_type="test_selected_run",
        run_id="test_selected",
        research_note_path=setup.research_note_path,
    )
    test_summary_path = save_sweep_summary([test_row], setup.output_dir / "test_summary")
    research_path = save_train_test_research_summary(
        args=args,
        train_rows=train_result.rows,
        test_row=test_row,
        output_dir=setup.output_dir,
        train_summary_path=train_result.summary_path,
        test_summary_path=test_summary_path,
    )

    print(f"Train/test sweep complete: {len(train_result.rows)} train runs")
    print(f"train_summary: {train_result.summary_path}")
    print(f"test_summary: {test_summary_path}")
    print(f"research: {research_path}")
    print(f"selected_train_run: {best_train['run_id']}")
    print(f"selected_train_{args.select_by}: {_selection_value(best_train, args.select_by):.4f}")
    print(f"test_total_return: {float(test_row['total_return']):.2%}")
    return 0


def run_train_sweep_variants(
    *,
    args: argparse.Namespace,
    variants: Sequence[dict],
    train_data: pd.DataFrame,
    train_dir: Path,
    run_type: str,
    run_id_prefix: str,
    run_name_context: str,
    extra_params: dict,
    research_note_path: str | None,
) -> TrainSweepResult:
    train_benchmark = build_benchmark(train_data, args.initial_cash, args.benchmark)
    train_data_quality = build_data_quality_report(train_data)
    train_rows: list[SweepSummaryRow] = []
    variants_by_run_id: dict[str, dict] = {}

    for index, variant in enumerate(variants, start=1):
        local_run_id = f"run_{index:03d}"
        persisted_run_id = f"{run_id_prefix}{local_run_id}"
        variants_by_run_id[persisted_run_id] = variant
        strategy_payload = variant["payload"]
        params = {
            **variant["params"],
            **extra_params,
        }
        strategy_spec = parse_strategy(strategy_payload)
        run_name_prefix = args.run_name or strategy_spec.name
        run_name_parts = [run_name_prefix]
        if run_name_context:
            run_name_parts.append(run_name_context)
        run_name_parts.extend(["train", local_run_id])
        train_rows.append(
            run_sweep_variant(
                args=args,
                data=train_data,
                benchmark_curve=train_benchmark.curve,
                benchmark_metrics=train_benchmark.metrics,
                benchmark_display_name=train_benchmark.display_name,
                data_quality=train_data_quality,
                strategy_spec=strategy_spec,
                strategy_payload=strategy_payload,
                run_dir=train_dir / local_run_id,
                run_name=" ".join(run_name_parts),
                parameters=params,
                run_type=run_type,
                run_id=persisted_run_id,
                research_note_path=research_note_path,
            )
        )

    train_rows.sort(key=lambda row: _selection_value(row, args.select_by), reverse=True)
    summary_path = save_sweep_summary(train_rows, train_dir)
    best_row = train_rows[0]
    best_variant = variants_by_run_id[str(best_row["run_id"])]
    return TrainSweepResult(
        rows=train_rows,
        summary_path=summary_path,
        best_row=best_row,
        best_variant=best_variant,
    )


def prepare_sweep_setup(args: argparse.Namespace) -> SweepSetup:
    base_payload = load_strategy_payload(args.strategy)
    param_sweeps = parse_param_sweeps(args.param)
    variants = build_sweep_variants(base_payload, param_sweeps)
    data = pd.read_csv(args.data)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    note = load_research_note(args)
    research_note_path = save_research_note(note, output_dir) if note is not None else None
    return SweepSetup(
        variants=variants,
        data=data,
        output_dir=output_dir,
        research_note_path=research_note_path,
    )


def split_train_test_data(data: pd.DataFrame, train_end: str, test_start: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "date" not in data.columns:
        raise ValueError("train/test split requires a date column.")
    train_end_date = pd.Timestamp(train_end)
    test_start_date = pd.Timestamp(test_start)
    if train_end_date >= test_start_date:
        raise ValueError("--train-end must be earlier than --test-start.")

    dates = pd.to_datetime(data["date"])
    # Keep the two samples disjoint: the train set is used to choose a
    # parameter variant, and the test set is reserved for the selected variant.
    train_data = data.loc[dates <= train_end_date].copy()
    test_data = data.loc[dates >= test_start_date].copy()
    if train_data.empty:
        raise ValueError("train split is empty.")
    if test_data.empty:
        raise ValueError("test split is empty.")
    return train_data, test_data


def parse_walk_forward_windows(raw_windows: Sequence[str]) -> list[dict[str, str]]:
    if not raw_windows:
        raise ValueError("At least one --walk-forward-window is required.")

    windows: list[dict[str, str]] = []
    previous_test_end: pd.Timestamp | None = None
    for index, raw_window in enumerate(raw_windows, start=1):
        parts = [part.strip() for part in raw_window.split(",")]
        if len(parts) != 4 or any(not part for part in parts):
            raise ValueError(
                "--walk-forward-window must use train_start,train_end,test_start,test_end format."
            )
        train_start, train_end, test_start, test_end = parts
        train_start_date = pd.Timestamp(train_start)
        train_end_date = pd.Timestamp(train_end)
        test_start_date = pd.Timestamp(test_start)
        test_end_date = pd.Timestamp(test_end)
        if train_start_date > train_end_date:
            raise ValueError(f"walk-forward window {index} train_start must be on or before train_end.")
        if test_start_date > test_end_date:
            raise ValueError(f"walk-forward window {index} test_start must be on or before test_end.")
        if train_end_date >= test_start_date:
            raise ValueError(f"walk-forward window {index} train_end must be earlier than test_start.")
        if previous_test_end is not None and test_start_date <= previous_test_end:
            raise ValueError("walk-forward test windows must be provided in increasing, non-overlapping order.")
        previous_test_end = test_end_date
        windows.append(
            {
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
            }
        )
    return windows


def slice_date_range_data(data: pd.DataFrame, start: str, end: str, label: str) -> pd.DataFrame:
    if "date" not in data.columns:
        raise ValueError("walk-forward windows require a date column.")
    dates = pd.to_datetime(data["date"])
    sliced = data.loc[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))].copy()
    if sliced.empty:
        raise ValueError(f"{label} window is empty: {start} to {end}.")
    if len(sliced) < 2:
        raise ValueError(f"{label} window must contain at least two rows: {start} to {end}.")
    return sliced


def _selection_value(row: SweepSummaryRow, select_by: str) -> float:
    value = row.get(select_by)
    if value is None:
        return float("-inf")
    return float(value)


def save_train_test_research_summary(
    *,
    args: argparse.Namespace,
    train_rows: Sequence[SweepSummaryRow],
    test_row: SweepSummaryRow,
    output_dir: str | Path,
    train_summary_path: str,
    test_summary_path: str,
) -> str:
    destination = Path(output_dir)
    research_path = destination / "research.md"
    best_train = train_rows[0]
    experiment_line = _experiment_summary_line(args)
    research_path.write_text(
        f"""# Train/Test Sweep Research Summary

## Split

- Train end: `{args.train_end}`
- Test start: `{args.test_start}`
- Selection metric: `{args.select_by}`
- Benchmark: `{args.benchmark}`
{experiment_line}

## Artifacts

- Train summary: `{train_summary_path}`
- Test summary: `{test_summary_path}`
- Selected train run: `{best_train['run_id']}`
- Test output directory: `{test_row['output_dir']}`
{research_note_summary_line(args, output_dir)}

## Results

- Selected train {args.select_by}: {float(_selection_value(best_train, args.select_by)):.4f}
- Selected train total return: {float(best_train['total_return']):.2%}
- Test total return: {float(test_row['total_return']):.2%}
- Test excess total return: {float(test_row['excess_total_return']):.2%}

## Skeptic Pass

- Treat the test result as a guardrail, not proof of an edge.
- Check whether the selected train parameters are near other strong train runs.
- Compare test excess return against the same-period benchmark.
- Re-run promising ideas on a different symbol or date range.
""",
        encoding="utf-8",
    )
    return str(research_path)


def parse_param_sweeps(raw_params: Sequence[str]) -> list[tuple[str, list[str | int | float]]]:
    if not raw_params:
        raise ValueError("At least one --param is required for sweep.")

    parsed: list[tuple[str, list[str | int | float]]] = []
    for raw_param in raw_params:
        if "=" not in raw_param:
            raise ValueError(f"Invalid --param '{raw_param}'. Expected path=value1,value2.")
        path, raw_values = raw_param.split("=", 1)
        path = path.strip()
        values = [_coerce_param_value(value.strip()) for value in raw_values.split(",") if value.strip()]
        if not path:
            raise ValueError("Parameter path must not be empty.")
        if not values:
            raise ValueError(f"Parameter '{path}' must include at least one value.")
        parsed.append((path, values))
    return parsed


def build_sweep_variants(
    base_payload: dict,
    param_sweeps: Sequence[tuple[str, Sequence[str | int | float]]],
) -> list[dict]:
    paths = [path for path, _ in param_sweeps]
    value_lists = [values for _, values in param_sweeps]
    variants: list[dict] = []

    # itertools.product is Python's standard way to ask for every combination:
    # with [5, 10] and [30, 50], it yields (5, 30), (5, 50), (10, 30), (10, 50).
    for combination in itertools.product(*value_lists):
        payload = copy.deepcopy(base_payload)
        params = dict(zip(paths, combination))
        for path, value in params.items():
            apply_strategy_override(payload, path, value)
        parse_strategy(payload)
        variants.append({"payload": payload, "params": params})
    return variants


def apply_strategy_override(payload: dict, path: str, value: str | int | float) -> None:
    path_parts = path.split(".")
    if len(path_parts) != 3 or path_parts[1] != "inputs":
        raise ValueError(
            "Only indicator input overrides are supported in v1 sweeps, "
            "for example sma_20.inputs.length=5,10."
        )

    indicator_id, _, input_key = path_parts
    for indicator in payload.get("indicators", []):
        if indicator.get("id") == indicator_id:
            indicator.setdefault("inputs", {})[input_key] = value
            return

    raise ValueError(f"Unknown indicator id in parameter path: {indicator_id}")


def save_sweep_summary(rows: Sequence[SweepSummaryRow], output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary_path = destination / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SWEEP_SUMMARY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(row.to_dict() for row in rows)
    return str(summary_path)


def build_walk_forward_summary_row(
    *,
    window_id: str,
    window: dict[str, str],
    best_train: SweepSummaryRow,
    test_row: SweepSummaryRow,
    train_summary_path: str,
    test_summary_path: str,
) -> WalkForwardSummaryRow:
    return WalkForwardSummaryRow(
        window_id=window_id,
        train_start=window["train_start"],
        train_end=window["train_end"],
        test_start=window["test_start"],
        test_end=window["test_end"],
        selected_train_run_id=str(best_train["run_id"]),
        selected_train_params=public_params_json(str(best_train["params"])),
        selected_train_total_return=float(best_train["total_return"]),
        selected_train_sharpe_ratio=best_train["sharpe_ratio"],
        test_run_id=str(test_row["run_id"]),
        test_total_return=float(test_row["total_return"]),
        test_excess_total_return=float(test_row["excess_total_return"]),
        test_sharpe_ratio=test_row["sharpe_ratio"],
        test_trade_count=int(test_row["trade_count"]),
        train_summary_path=train_summary_path,
        test_summary_path=test_summary_path,
        test_output_dir=str(test_row["output_dir"]),
    )


def public_params_json(raw_params: str) -> str:
    params = json.loads(raw_params)
    if not isinstance(params, dict):
        return raw_params
    public_params = {key: value for key, value in params.items() if not str(key).startswith("_")}
    return json.dumps(public_params, sort_keys=True)


def save_walk_forward_summary(
    rows: Sequence[WalkForwardSummaryRow],
    output_dir: str | Path,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary_path = destination / "walk_forward_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WALK_FORWARD_SUMMARY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(row.to_dict() for row in rows)
    return str(summary_path)


def save_walk_forward_research_summary(
    args: argparse.Namespace,
    rows: Sequence[WalkForwardSummaryRow],
    output_dir: str | Path,
    summary_path: str,
) -> str:
    destination = Path(output_dir)
    research_path = destination / "research.md"
    experiment_line = _experiment_summary_line(args)
    window_lines = "\n".join(
        (
            f"| `{row['window_id']}` | {row['train_start']} to {row['train_end']} | "
            f"{row['test_start']} to {row['test_end']} | `{row['selected_train_run_id']}` | "
            f"{float(row['selected_train_total_return']):.2%} | "
            f"{float(row['test_total_return']):.2%} | "
            f"{float(row['test_excess_total_return']):.2%} | "
            f"{int(row['test_trade_count'])} |"
        )
        for row in rows
    )
    research_path.write_text(
        f"""# Walk-Forward Research Summary

## Inputs

- Strategy: `{args.strategy}`
- Data: `{args.data}`
- Selection metric: `{args.select_by}`
- Benchmark: `{args.benchmark}`
{experiment_line}
- Windows: {len(rows)}
- Summary: `{summary_path}`
{research_note_summary_line(args, output_dir)}

## Window Results

| Window | Train | Test | Selected Train Run | Train Return | Test Return | Test Excess Return | Test Trades |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
{window_lines}

## Skeptic Pass

- Treat this as repeated out-of-sample evidence, not proof of an edge.
- Do not move window dates after seeing the results.
- Check whether the same parameter region is selected repeatedly.
- Check whether test excess return is consistent across windows.
""",
        encoding="utf-8",
    )
    return str(research_path)


def save_research_summary(
    args: argparse.Namespace,
    rows: Sequence[SweepSummaryRow],
    output_dir: str | Path,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    research_path = destination / "research.md"
    git_commit = current_git_commit()
    experiment_line = _experiment_summary_line(args)
    benchmark_total_return = rows[0].get("benchmark_total_return") if rows else None
    best = rows[0] if rows else None
    best_lines = ""
    if best:
        best_lines = (
            f"- Best run by total return: `{best['run_id']}`\n"
            f"- Best total return: {float(best['total_return']):.2%}\n"
            f"- Best excess total return: {float(best['excess_total_return']):.2%}\n"
            f"- Best run params: `{best['params']}`\n"
        )
    benchmark_lines = ""
    if benchmark_total_return is not None:
        benchmark_lines = f"- Benchmark `{args.benchmark}` total return: {float(benchmark_total_return):.2%}\n"
    note_lines = ""
    if getattr(args, "note", None) is not None or getattr(args, "note_file", None) is not None:
        note_lines = f"- Research note: `{destination / 'research_note.md'}`\n"

    param_lines = "\n".join(f"- `{raw_param}`" for raw_param in args.param)
    command_lines = "\n".join(
        [
            "quant-lab sweep \\",
            f"  --strategy {args.strategy} \\",
            f"  --data {args.data} \\",
            *[f"  --param {raw_param} \\" for raw_param in args.param],
            f"  --sizing {args.sizing} \\",
            f"  --allocation {args.allocation} \\",
            f"  --benchmark {args.benchmark} \\",
            f"  --cost-preset {args.cost_assumptions.preset} \\",
            f"  --commission-fixed {args.cost_assumptions.commission_fixed} \\",
            f"  --commission-rate {args.cost_assumptions.commission_rate} \\",
            f"  --slippage-bps {args.cost_assumptions.slippage_bps} \\",
            *note_command_lines(args),
            f"  --out {args.out}",
        ]
    )
    research_path.write_text(
        f"""# Sweep Research Summary

## Command Used

```bash
{command_lines}
```

## Inputs

- Strategy: `{args.strategy}`
- Data: `{args.data}`
- Initial cash: `{args.initial_cash}`
- Quantity: `{args.quantity}`
- Sizing: `{args.sizing}`
- Allocation: `{args.allocation}`
- Benchmark: `{args.benchmark}`
- Git commit: `{git_commit}`
{experiment_line}
- Cost preset: `{args.cost_assumptions.preset}`
- Commission fixed: `{args.cost_assumptions.commission_fixed}`
- Commission rate: `{args.cost_assumptions.commission_rate}`
- Slippage bps: `{args.cost_assumptions.slippage_bps}`
{note_lines}

## Parameters

{param_lines}

## Results

- Runs: {len(rows)}
{benchmark_lines}
{best_lines}
{format_sweep_analysis_section(rows)}

## Skeptic Pass

- Check whether the best result is supported by enough trades.
- Check whether nearby parameter values are also strong.
- Treat `isolated` or `grid_too_sparse` stability as a reason to run a tighter follow-up grid.
- Compare excess return against buy-and-hold before treating a result as useful.
- Re-run promising variants on a longer or different sample before trusting them.
""",
        encoding="utf-8",
    )
    return str(research_path)


def _coerce_param_value(raw_value: str) -> str | int | float:
    try:
        return int(raw_value)
    except ValueError:
        pass
    try:
        return float(raw_value)
    except ValueError:
        return raw_value


def _experiment_summary_line(args: argparse.Namespace) -> str:
    experiment_id = getattr(args, "experiment_id", None)
    if not experiment_id:
        return ""
    return f"- Experiment: `{experiment_id}`"
