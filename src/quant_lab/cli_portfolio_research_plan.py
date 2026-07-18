"""CLI command handlers for guided portfolio research plans."""

from __future__ import annotations

import argparse
from pathlib import Path

from .portfolio_research_plan import (
    create_portfolio_research_plan,
    load_portfolio_research_plan,
    recommend_portfolio_next_step,
    save_portfolio_research_plan,
)
from .research_index import filter_index_records, load_research_index
from .research_registry import (
    append_experiment_record,
    create_experiment_record,
    load_experiments,
    next_experiment_id,
    normalize_tags,
)


def portfolio_plan_init_command(args: argparse.Namespace) -> int:
    records = load_experiments(args.experiments_path)
    existing_ids = {record.experiment_id for record in records}
    experiment_id = args.experiment_id or next_experiment_id(records)
    if experiment_id not in existing_ids:
        record = create_experiment_record(
            experiment_id=experiment_id,
            title=args.title,
            hypothesis=args.hypothesis,
            status="planned",
            tags=normalize_tags(args.tag),
            strategy_path=args.portfolio,
            data_path=None,
            notes="Created by portfolio-plan init.",
        )
        append_experiment_record(record, args.experiments_path)

    plan = create_portfolio_research_plan(
        title=args.title,
        hypothesis=args.hypothesis,
        portfolio_path=args.portfolio,
        experiment_id=experiment_id,
        experiments_path=args.experiments_path,
        index_path=args.index_path,
        output_dir=args.out,
        initial_cash=args.initial_cash,
        cost_preset=args.cost_preset,
        commission_fixed=args.commission_fixed,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
        tags=args.tag,
    )
    json_path, markdown_path = save_portfolio_research_plan(plan)
    recommendation = recommend_portfolio_next_step(plan, [], experiment_has_decision=False)

    print(f"Portfolio research plan created: {json_path}")
    print(f"markdown: {markdown_path}")
    print(f"experiment_id: {experiment_id}")
    print("next_command:")
    print(recommendation.command)
    return 0


def portfolio_plan_next_command(args: argparse.Namespace) -> int:
    plan = load_portfolio_research_plan(args.plan)
    records = filter_index_records(load_research_index(plan.index_path), experiment_id=plan.experiment_id)
    experiments = load_experiments(plan.experiments_path)
    experiment = next((record for record in experiments if record.experiment_id == plan.experiment_id), None)
    recommendation = recommend_portfolio_next_step(
        plan,
        records,
        experiment_has_decision=experiment is not None and experiment.decision_record is not None,
        variants_exist=_portfolio_variants_exist(plan.output_dir),
        summary_exists=_portfolio_summary_exists(plan.output_dir),
        candidate_specs_exist=_portfolio_candidate_specs_exist(plan.output_dir),
        batch_manifest_exists=_portfolio_batch_manifest_exists(plan.output_dir),
        batch_result_exists=_portfolio_batch_result_exists(plan.output_dir),
        batch_summary_exists=_portfolio_batch_summary_exists(plan.output_dir),
        data_trust_report_exists=_portfolio_data_trust_report_exists(records),
    )

    print(f"Portfolio research plan: {args.plan}")
    print(f"experiment_id: {plan.experiment_id}")
    print(f"recommended_step: {recommendation.step}")
    print(f"reason: {recommendation.reason}")
    if recommendation.command is not None:
        print("next_command:")
        print(recommendation.command)
    return 0


def _portfolio_variants_exist(output_dir: str) -> bool:
    variants_dir = Path(output_dir) / "portfolio_variants"
    return variants_dir.exists() and any(variants_dir.glob("*.json"))


def _portfolio_summary_exists(output_dir: str) -> bool:
    return (Path(output_dir) / "portfolio_summary.md").exists()


def _portfolio_data_trust_report_exists(index_records: list[dict]) -> bool:
    for record in index_records:
        if str(record.get("run_type")) != "portfolio_run":
            continue
        metadata_path = str(record.get("metadata_path", "")).strip()
        if metadata_path:
            return (Path(metadata_path).parent / "portfolio_data_trust_report.md").exists()
    return False


def _portfolio_candidate_specs_exist(output_dir: str) -> bool:
    for candidate_dir in _portfolio_candidate_dirs(output_dir):
        if candidate_dir.exists() and any(candidate_dir.glob("*.json")):
            return True
    return False


def _portfolio_batch_manifest_exists(output_dir: str) -> bool:
    return (Path(output_dir) / "portfolio_batch" / "portfolio_batch_manifest.json").exists()


def _portfolio_batch_result_exists(output_dir: str) -> bool:
    return (Path(output_dir) / "portfolio_batch" / "portfolio_batch_result.json").exists()


def _portfolio_batch_summary_exists(output_dir: str) -> bool:
    return (Path(output_dir) / "portfolio_batch" / "portfolio_batch_summary.md").exists()


def _portfolio_candidate_dirs(output_dir: str) -> list[Path]:
    base = Path(output_dir)
    return [base / "portfolio_variants", base / "portfolio_candidates"]
