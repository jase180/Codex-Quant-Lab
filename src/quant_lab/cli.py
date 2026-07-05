"""Command-line interface for Codex Quant Lab."""

from __future__ import annotations

import argparse
import copy
import csv
import itertools
import json
import subprocess
from pathlib import Path
from typing import Sequence

import pandas as pd

from backtester_core import (
    BacktestEngine,
    save_run_report_artifacts,
    summarize_run_metrics,
)

from .data_fetch import fetch_market_data, write_market_data_csv
from .rule_based_strategy import build_rule_based_strategy
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
    sweep_parser.set_defaults(func=sweep_command)
    return parser


def run_command(args: argparse.Namespace) -> int:
    strategy_spec = load_strategy(args.strategy)
    strategy = build_rule_based_strategy(
        strategy_spec,
        order_quantity=args.quantity,
        sizing=args.sizing,
        allocation=args.allocation,
    )
    data = pd.read_csv(args.data)

    result = BacktestEngine(initial_cash=args.initial_cash).run(data, strategy)
    run_name = args.run_name or strategy_spec.name
    artifact_paths = save_run_report_artifacts(result, args.out, run_name=run_name)
    artifact_paths["trades"] = save_trades(result.trades, args.out)

    print(f"Run complete: {run_name}")
    for artifact_name in sorted(artifact_paths):
        print(f"{artifact_name}: {artifact_paths[artifact_name]}")
    print(f"final_equity: {result.final_equity:.2f}")
    print(f"total_return: {result.total_return:.2%}")
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


def sweep_command(args: argparse.Namespace) -> int:
    base_payload = load_strategy_payload(args.strategy)
    param_sweeps = parse_param_sweeps(args.param)
    variants = build_sweep_variants(base_payload, param_sweeps)
    data = pd.read_csv(args.data)
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

        result = BacktestEngine(initial_cash=args.initial_cash).run(data, strategy)
        metrics = summarize_run_metrics(result)
        run_name_prefix = args.run_name or strategy_spec.name
        save_run_report_artifacts(result, run_dir, run_name=f"{run_name_prefix} {run_id}")
        save_trades(result.trades, run_dir)
        save_strategy_payload(strategy_payload, run_dir)

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
    return 0


def save_trades(trades: pd.DataFrame, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    trades_path = destination / "trades.csv"
    trades.to_csv(trades_path)
    return str(trades_path)


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
    best = rows[0] if rows else None
    git_commit = current_git_commit()
    best_lines = ""
    if best:
        best_lines = (
            f"- Best run by total return: `{best['run_id']}`\n"
            f"- Best total return: {float(best['total_return']):.2%}\n"
            f"- Best run params: `{best['params']}`\n"
        )

    param_lines = "\n".join(f"- `{raw_param}`" for raw_param in args.param)
    command_lines = "\n".join(
        [
            "quant-lab sweep \\",
            f"  --strategy {args.strategy} \\",
            f"  --data {args.data} \\",
            *[f"  --param {raw_param} \\" for raw_param in args.param],
            f"  --sizing {args.sizing} \\",
            f"  --allocation {args.allocation} \\",
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
- Git commit: `{git_commit}`

## Parameters

{param_lines}

## Results

- Runs: {len(rows)}
{best_lines}
## Skeptic Pass

- Check whether the best result is supported by enough trades.
- Check whether nearby parameter values are also strong.
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
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
