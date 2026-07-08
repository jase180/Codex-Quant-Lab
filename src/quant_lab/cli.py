"""Command-line interface for Codex Quant Lab."""

from __future__ import annotations

import argparse
import copy
import csv
import itertools
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

import pandas as pd

from backtester_core import (
    BacktestEngine,
    ExecutionModel,
    TransactionCostModel,
    build_run_report,
    equity_curve_from_result,
    save_run_report_artifacts,
    summarize_run_metrics,
)
from metrics_reporting import save_drawdown_chart, save_equity_curve_chart

from .benchmarks import (
    append_benchmark_section,
    benchmark_summary_fields,
    build_benchmark,
    excess_total_return,
)
from .costs import COST_PRESETS, CostAssumptions, resolve_cost_assumptions
from .data_fetch import fetch_market_data, write_market_data_csv
from .data_quality import (
    append_data_quality_section,
    build_data_quality_report,
    save_data_quality_report,
)
from .research_index import append_research_index_record, build_run_index_record, format_index_csv
from .research_index import filter_index_records, format_index_table, load_research_index, sort_index_records
from .research_warnings import (
    append_research_warnings_section,
    build_research_warnings,
    save_research_warnings,
)
from .run_inspection import format_run_comparison, format_run_summary, load_run_summaries, load_run_summary
from .rule_based_strategy import build_rule_based_strategy
from .run_metadata import (
    BenchmarkMetadata,
    CostMetadata,
    DataMetadata,
    EnvironmentMetadata,
    RunMetadata,
    SizingMetadata,
    StrategyMetadata,
    command_tokens,
    save_run_metadata,
)
from .strategy_schema import load_strategy, parse_strategy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quant-lab",
        description="Run Codex Quant Lab backtests and research workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one strategy against one OHLCV CSV.")
    run_parser.add_argument("--strategy", required=True, help="Path to a v1 strategy JSON file.")
    run_parser.add_argument("--data", required=True, help="Path to a daily OHLCV CSV file.")
    run_parser.add_argument("--out", required=True, help="Directory where run artifacts are written.")
    run_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash. Defaults to 100000.",
    )
    run_parser.add_argument(
        "--quantity",
        type=float,
        default=1,
        help="Order quantity for fixed-shares sizing. Defaults to 1.",
    )
    run_parser.add_argument(
        "--sizing",
        choices=["fixed-shares", "percent-equity"],
        default="fixed-shares",
        help="Position sizing mode. Defaults to fixed-shares.",
    )
    run_parser.add_argument(
        "--allocation",
        type=float,
        default=1.0,
        help="Cash fraction to invest for percent-equity buys. Defaults to 1.0.",
    )
    run_parser.add_argument(
        "--run-name",
        default=None,
        help="Report title. Defaults to the strategy name.",
    )
    add_cost_arguments(run_parser)
    add_benchmark_argument(run_parser)
    add_index_argument(run_parser)
    run_parser.set_defaults(func=run_command)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch daily market data into the local CSV cache.",
    )
    fetch_parser.add_argument("--symbol", required=True, help="Ticker symbol, such as SPY or QQQ.")
    fetch_parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format.")
    fetch_parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format.")
    fetch_parser.add_argument(
        "--out",
        default="data/cache",
        help="Directory where the normalized OHLCV CSV is written. Defaults to data/cache.",
    )
    fetch_parser.add_argument(
        "--interval",
        default="1d",
        help="Market data interval. Only 1d is supported for now.",
    )
    fetch_parser.set_defaults(func=fetch_command)

    list_parser = subparsers.add_parser(
        "list-runs",
        help="List runs from the local research index.",
    )
    add_index_argument(list_parser)
    list_parser.add_argument("--symbol", default=None, help="Only show runs for one symbol, such as QQQ.")
    list_parser.add_argument("--strategy-id", default=None, help="Only show runs for one strategy id.")
    list_parser.add_argument(
        "--run-type",
        choices=["run", "sweep_run", "train_sweep_run", "test_selected_run"],
        default=None,
        help="Only show one run type.",
    )
    list_parser.add_argument("--csv", action="store_true", help="Print CSV instead of a fixed-width table.")
    list_parser.add_argument(
        "--sort",
        default="created_at_utc",
        choices=[
            "created_at_utc",
            "total_return",
            "benchmark_total_return",
            "excess_total_return",
            "sharpe_ratio",
            "max_drawdown",
            "trade_count",
        ],
        help="Index field to sort by. Defaults to created_at_utc.",
    )
    list_parser.add_argument(
        "--ascending",
        action="store_true",
        help="Sort smallest to largest. Defaults to descending.",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum rows to print. Defaults to 20.",
    )
    list_parser.set_defaults(func=list_runs_command)

    show_parser = subparsers.add_parser(
        "show-run",
        help="Inspect one saved run from run_metadata.json.",
    )
    show_parser.add_argument("--metadata", required=True, help="Path to a run_metadata.json file.")
    show_parser.set_defaults(func=show_run_command)

    compare_parser = subparsers.add_parser(
        "compare-runs",
        help="Compare two or more saved runs from run_metadata.json files.",
    )
    compare_parser.add_argument(
        "--metadata",
        action="append",
        required=True,
        help="Path to a run_metadata.json file. Provide at least two.",
    )
    compare_parser.set_defaults(func=compare_runs_command)

    sweep_parser = subparsers.add_parser(
        "sweep",
        help="Run every combination of strategy parameter overrides.",
    )
    sweep_parser.add_argument("--strategy", required=True, help="Path to a v1 strategy JSON file.")
    sweep_parser.add_argument("--data", required=True, help="Path to a daily OHLCV CSV file.")
    sweep_parser.add_argument("--out", required=True, help="Directory where sweep artifacts are written.")
    sweep_parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="Parameter sweep in path=value1,value2 form, such as sma_20.inputs.length=5,10,20.",
    )
    sweep_parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting portfolio cash. Defaults to 100000.",
    )
    sweep_parser.add_argument(
        "--quantity",
        type=float,
        default=1,
        help="Order quantity for fixed-shares sizing. Defaults to 1.",
    )
    sweep_parser.add_argument(
        "--sizing",
        choices=["fixed-shares", "percent-equity"],
        default="fixed-shares",
        help="Position sizing mode. Defaults to fixed-shares.",
    )
    sweep_parser.add_argument(
        "--allocation",
        type=float,
        default=1.0,
        help="Cash fraction to invest for percent-equity buys. Defaults to 1.0.",
    )
    sweep_parser.add_argument(
        "--run-name",
        default=None,
        help="Report title prefix. Defaults to the strategy name.",
    )
    sweep_parser.add_argument("--train-end", default=None, help="Final train date for train/test sweep mode.")
    sweep_parser.add_argument("--test-start", default=None, help="First test date for train/test sweep mode.")
    sweep_parser.add_argument(
        "--select-by",
        choices=["total_return", "sharpe_ratio"],
        default="total_return",
        help="Metric used to select the train winner for test rerun. Defaults to total_return.",
    )
    add_cost_arguments(sweep_parser)
    add_benchmark_argument(sweep_parser)
    add_index_argument(sweep_parser)
    sweep_parser.set_defaults(func=sweep_command)
    return parser


