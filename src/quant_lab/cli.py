"""Command-line interface for Codex Quant Lab."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import pandas as pd

from backtester_core import BacktestEngine, save_run_report_artifacts

from .rule_based_strategy import build_rule_based_strategy
from .strategy_schema import load_strategy


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
        type=int,
        default=1,
        help="Order quantity used by v1 long-only rule-based strategies. Defaults to 1.",
    )
    run_parser.add_argument(
        "--run-name",
        default=None,
        help="Report title. Defaults to the strategy name.",
    )
    run_parser.set_defaults(func=run_command)
    return parser


def run_command(args: argparse.Namespace) -> int:
    strategy_spec = load_strategy(args.strategy)
    strategy = build_rule_based_strategy(strategy_spec, order_quantity=args.quantity)
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


def save_trades(trades: pd.DataFrame, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    trades_path = destination / "trades.csv"
    trades.to_csv(trades_path)
    return str(trades_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
