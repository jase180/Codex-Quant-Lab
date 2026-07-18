"""Shared execution path for portfolio research runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backtester_core.execution import ExecutionModel, TransactionCostModel
from metrics_reporting import RunMetrics

from .portfolio_artifacts import save_portfolio_artifacts
from .portfolio_backtest import PortfolioBacktestResult, StaticWeightPortfolioBacktester
from .portfolio_benchmarks import build_portfolio_benchmark_comparison
from .portfolio_data import load_multi_asset_dataset
from .portfolio_metadata import PortfolioMetadata
from .portfolio_spec import load_portfolio_spec
from .research_index import RunIndexRecord, append_research_index_record
from .research_registry import link_run_metadata_path, require_experiment


@dataclass(frozen=True)
class PortfolioRunExecution:
    """Artifacts and headline metrics produced by one portfolio research run."""

    portfolio_name: str
    artifact_paths: dict[str, str]
    final_equity: float
    total_return: float
    benchmark_symbol: str
    benchmark_total_return: float
    excess_total_return: float
    cost_preset: str


def execute_portfolio_run(
    *,
    portfolio_path: str | Path,
    output_dir: str | Path,
    initial_cash: float,
    cost_assumptions,
    experiments_path: str | Path,
    experiment_id: str | None,
    index_path: str | Path,
    command: list[str],
) -> PortfolioRunExecution:
    """Run one portfolio spec and persist normal portfolio-run artifacts."""

    require_experiment(experiments_path, experiment_id)

    portfolio = load_portfolio_spec(portfolio_path)
    dataset = load_multi_asset_dataset(portfolio)
    cost_model = TransactionCostModel(
        commission_fixed=cost_assumptions.commission_fixed,
        commission_rate=cost_assumptions.commission_rate,
        slippage_bps=cost_assumptions.slippage_bps,
    )
    result = StaticWeightPortfolioBacktester(
        initial_cash=initial_cash,
        execution_model=ExecutionModel(cost_model=cost_model),
    ).run(portfolio, dataset)
    benchmark = build_portfolio_benchmark_comparison(
        portfolio=portfolio,
        dataset=dataset,
        result=result,
        initial_cash=initial_cash,
    )
    saved = save_portfolio_artifacts(
        portfolio=portfolio,
        dataset=dataset,
        result=result,
        output_dir=output_dir,
        initial_cash=initial_cash,
        cost_assumptions=cost_assumptions,
        benchmark_comparison=benchmark,
        command=command,
    )
    link_run_metadata_path(
        registry_path=experiments_path,
        experiment_id=experiment_id,
        metadata_path=saved.artifact_paths["metadata"],
    )
    append_research_index_record(
        _build_portfolio_index_record(
            metadata=saved.metadata,
            metrics=saved.metrics,
            result=result,
            output_dir=output_dir,
            experiment_id=experiment_id,
            trade_count=len(result.trades),
        ),
        index_path,
    )
    return PortfolioRunExecution(
        portfolio_name=portfolio.name,
        artifact_paths=saved.artifact_paths,
        final_equity=result.final_equity,
        total_return=result.total_return,
        benchmark_symbol=benchmark.symbol,
        benchmark_total_return=benchmark.metrics.total_return,
        excess_total_return=benchmark.excess_total_return,
        cost_preset=cost_assumptions.preset,
    )


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