def add_cost_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cost-preset",
        choices=sorted(COST_PRESETS),
        default="none",
        help="Named transaction cost preset. Explicit cost flags override preset values.",
    )
    parser.add_argument(
        "--commission-fixed",
        type=float,
        default=None,
        help="Flat commission charged per fill. Overrides --cost-preset.",
    )
    parser.add_argument(
        "--commission-rate",
        type=float,
        default=None,
        help="Commission as a decimal fraction of trade notional. Overrides --cost-preset.",
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        default=None,
        help="One-way slippage in basis points. Overrides --cost-preset.",
    )


def add_index_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--index-path",
        default="artifacts/research_index.jsonl",
        help="Append-only JSONL research index path. Defaults to artifacts/research_index.jsonl.",
    )


def add_benchmark_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--benchmark",
        choices=["buy-and-hold", "cash"],
        default="buy-and-hold",
        help="Benchmark used in reports, summaries, charts, and metadata. Defaults to buy-and-hold.",
    )


def run_command(args: argparse.Namespace) -> int:
    args.cost_assumptions = resolve_cli_costs(args)
    strategy_spec = load_strategy(args.strategy)
    strategy = build_rule_based_strategy(
        strategy_spec,
        order_quantity=args.quantity,
        sizing=args.sizing,
        allocation=args.allocation,
    )
    data = pd.read_csv(args.data)
    data_quality = build_data_quality_report(data)

    result = build_engine(args).run(data, strategy)
    run_name = args.run_name or strategy_spec.name
    benchmark = build_benchmark(data, args.initial_cash, args.benchmark)
    report = append_benchmark_section(
        build_run_report(result, run_name=run_name),
        benchmark.metrics,
        result.total_return,
        benchmark.display_name,
    )
    report = append_data_quality_section(report, data_quality)
    artifact_paths = save_run_report_artifacts(result, args.out, run_name=run_name)
    run_metrics = summarize_run_metrics(result)
    research_warnings = build_research_warnings(run_metrics, result.trades)
    report = append_research_warnings_section(report, research_warnings)
    report_path = Path(artifact_paths["report"])
    report_path.write_text(report, encoding="utf-8")
    artifact_paths["trades"] = save_trades(result.trades, args.out)
    artifact_paths.update(save_charts(result, benchmark.curve, args.out, benchmark.display_name))
    artifact_paths["data_quality"] = save_data_quality_report(data_quality, args.out)
    artifact_paths["research_warnings"] = save_research_warnings(research_warnings, args.out)
    artifact_paths["metadata"] = str(Path(args.out) / "run_metadata.json")
    artifact_paths["research_index"] = str(args.index_path)
    metadata = build_run_metadata(
        args=args,
        strategy_spec=strategy_spec,
        data=data,
        run_type="run",
        run_id=None,
        parameters={},
        artifacts=artifact_paths,
    )
    artifact_paths["metadata"] = save_run_metadata(metadata, args.out)
    append_research_index(
        metadata=metadata,
        metrics=run_metrics,
        benchmark_metrics=benchmark.metrics,
        output_dir=args.out,
        trade_count=len(result.trades),
        index_path=args.index_path,
        strategy_total_return=result.total_return,
    )

    print(f"Run complete: {run_name}")
    for artifact_name in sorted(artifact_paths):
        print(f"{artifact_name}: {artifact_paths[artifact_name]}")
    print(f"final_equity: {result.final_equity:.2f}")
    print(f"total_return: {result.total_return:.2%}")
    print(f"benchmark: {benchmark.name}")
    print(f"benchmark_total_return: {benchmark.metrics.total_return:.2%}")
    print(f"excess_total_return: {excess_total_return(result.total_return, benchmark.metrics.total_return):.2%}")
    print(f"cost_preset: {args.cost_assumptions.preset}")
    print(f"commission_fixed: {args.cost_assumptions.commission_fixed}")
    print(f"commission_rate: {args.cost_assumptions.commission_rate}")
    print(f"slippage_bps: {args.cost_assumptions.slippage_bps}")
    return 0


