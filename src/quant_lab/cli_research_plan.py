"""CLI command handlers for guided research plans."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .research_index import filter_index_records, load_research_index
from .research_plan import ResearchPlan, create_research_plan, load_research_plan, save_research_plan
from .research_plan_workflow import (
    build_baseline_run_command_from_values,
    evidence_summary_exists,
    experiment_conclusion_exists,
    experiment_has_decision,
    parameter_neighborhood_exists,
    recommend_next_step,
    run_trust_report_exists,
)
from .research_registry import (
    append_experiment_record,
    create_experiment_record,
    load_experiments,
    next_experiment_id,
    normalize_tags,
)


def research_plan_init_command(args: argparse.Namespace) -> int:
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
            strategy_path=args.strategy,
            data_path=args.data,
            notes="Created by research-plan init.",
        )
        append_experiment_record(record, args.experiments_path)

    plan = create_research_plan(
        title=args.title,
        hypothesis=args.hypothesis,
        strategy_path=args.strategy,
        data_path=args.data,
        symbol=args.symbol,
        experiment_id=experiment_id,
        experiments_path=args.experiments_path,
        index_path=args.index_path,
        output_dir=args.out,
        initial_cash=args.initial_cash,
        quantity=args.quantity,
        sizing=args.sizing,
        allocation=args.allocation,
        benchmark=args.benchmark,
        cost_preset=args.cost_preset,
        commission_fixed=args.commission_fixed,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
        intended_benefit=args.intended_benefit,
        primary_metric=args.primary_metric,
        minimum_acceptable_performance=args.minimum_acceptable_performance,
        important_tradeoffs=args.tradeoff,
        success_criteria=_parse_success_criteria(args.success_criterion),
        tags=args.tag,
    )
    json_path, markdown_path = save_research_plan(plan)
    baseline_command = build_baseline_run_command(args, experiment_id)

    print(f"Research plan created: {json_path}")
    print(f"markdown: {markdown_path}")
    print(f"experiment_id: {experiment_id}")
    print("next_command:")
    print(baseline_command)
    return 0


def _parse_success_criteria(values: list[str]) -> list[dict]:
    criteria: list[dict] = []
    for value in values:
        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise ValueError("--success-criterion must be a JSON object")
        criteria.append(payload)
    return criteria


def research_plan_next_command(args: argparse.Namespace) -> int:
    plan = load_research_plan(args.plan)
    records = filter_index_records(load_research_index(plan.index_path), experiment_id=plan.experiment_id)
    experiments = load_experiments(plan.experiments_path)
    experiment = next((record for record in experiments if record.experiment_id == plan.experiment_id), None)
    recommendation = recommend_next_step(
        plan,
        records,
        experiment_has_decision=experiment_has_decision(experiment),
        run_trust_report_exists=run_trust_report_exists(records),
        evidence_summary_exists=evidence_summary_exists(plan.output_dir),
        parameter_neighborhood_exists=parameter_neighborhood_exists(plan.output_dir),
        experiment_conclusion_exists=experiment_conclusion_exists(plan.output_dir),
    )

    print(f"Research plan: {args.plan}")
    print(f"experiment_id: {plan.experiment_id}")
    print(f"recommended_step: {recommendation.step}")
    print(f"reason: {recommendation.reason}")
    if recommendation.command is not None:
        print("next_command:")
        print(recommendation.command)
    return 0


def build_baseline_run_command(args: argparse.Namespace, experiment_id: str) -> str:
    return build_baseline_run_command_from_values(
        strategy=args.strategy,
        data=args.data,
        out=Path(args.out) / "baseline",
        initial_cash=args.initial_cash,
        quantity=args.quantity,
        sizing=args.sizing,
        allocation=args.allocation,
        benchmark=args.benchmark,
        cost_preset=args.cost_preset,
        experiments_path=args.experiments_path,
        experiment_id=experiment_id,
        index_path=args.index_path,
        hypothesis=args.hypothesis,
        commission_fixed=args.commission_fixed,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
    )
