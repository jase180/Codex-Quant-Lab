"""CLI command handlers for portfolio research runs."""

from __future__ import annotations

import argparse
from pathlib import Path

from backtester_core.execution import ExecutionModel, TransactionCostModel
from metrics_reporting import RunMetrics

from .cli_runs import resolve_cli_costs
from .portfolio_artifacts import PortfolioMetadata, save_portfolio_artifacts
from .portfolio_backtest import PortfolioBacktestResult, StaticWeightPortfolioBacktester
from .portfolio_benchmarks import build_portfolio_benchmark_comparison
from .portfolio_data import load_multi_asset_dataset
from .portfolio_spec import load_portfolio_spec
from .research_index import RunIndexRecord, append_research_index_record
from .research_registry import link_run_metadata_path, require_experiment


def portfolio_run_command(args: argparse.Namespace) -> int:
    args.cost_assumptions = resolve_cli_costs(args)
    require_experiment(args.experiments_path, args.experiment_id)

    portfolio = load_portfolio_spec(args.portfolio)
    dataset = load_multi_asset_dataset(portfolio)
    cost_model = TransactionCostModel(
        commission_fixed=args.cost_assumptions.commission_fixed,
        commission_rate=args.cost_assumptions.commission_rate,
        slippage_bps=args.cost_assumptions.slippage_bps,
    )
    result = StaticWeightPortfolioBacktester(
        initial_cash=args.initial_cash,
        execution_model=ExecutionModel(cost_model=cost_model),
    ).run(portfolio, dataset)
    benchmark = build_portfolio_benchmark_comparison(
        portfolio=portfolio,
        dataset=dataset,
        result=result,
        initial_cash=args.initial_cash,
    )
    saved = save_portfolio_artifacts(
        portfolio=portfolio,
        dataset=dataset,
        result=result,
        output_dir=args.out,
        initial_cash=args.initial_cash,
        cost_assumptions=args.cost_assumptions,
        benchmark_comparison=benchmark,
        command=args.command_tokens,
    )
    link_run_metadata_path(
        registry_path=args.experiments_path,
        experiment_id=args.experiment_id,
        metadata_path=saved.artifact_paths["metadata"],
    )
    append_research_index_record(
        _build_portfolio_index_record(
            metadata=saved.metadata,
            metrics=saved.metrics,
            result=result,
            output_dir=args.out,
            experiment_id=args.experiment_id,
            trade_count=len(result.trades),
        ),
        args.index_path,
    )

    print(f"Portfolio run complete: {portfolio.name}")
    for artifact_name in sorted(saved.artifact_paths):
        print(f"{artifact_name}: {saved.artifact_paths[artifact_name]}")
    print(f"final_equity: {result.final_equity:.2f}")
    print(f"total_return: {result.total_return:.2%}")
    print(f"benchmark: buy-and-hold {benchmark.symbol}")
    print(f"benchmark_total_return: {benchmark.metrics.total_return:.2%}")
    print(f"excess_total_return: {benchmark.excess_total_return:.2%}")
    print(f"cost_preset: {args.cost_assumptions.preset}")
    return 0


def _build_portfolio_index_record(
    *,
    metadata: PortfolioMetadata,
    metrics: RunMetrics,
    result: PortfolioBacktestResult,
    output_dir: str | Path,
    experiment_id: str | None,
    trade_count: int,
) -> RunIndexRecord:
    benchmark = metadata.benchmark
    if benchmark is None:
        raise ValueError("portfolio metadata must include benchmark comparison before indexing")
    aligned_start = result.equity_curve.index[0].date().isoformat()
    aligned_end = result.equity_curve.index[-1].date().isoformat()

    return RunIndexRecord(
        index_schema_version="research_index.v1",
        created_at_utc=metadata.created_at_utc,
        run_type=metadata.run_type,
        run_id=None,
        experiment_id=experiment_id,
        strategy_id=metadata.portfolio_id,
        strategy_name=metadata.name,
        symbol=",".join(symbol.symbol for symbol in metadata.symbols),
        timeframe="1d",
        data_start=aligned_start,
        data_end=aligned_end,
        final_equity=metrics.ending_equity,
        total_return=metrics.total_return,
        cagr=metrics.cagr,
        sharpe_ratio=metrics.sharpe_ratio,
        max_drawdown=metrics.max_drawdown,
        trade_count=trade_count,
        benchmark_name=f"buy-and-hold-{benchmark.symbol.lower()}",
        benchmark_total_return=benchmark.total_return,
        benchmark_max_drawdown=benchmark.max_drawdown,
        excess_total_return=benchmark.excess_total_return,
        sizing="static-weights",
        initial_cash=metadata.initial_cash,
        quantity=0.0,
        allocation=1.0,
        cost_preset=metadata.costs.preset,
        commission_fixed=metadata.costs.commission_fixed,
        commission_rate=metadata.costs.commission_rate,
        slippage_bps=metadata.costs.slippage_bps,
        output_dir=str(output_dir),
        metadata_path=metadata.artifacts["metadata"],
        git_commit=metadata.environment.git_commit,
    )