def fetch_command(args: argparse.Namespace) -> int:
    data = fetch_market_data(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        interval=args.interval,
    )
    csv_path = write_market_data_csv(
        data=data,
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        output_dir=args.out,
    )
    print(f"Fetched {len(data)} rows for {args.symbol.upper()}")
    print(f"data: {csv_path}")
    return 0


def list_runs_command(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")

    records = load_research_index(args.index_path)
    records = filter_index_records(
        records,
        symbol=args.symbol,
        strategy_id=args.strategy_id,
        run_type=args.run_type,
    )
    records = sort_index_records(records, args.sort, descending=not args.ascending)
    records = records[: args.limit]

    if not records:
        print(f"No runs found in {args.index_path}")
        return 0

    if args.csv:
        print(format_index_csv(records))
    else:
        print(format_index_table(records))
    return 0


def show_run_command(args: argparse.Namespace) -> int:
    summary = load_run_summary(args.metadata)
    print(format_run_summary(summary))
    return 0


def compare_runs_command(args: argparse.Namespace) -> int:
    summaries = load_run_summaries(args.metadata)
    print(format_run_comparison(summaries))
    return 0


def sweep_command(args: argparse.Namespace) -> int:
    args.cost_assumptions = resolve_cli_costs(args)
    if args.train_end or args.test_start:
        return train_test_sweep_command(args)

    base_payload = load_strategy_payload(args.strategy)
    param_sweeps = parse_param_sweeps(args.param)
    variants = build_sweep_variants(base_payload, param_sweeps)
    data = pd.read_csv(args.data)
    data_quality = build_data_quality_report(data)
    benchmark = build_benchmark(data, args.initial_cash, args.benchmark)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, str | int | float | None]] = []
    for index, variant in enumerate(variants, start=1):
        run_id = f"run_{index:03d}"
        run_dir = output_dir / run_id
        strategy_payload = variant["payload"]
        params = variant["params"]
        strategy_spec = parse_strategy(strategy_payload)
        run_name_prefix = args.run_name or strategy_spec.name
        summary_rows.append(
            run_sweep_variant(
                args=args,
                data=data,
                benchmark_curve=benchmark.curve,
                benchmark_metrics=benchmark.metrics,
                benchmark_display_name=benchmark.display_name,
                data_quality=data_quality,
                strategy_spec=strategy_spec,
                strategy_payload=strategy_payload,
                run_dir=run_dir,
                run_name=f"{run_name_prefix} {run_id}",
                parameters=params,
                run_type="sweep_run",
                run_id=run_id,
            )
        )

    # Sorting after all runs keeps the run directories stable while making the
    # comparison table easy to scan from best to worst total return.
    summary_rows.sort(key=lambda row: float(row["total_return"]), reverse=True)
    summary_path = save_sweep_summary(summary_rows, output_dir)
    research_path = save_research_summary(args, summary_rows, output_dir)

    print(f"Sweep complete: {len(summary_rows)} runs")
    print(f"summary: {summary_path}")
    print(f"research: {research_path}")
    if summary_rows:
        best = summary_rows[0]
        print(f"best_run: {best['run_id']}")
        print(f"best_total_return: {float(best['total_return']):.2%}")
        print(f"best_excess_total_return: {float(best['excess_total_return']):.2%}")
    return 0


