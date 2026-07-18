"""CLI command handlers for guided research plans."""

from __future__ import annotations

import argparse
import shlex
from dataclasses import dataclass
from pathlib import Path

from .research_index import filter_index_records, load_research_index
from .research_plan import ResearchPlan, create_research_plan, load_research_plan, save_research_plan
from .research_plan_common import add_optional_cost_overrides
from .research_registry import (
    append_experiment_record,
    create_experiment_record,
    load_experiments,
    next_experiment_id,
    normalize_tags,
)


@dataclass(frozen=True)
class ResearchPlanRecommendation:
    step: str
    reason: str
    command: str | None


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


def research_plan_next_command(args: argparse.Namespace) -> int:
    plan = load_research_plan(args.plan)
    records = filter_index_records(load_research_index(plan.index_path), experiment_id=plan.experiment_id)
    experiments = load_experiments(plan.experiments_path)
    experiment = next((record for record in experiments if record.experiment_id == plan.experiment_id), None)
    recommendation = recommend_next_step(
        plan,
        records,
        experiment_has_decision=experiment_has_decision(experiment),
        run_trust_report_exists=_run_trust_report_exists(records),
        evidence_summary_exists=_evidence_summary_exists(plan.output_dir),
    )

    print(f"Research plan: {args.plan}")
    print(f"experiment_id: {plan.experiment_id}")
    print(f"recommended_step: {recommendation.step}")
    print(f"reason: {recommendation.reason}")
    if recommendation.command is not None:
        print("next_command:")
        print(recommendation.command)
    return 0


def recommend_next_step(
    plan: ResearchPlan,
    index_records: list[dict],
    *,
    experiment_has_decision: bool = False,
    run_trust_report_exists: bool = False,
    evidence_summary_exists: bool = False,
) -> ResearchPlanRecommendation:
    if experiment_has_decision:
        return ResearchPlanRecommendation(
            step="done",
            reason="The experiment already has a recorded decision.",
            command=None,
        )

    run_types = {str(record.get("run_type")) for record in index_records}
    baseline_metadata_path = _first_metadata_path(index_records, run_type="run")
    if "run" not in run_types:
        return ResearchPlanRecommendation(
            step="baseline",
            reason="No baseline run is linked to this experiment yet.",
            command=build_baseline_run_command_from_plan(plan),
        )
    if baseline_metadata_path and not run_trust_report_exists:
        return ResearchPlanRecommendation(
            step="run_trust",
            reason="A baseline exists; write a data trust report before widening the research branch.",
            command=build_run_trust_command(baseline_metadata_path),
        )
    if "sweep_run" not in run_types:
        return ResearchPlanRecommendation(
            step="sweep",
            reason="A baseline exists, but no parameter sweep is linked yet.",
            command=build_sweep_command_from_plan(plan),
        )
    if not ({"test_selected_run", "walk_forward_test_run"} & run_types):
        return ResearchPlanRecommendation(
            step="train_test",
            reason="A sweep exists, but no validation test run is linked yet.",
            command=build_train_test_command_from_plan(plan),
        )
    if not evidence_summary_exists:
        return ResearchPlanRecommendation(
            step="summarize",
            reason="Validation evidence exists; write the evidence summary before drafting a decision.",
            command=build_summarize_command_from_plan(plan),
        )
    return ResearchPlanRecommendation(
        step="draft_decision",
        reason="The evidence summary exists; draft a conservative decision before writing it to the registry.",
        command=build_draft_decision_command_from_plan(plan),
    )


def experiment_has_decision(experiment) -> bool:
    return experiment is not None and experiment.decision_record is not None


def _run_trust_report_exists(index_records: list[dict]) -> bool:
    metadata_path = _first_metadata_path(index_records, run_type="run")
    if not metadata_path:
        return False
    return (Path(metadata_path).parent / "run_trust_report.md").exists()


def _evidence_summary_exists(output_dir: str) -> bool:
    return (Path(output_dir) / "evidence_summary.md").exists()


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


def build_baseline_run_command_from_plan(plan: ResearchPlan) -> str:
    return build_baseline_run_command_from_values(
        strategy=plan.strategy_path,
        data=plan.data_path,
        out=Path(plan.output_dir) / "baseline",
        initial_cash=plan.initial_cash,
        quantity=plan.quantity,
        sizing=plan.sizing,
        allocation=plan.allocation,
        benchmark=plan.benchmark,
        cost_preset=plan.cost_preset,
        experiments_path=plan.experiments_path,
        experiment_id=plan.experiment_id,
        index_path=plan.index_path,
        hypothesis=plan.hypothesis,
        commission_fixed=plan.commission_fixed,
        commission_rate=plan.commission_rate,
        slippage_bps=plan.slippage_bps,
    )


