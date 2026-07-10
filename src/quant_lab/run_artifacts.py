"""Shared artifact writing for backtest runs and sweep variants."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

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

from .benchmarks import append_benchmark_section, benchmark_summary_fields, excess_total_return
from .data_quality import append_data_quality_section, save_data_quality_report
from .research_index import append_research_index_record, build_run_index_record
from .research_warnings import append_research_warnings_section, build_research_warnings, save_research_warnings
from .rule_based_strategy import build_rule_based_strategy
from .run_metadata import (
    BenchmarkMetadata,
    CostMetadata,
    DataMetadata,
    EnvironmentMetadata,
    RunMetadata,
    SizingMetadata,
    StrategyMetadata,
    save_run_metadata,
)


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
    research_note_path: str | None = None,
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
    if research_note_path is not None:
        artifact_paths["research_note"] = research_note_path
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


def save_strategy_payload(strategy_payload: dict, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    strategy_path = destination / "strategy.json"
    strategy_path.write_text(
        json.dumps(strategy_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(strategy_path)


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