def train_test_sweep_command(args: argparse.Namespace) -> int:
    if not args.train_end or not args.test_start:
        raise ValueError("--train-end and --test-start must be provided together.")

    base_payload = load_strategy_payload(args.strategy)
    param_sweeps = parse_param_sweeps(args.param)
    variants = build_sweep_variants(base_payload, param_sweeps)
    data = pd.read_csv(args.data)
    train_data, test_data = split_train_test_data(data, args.train_end, args.test_start)
    output_dir = Path(args.out)
    train_dir = output_dir / "train_sweep"
    test_dir = output_dir / "test_selected"
    output_dir.mkdir(parents=True, exist_ok=True)

    train_benchmark = build_benchmark(train_data, args.initial_cash, args.benchmark)
    train_data_quality = build_data_quality_report(train_data)
    train_rows: list[dict[str, str | int | float | None]] = []
    variants_by_run_id: dict[str, dict] = {}

    for index, variant in enumerate(variants, start=1):
        run_id = f"run_{index:03d}"
        variants_by_run_id[run_id] = variant
        strategy_payload = variant["payload"]
        params = {
            **variant["params"],
            "_split_phase": "train",
            "_train_end": args.train_end,
            "_test_start": args.test_start,
            "_select_by": args.select_by,
        }
        strategy_spec = parse_strategy(strategy_payload)
        run_name_prefix = args.run_name or strategy_spec.name
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
                run_dir=train_dir / run_id,
                run_name=f"{run_name_prefix} train {run_id}",
                parameters=params,
                run_type="train_sweep_run",
                run_id=run_id,
            )
        )

    train_rows.sort(key=lambda row: _selection_value(row, args.select_by), reverse=True)
    train_summary_path = save_sweep_summary(train_rows, train_dir)
    best_train = train_rows[0]
    best_variant = variants_by_run_id[str(best_train["run_id"])]

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
    )
    test_summary_path = save_sweep_summary([test_row], output_dir / "test_summary")
    research_path = save_train_test_research_summary(
        args=args,
        train_rows=train_rows,
        test_row=test_row,
        output_dir=output_dir,
        train_summary_path=train_summary_path,
        test_summary_path=test_summary_path,
    )

    print(f"Train/test sweep complete: {len(train_rows)} train runs")
    print(f"train_summary: {train_summary_path}")
    print(f"test_summary: {test_summary_path}")
    print(f"research: {research_path}")
    print(f"selected_train_run: {best_train['run_id']}")
    print(f"selected_train_{args.select_by}: {_selection_value(best_train, args.select_by):.4f}")
    print(f"test_total_return: {float(test_row['total_return']):.2%}")
    return 0


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