def build_baseline_run_command_from_values(
    *,
    strategy: str,
    data: str,
    out: str | Path,
    initial_cash: float,
    quantity: float,
    sizing: str,
    allocation: float,
    benchmark: str,
    cost_preset: str,
    experiments_path: str,
    experiment_id: str,
    index_path: str,
    hypothesis: str,
    commission_fixed: float | None,
    commission_rate: float | None,
    slippage_bps: float | None,
) -> str:
    command = [
        "quant-lab",
        "run",
        "--strategy",
        str(strategy),
        "--data",
        str(data),
        "--out",
        str(out),
        "--initial-cash",
        str(initial_cash),
        "--quantity",
        str(quantity),
        "--sizing",
        str(sizing),
        "--allocation",
        str(allocation),
        "--benchmark",
        str(benchmark),
        "--cost-preset",
        str(cost_preset),
        "--experiments-path",
        str(experiments_path),
        "--experiment-id",
        experiment_id,
        "--index-path",
        str(index_path),
        "--note",
        f"Baseline for research plan: {hypothesis}",
    ]
    add_optional_cost_overrides(command, commission_fixed, commission_rate, slippage_bps)
    return shlex.join(command)


def build_sweep_command_from_plan(plan: ResearchPlan) -> str:
    command = base_sweep_command(plan, Path(plan.output_dir) / "sweep_001")
    command.extend(["--param", "indicator_id.inputs.length=VALUE1,VALUE2"])
    command.extend(["--note", f"Parameter sweep for research plan: {plan.hypothesis}"])
    return shlex.join(command)


def build_train_test_command_from_plan(plan: ResearchPlan) -> str:
    command = base_sweep_command(plan, Path(plan.output_dir) / "train_test_001")
    command.extend(["--param", "indicator_id.inputs.length=VALUE1,VALUE2"])
    command.extend(["--train-end", "YYYY-MM-DD"])
    command.extend(["--test-start", "YYYY-MM-DD"])
    command.extend(["--select-by", "sharpe_ratio"])
    return shlex.join(command)


def base_sweep_command(plan: ResearchPlan, out: str | Path) -> list[str]:
    command = [
        "quant-lab",
        "sweep",
        "--strategy",
        plan.strategy_path,
        "--data",
        plan.data_path,
        "--out",
        str(out),
        "--initial-cash",
        str(plan.initial_cash),
        "--quantity",
        str(plan.quantity),
        "--sizing",
        plan.sizing,
        "--allocation",
        str(plan.allocation),
        "--benchmark",
        plan.benchmark,
        "--cost-preset",
        plan.cost_preset,
        "--experiments-path",
        plan.experiments_path,
        "--experiment-id",
        plan.experiment_id,
        "--index-path",
        plan.index_path,
    ]
    add_optional_cost_overrides(command, plan.commission_fixed, plan.commission_rate, plan.slippage_bps)
    return command


def build_summarize_command_from_plan(plan: ResearchPlan) -> str:
    return shlex.join(
        [
            "quant-lab",
            "summarize-experiment",
            "--experiment-id",
            plan.experiment_id,
            "--experiments-path",
            plan.experiments_path,
            "--index-path",
            plan.index_path,
            "--out",
            _display_path(Path(plan.output_dir) / "evidence_summary.md"),
        ]
    )


def build_draft_decision_command_from_plan(plan: ResearchPlan) -> str:
    return shlex.join(
        [
            "quant-lab",
            "draft-decision",
            "--experiment-id",
            plan.experiment_id,
            "--experiments-path",
            plan.experiments_path,
            "--index-path",
            plan.index_path,
        ]
    )


def build_run_trust_command(metadata_path: str) -> str:
    return shlex.join(["quant-lab", "summarize-run-trust", "--metadata", metadata_path])


def _first_metadata_path(index_records: list[dict], *, run_type: str) -> str | None:
    for record in index_records:
        if str(record.get("run_type")) != run_type:
            continue
        metadata_path = str(record.get("metadata_path", "")).strip()
        if metadata_path:
            return metadata_path
    return None


def _display_path(path: str | Path) -> str:
    path_string = str(path)
    if Path(path).is_absolute():
        return path_string
    return path_string.replace("\\", "/")
