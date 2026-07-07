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
    buy_and_hold_equity_curve,
    buy_and_hold_metrics,
    excess_total_return,
)
from .data_fetch import fetch_market_data, write_market_data_csv
from .research_index import append_research_index_record, build_run_index_record
from .research_index import filter_index_records, format_index_table, load_research_index, sort_index_records
from .run_inspection import format_run_summary, load_run_summary
from .rule_based_strategy import build_rule_based_strategy
from .run_metadata import (
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
    add_cost_arguments(sweep_parser)
    add_index_argument(sweep_parser)
    sweep_parser.set_defaults(func=sweep_command)
    return parser


def add_cost_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--commission-fixed",
        type=float,
        default=0.0,
        help="Flat commission charged per fill. Defaults to 0.",
    )
    parser.add_argument(
        "--commission-rate",
        type=float,
        default=0.0,
        help="Commission as a decimal fraction of trade notional. Defaults to 0.",
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        default=0.0,
        help="One-way slippage in basis points. Defaults to 0.",
    )


def add_index_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--index-path",
        default="artifacts/research_index.jsonl",
        help="Append-only JSONL research index path. Defaults to artifacts/research_index.jsonl.",
    )


def run_command(args: argparse.Namespace) -> int:
    strategy_spec = load_strategy(args.strategy)
    strategy = build_rule_based_strategy(
        strategy_spec,
        order_quantity=args.quantity,
        sizing=args.sizing,
        allocation=args.allocation,
    )
    data = pd.read_csv(args.data)

    result = build_engine(args).run(data, strategy)
    run_name = args.run_name or strategy_spec.name
    benchmark_curve = buy_and_hold_equity_curve(data, args.initial_cash)
    benchmark_metrics = buy_and_hold_metrics(data, args.initial_cash)
    report = append_benchmark_section(
        build_run_report(result, run_name=run_name),
        benchmark_metrics,
        result.total_return,
    )
    artifact_paths = save_run_report_artifacts(result, args.out, run_name=run_name)
    run_metrics = summarize_run_metrics(result)
    report_path = Path(artifact_paths["report"])
    report_path.write_text(report, encoding="utf-8")
    artifact_paths["trades"] = save_trades(result.trades, args.out)
    artifact_paths.update(save_charts(result, benchmark_curve, args.out))
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
        benchmark_metrics=benchmark_metrics,
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
    print(f"benchmark_total_return: {benchmark_metrics.total_return:.2%}")
    print(f"excess_total_return: {excess_total_return(result.total_return, benchmark_metrics.total_return):.2%}")
    print(f"commission_fixed: {args.commission_fixed}")
    print(f"commission_rate: {args.commission_rate}")
    print(f"slippage_bps: {args.slippage_bps}")
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
    records = filter_index_records(records, symbol=args.symbol)
    records = sort_index_records(records, args.sort, descending=not args.ascending)
    records = records[: args.limit]

    if not records:
        print(f"No runs found in {args.index_path}")
        return 0

    print(format_index_table(records))
    return 0


def show_run_command(args: argparse.Namespace) -> int:
    summary = load_run_summary(args.metadata)
    print(format_run_summary(summary))
    return 0


def sweep_command(args: argparse.Namespace) -> int:
    base_payload = load_strategy_payload(args.strategy)
    param_sweeps = parse_param_sweeps(args.param)
    variants = build_sweep_variants(base_payload, param_sweeps)
    data = pd.read_csv(args.data)
    benchmark_curve = buy_and_hold_equity_curve(data, args.initial_cash)
    benchmark_metrics = buy_and_hold_metrics(data, args.initial_cash)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, str | int | float | None]] = []
    for index, variant in enumerate(variants, start=1):
        run_id = f"run_{index:03d}"
        run_dir = output_dir / run_id
        strategy_payload = variant["payload"]
        params = variant["params"]
        strategy_spec = parse_strategy(strategy_payload)
        strategy = build_rule_based_strategy(
            strategy_spec,
            order_quantity=args.quantity,
            sizing=args.sizing,
            allocation=args.allocation,
        )

        result = build_engine(args).run(data, strategy)
        metrics = summarize_run_metrics(result)
        run_name_prefix = args.run_name or strategy_spec.name
        report = append_benchmark_section(
            build_run_report(result, run_name=f"{run_name_prefix} {run_id}"),
            benchmark_metrics,
            result.total_return,
        )
        artifact_paths = save_run_report_artifacts(result, run_dir, run_name=f"{run_name_prefix} {run_id}")
        Path(artifact_paths["report"]).write_text(report, encoding="utf-8")
        artifact_paths["trades"] = save_trades(result.trades, run_dir)
        artifact_paths.update(save_charts(result, benchmark_curve, run_dir))
        artifact_paths["strategy"] = save_strategy_payload(strategy_payload, run_dir)
        artifact_paths["metadata"] = str(run_dir / "run_metadata.json")
        artifact_paths["research_index"] = str(args.index_path)
        metadata = build_run_metadata(
            args=args,
            strategy_spec=strategy_spec,
            data=data,
            run_type="sweep_run",
            run_id=run_id,
            parameters=params,
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

        summary_rows.append(
            {
                "run_id": run_id,
                "strategy_id": strategy_spec.strategy_id,
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
                "commission_fixed": args.commission_fixed,
                "commission_rate": args.commission_rate,
                "slippage_bps": args.slippage_bps,
                **benchmark_summary_fields(benchmark_metrics),
                "excess_total_return": excess_total_return(
                    result.total_return,
                    benchmark_metrics.total_return,
                ),
                "output_dir": str(run_dir),
            }
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


def build_engine(args: argparse.Namespace) -> BacktestEngine:
    cost_model = TransactionCostModel(
        commission_fixed=args.commission_fixed,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
    )
    return BacktestEngine(
        initial_cash=args.initial_cash,
        execution_model=ExecutionModel(cost_model=cost_model),
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
            commission_fixed=float(args.commission_fixed),
            commission_rate=float(args.commission_rate),
            slippage_bps=float(args.slippage_bps),
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


def save_charts(result, benchmark_curve, output_dir: str | Path) -> dict[str, str]:
    destination = Path(output_dir)
    strategy_curve = equity_curve_from_result(result)
    return {
        "equity_chart": save_equity_curve_chart(
            strategy_curve,
            benchmark_curve,
            destination / "equity_curve.png",
        ),
        "drawdown_chart": save_drawdown_chart(
            strategy_curve,
            benchmark_curve,
            destination / "drawdown.png",
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
        "commission_fixed",
        "commission_rate",
        "slippage_bps",
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
        benchmark_lines = f"- Buy-and-hold total return: {float(benchmark_total_return):.2%}\n"

    param_lines = "\n".join(f"- `{raw_param}`" for raw_param in args.param)
    command_lines = "\n".join(
        [
            "quant-lab sweep \\",
            f"  --strategy {args.strategy} \\",
            f"  --data {args.data} \\",
            *[f"  --param {raw_param} \\" for raw_param in args.param],
            f"  --sizing {args.sizing} \\",
            f"  --allocation {args.allocation} \\",
            f"  --commission-fixed {args.commission_fixed} \\",
            f"  --commission-rate {args.commission_rate} \\",
            f"  --slippage-bps {args.slippage_bps} \\",
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
- Commission fixed: `{args.commission_fixed}`
- Commission rate: `{args.commission_rate}`
- Slippage bps: `{args.slippage_bps}`
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