def _selection_value(row: dict[str, str | int | float | None], select_by: str) -> float:
    value = row.get(select_by)
    if value is None:
        return float("-inf")
    return float(value)


def save_train_test_research_summary(
    *,
    args: argparse.Namespace,
    train_rows: Sequence[dict[str, str | int | float | None]],
    test_row: dict[str, str | int | float | None],
    output_dir: str | Path,
    train_summary_path: str,
    test_summary_path: str,
) -> str:
    destination = Path(output_dir)
    research_path = destination / "research.md"
    best_train = train_rows[0]
    research_path.write_text(
        f"""# Train/Test Sweep Research Summary

## Split

- Train end: `{args.train_end}`
- Test start: `{args.test_start}`
- Selection metric: `{args.select_by}`
- Benchmark: `{args.benchmark}`

## Artifacts

- Train summary: `{train_summary_path}`
- Test summary: `{test_summary_path}`
- Selected train run: `{best_train['run_id']}`
- Test output directory: `{test_row['output_dir']}`

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


def run_sweep_variant(
    *,
    args: argparse.Namespace,
    data: pd.DataFrame,
    benchmark_curve,
    benchmark_metrics,
    benchmark_display_name: str,
    data_quality,
    strategy_spec,
    strategy_payload: dict,
    run_dir: Path,
    run_name: str,
    parameters: dict[str, str | int | float],
    run_type: str,
    run_id: str,
) -> dict[str, str | int | float | None]:
    strategy = build_rule_based_strategy(
        strategy_spec,
        order_quantity=args.quantity,
        sizing=args.sizing,
        allocation=args.allocation,
    )
    result = build_engine(args).run(data, strategy)
    metrics = summarize_run_metrics(result)
    research_warnings = build_research_warnings(metrics, result.trades)
    report = append_benchmark_section(
        build_run_report(result, run_name=run_name),
        benchmark_metrics,
        result.total_return,
        benchmark_display_name,
    )
    report = append_data_quality_section(report, data_quality)
    report = append_research_warnings_section(report, research_warnings)
    artifact_paths = save_run_report_artifacts(result, run_dir, run_name=run_name)
    Path(artifact_paths["report"]).write_text(report, encoding="utf-8")
    artifact_paths["trades"] = save_trades(result.trades, run_dir)
    artifact_paths.update(save_charts(result, benchmark_curve, run_dir, benchmark_display_name))
    artifact_paths["data_quality"] = save_data_quality_report(data_quality, run_dir)
    artifact_paths["research_warnings"] = save_research_warnings(research_warnings, run_dir)
    artifact_paths["strategy"] = save_strategy_payload(strategy_payload, run_dir)
    artifact_paths["metadata"] = str(run_dir / "run_metadata.json")
    artifact_paths["research_index"] = str(args.index_path)
    metadata = build_run_metadata(
        args=args,
        strategy_spec=strategy_spec,
        data=data,
        run_type=run_type,
        run_id=run_id,
        parameters=parameters,
        artifacts=artifact_paths,
    )
    artifact_paths["metadata"] = save_run_metadata(metadata, run_dir)
    append_research_index(
        metadata=metadata,
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        output_dir=run_dir,
        trade_count=len(result.trades),
        index_path=args.index_path,
        strategy_total_return=result.total_return,
    )

    return build_summary_row(
        run_id=run_id,
        strategy_id=strategy_spec.strategy_id,
        params=parameters,
        result=result,
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        output_dir=run_dir,
        args=args,
    )


def build_summary_row(
    *,
    run_id: str,
    strategy_id: str,
    params: dict[str, str | int | float],
    result,
    metrics,
    benchmark_metrics,
    output_dir: str | Path,
    args: argparse.Namespace,
) -> dict[str, str | int | float | None]:
    return {
        "run_id": run_id,
        "strategy_id": strategy_id,
        "params": json.dumps(params, sort_keys=True),
        "final_equity": result.final_equity,
        "total_return": result.total_return,
        "cagr": metrics.cagr,
        "sharpe_ratio": metrics.sharpe_ratio,
        "max_drawdown": metrics.max_drawdown,
        "trade_count": len(result.trades),
        "sizing": args.sizing,
        "quantity": args.quantity,
        "allocation": args.allocation,
        "cost_preset": args.cost_assumptions.preset,
        "commission_fixed": args.cost_assumptions.commission_fixed,
        "commission_rate": args.cost_assumptions.commission_rate,
        "slippage_bps": args.cost_assumptions.slippage_bps,
        **benchmark_summary_fields(args.benchmark, benchmark_metrics),
        "excess_total_return": excess_total_return(
            result.total_return,
            benchmark_metrics.total_return,
        ),
        "output_dir": str(output_dir),
    }


def build_engine(args: argparse.Namespace) -> BacktestEngine:
    cost_assumptions = args.cost_assumptions
    cost_model = TransactionCostModel(
        commission_fixed=cost_assumptions.commission_fixed,
        commission_rate=cost_assumptions.commission_rate,
        slippage_bps=cost_assumptions.slippage_bps,
    )
    return BacktestEngine(
        initial_cash=args.initial_cash,
        execution_model=ExecutionModel(cost_model=cost_model),
    )


def resolve_cli_costs(args: argparse.Namespace) -> CostAssumptions:
    return resolve_cost_assumptions(
        cost_preset=args.cost_preset,
        commission_fixed=args.commission_fixed,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
    )


def append_research_index(
    *,
    metadata: RunMetadata,
    metrics,
    benchmark_metrics,
    output_dir: str | Path,
    trade_count: int,
    index_path: str | Path,
    strategy_total_return: float,
) -> str:
    record = build_run_index_record(
        metadata=metadata,
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        excess_return=excess_total_return(strategy_total_return, benchmark_metrics.total_return),
        trade_count=trade_count,
        output_dir=output_dir,
    )
    return append_research_index_record(record, index_path)


def build_run_metadata(
    *,
    args: argparse.Namespace,
    strategy_spec,
    data: pd.DataFrame,
    run_type: str,
    run_id: str | None,
    parameters: dict[str, str | int | float],
    artifacts: dict[str, str],
) -> RunMetadata:
    if "date" in data.columns and not data.empty:
        data_dates = pd.to_datetime(data["date"])
    else:
        data_dates = pd.Series(dtype="datetime64[ns]")
    metadata = RunMetadata(
        metadata_schema_version="run_metadata.v1",
        run_type=run_type,
        run_id=run_id,
        created_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        command=list(args.command_tokens),
        strategy=StrategyMetadata(
            strategy_id=strategy_spec.strategy_id,
            name=strategy_spec.name,
            schema_version=strategy_spec.schema_version,
            strategy_type=strategy_spec.strategy_type,
        ),
        data=DataMetadata(
            path=str(args.data),
            row_count=int(len(data)),
            start=_metadata_date(data_dates.min()) if not data_dates.empty else None,
            end=_metadata_date(data_dates.max()) if not data_dates.empty else None,
            symbol=strategy_spec.market.symbol,
            timeframe=strategy_spec.market.timeframe,
        ),
        sizing=SizingMetadata(
            mode=args.sizing,
            initial_cash=float(args.initial_cash),
            quantity=float(args.quantity),
            allocation=float(args.allocation),
        ),
        costs=CostMetadata(
            preset=args.cost_assumptions.preset,
            commission_fixed=float(args.cost_assumptions.commission_fixed),
            commission_rate=float(args.cost_assumptions.commission_rate),
            slippage_bps=float(args.cost_assumptions.slippage_bps),
        ),
        benchmark=BenchmarkMetadata(
            name=args.benchmark,
            display_name=args.benchmark.replace("-", " ").title(),
        ),
        environment=EnvironmentMetadata(git_commit=current_git_commit()),
        parameters=dict(parameters),
    )
    return metadata.with_artifacts(artifacts)


def _metadata_date(value: pd.Timestamp) -> str:
    return value.date().isoformat()


def save_trades(trades: pd.DataFrame, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    trades_path = destination / "trades.csv"
    trades.to_csv(trades_path)
    return str(trades_path)


def save_charts(
    result,
    benchmark_curve,
    output_dir: str | Path,
    benchmark_display_name: str,
) -> dict[str, str]:
    destination = Path(output_dir)
    strategy_curve = equity_curve_from_result(result)
    return {
        "equity_chart": save_equity_curve_chart(
            strategy_curve,
            benchmark_curve,
            destination / "equity_curve.png",
            benchmark_display_name,
        ),
        "drawdown_chart": save_drawdown_chart(
            strategy_curve,
            benchmark_curve,
            destination / "drawdown.png",
            benchmark_display_name,
        ),
    }


def load_strategy_payload(strategy_path: str | Path) -> dict:
    path = Path(strategy_path)
    return json.loads(path.read_text(encoding="utf-8"))


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


def save_strategy_payload(strategy_payload: dict, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    strategy_path = destination / "strategy.json"
    strategy_path.write_text(
        json.dumps(strategy_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(strategy_path)


def save_sweep_summary(rows: Sequence[dict[str, str | int | float | None]], output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary_path = destination / "summary.csv"
    fieldnames = [
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
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return str(summary_path)


def save_research_summary(
    args: argparse.Namespace,
    rows: Sequence[dict[str, str | int | float | None]],
    output_dir: str | Path,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    research_path = destination / "research.md"
    benchmark_total_return = rows[0].get("benchmark_total_return") if rows else None
    best = rows[0] if rows else None
    git_commit = current_git_commit()
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

    param_lines = "\n".join(f"- `{raw_param}`" for raw_param in args.param)
    command_lines = "\n".join(
        [
            "quant-lab sweep \\",
            f"  --strategy {args.strategy} \\",
            f"  --data {args.data} \\",
            *[f"  --param {raw_param} \\" for raw_param in args.param],
            f"  --sizing {args.sizing} \\",
            f"  --allocation {args.allocation} \\",
            f"  --cost-preset {args.cost_assumptions.preset} \\",
            f"  --commission-fixed {args.cost_assumptions.commission_fixed} \\",
            f"  --commission-rate {args.cost_assumptions.commission_rate} \\",
            f"  --slippage-bps {args.cost_assumptions.slippage_bps} \\",
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
- Cost preset: `{args.cost_assumptions.preset}`
- Commission fixed: `{args.cost_assumptions.commission_fixed}`
- Commission rate: `{args.cost_assumptions.commission_rate}`
- Slippage bps: `{args.cost_assumptions.slippage_bps}`
- Git commit: `{git_commit}`

## Parameters

{param_lines}

## Results

- Runs: {len(rows)}
{benchmark_lines}
{best_lines}
## Skeptic Pass

- Check whether the best result is supported by enough trades.
- Check whether nearby parameter values are also strong.
- Compare excess return against buy-and-hold before treating a result as useful.
- Re-run promising variants on a longer or different sample before trusting them.
""",
        encoding="utf-8",
    )
    return str(research_path)


def current_git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip()


def _coerce_param_value(raw_value: str) -> str | int | float:
    try:
        return int(raw_value)
    except ValueError:
        pass
    try:
        return float(raw_value)
    except ValueError:
        return raw_value


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(raw_argv)
    args.command_tokens = command_tokens("quant-lab", raw_argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
