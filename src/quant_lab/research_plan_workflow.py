"""Shared research-plan workflow recommendation helpers."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from .research_plan import ResearchPlan
from .research_plan_common import add_optional_cost_overrides


@dataclass(frozen=True)
class ResearchPlanRecommendation:
    step: str
    reason: str
    command: str | None


def recommend_next_step(
    plan: ResearchPlan,
    index_records: list[dict],
    *,
    experiment_has_decision: bool = False,
    run_trust_report_exists: bool = False,
    evidence_summary_exists: bool = False,
    parameter_neighborhood_exists: bool = False,
    experiment_conclusion_exists: bool = False,
) -> ResearchPlanRecommendation:
    if experiment_has_decision:
        return ResearchPlanRecommendation(
            step="done",
            reason="The experiment already has a recorded decision.",
            command=None,
        )

    run_types = {str(record.get("run_type")) for record in index_records}
    baseline_metadata_path = first_metadata_path(index_records, run_type="run")
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
    if "cost_sensitivity_run" not in run_types:
        return ResearchPlanRecommendation(
            step="robustness_cost_sensitivity",
            reason="The evidence summary exists; stress costs before drafting a decision.",
            command=build_cost_sensitivity_command_from_plan(plan),
        )
    if "date_sensitivity_run" not in run_types:
        return ResearchPlanRecommendation(
            step="robustness_date_sensitivity",
            reason="Cost sensitivity exists; test explicit date windows before drafting a decision.",
            command=build_date_sensitivity_command_from_plan(plan),
        )
    if "benchmark_sensitivity_run" not in run_types:
        return ResearchPlanRecommendation(
            step="robustness_benchmark_sensitivity",
            reason="Date sensitivity exists; check benchmark substitution before drafting a decision.",
            command=build_benchmark_sensitivity_command_from_plan(plan),
        )
    if sweep_summary_exists(plan.output_dir) and not parameter_neighborhood_exists:
        return ResearchPlanRecommendation(
            step="robustness_parameter_neighborhood",
            reason="Benchmark sensitivity exists; summarize whether nearby sweep parameters also beat the benchmark.",
            command=build_parameter_neighborhood_command_from_plan(plan),
        )
    if not experiment_conclusion_exists:
        return ResearchPlanRecommendation(
            step="conclude_experiment",
            reason="Evidence and robustness checks exist; write the canonical conclusion before drafting a decision.",
            command=build_conclude_experiment_command_from_plan(plan),
        )
    return ResearchPlanRecommendation(
        step="draft_decision",
        reason="The canonical conclusion exists; draft a conservative decision before writing it to the registry.",
        command=build_draft_decision_command_from_plan(plan),
    )


def experiment_has_decision(experiment) -> bool:
    return experiment is not None and experiment.decision_record is not None


def run_trust_report_exists(index_records: list[dict]) -> bool:
    metadata_path = first_metadata_path(index_records, run_type="run")
    if not metadata_path:
        return False
    return (Path(metadata_path).parent / "run_trust_report.md").exists()


def evidence_summary_exists(output_dir: str) -> bool:
    return (Path(output_dir) / "evidence_summary.md").exists()


def parameter_neighborhood_exists(output_dir: str) -> bool:
    return (Path(output_dir) / "robustness" / "parameters" / "parameter_neighborhood_report.md").exists()


def experiment_conclusion_exists(output_dir: str) -> bool:
    return (Path(output_dir) / "experiment_conclusion.json").exists()


def sweep_summary_exists(output_dir: str) -> bool:
    return (Path(output_dir) / "sweep_001" / "summary.csv").exists()


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
            display_path(Path(plan.output_dir) / "evidence_summary.md"),
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


def build_conclude_experiment_command_from_plan(plan: ResearchPlan) -> str:
    return shlex.join(
        [
            "quant-lab",
            "conclude-experiment",
            "--experiment-id",
            plan.experiment_id,
            "--experiments-path",
            plan.experiments_path,
            "--index-path",
            plan.index_path,
            "--out",
            display_path(plan.output_dir),
        ]
    )


def build_cost_sensitivity_command_from_plan(plan: ResearchPlan) -> str:
    presets = _ordered_unique([plan.cost_preset, "retail-conservative", "high-friction"])
    command = [
        "quant-lab",
        "robustness",
        "cost-sensitivity",
        "--strategy",
        plan.strategy_path,
        "--data",
        plan.data_path,
        "--out",
        display_path(Path(plan.output_dir) / "robustness" / "costs"),
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
        "--experiments-path",
        plan.experiments_path,
        "--experiment-id",
        plan.experiment_id,
        "--index-path",
        plan.index_path,
    ]
    for preset in presets:
        command.extend(["--cost-preset", preset])
    return shlex.join(command)


def build_date_sensitivity_command_from_plan(plan: ResearchPlan) -> str:
    command = [
        "quant-lab",
        "robustness",
        "date-sensitivity",
        "--strategy",
        plan.strategy_path,
        "--data",
        plan.data_path,
        "--out",
        display_path(Path(plan.output_dir) / "robustness" / "dates"),
        "--initial-cash",
        str(plan.initial_cash),
        "--quantity",
        str(plan.quantity),
        "--sizing",
        plan.sizing,
        "--allocation",
        str(plan.allocation),
        "--cost-preset",
        plan.cost_preset,
        "--benchmark",
        plan.benchmark,
        "--window",
        "START_DATE,END_DATE",
        "--window",
        "START_DATE,END_DATE",
        "--experiments-path",
        plan.experiments_path,
        "--experiment-id",
        plan.experiment_id,
        "--index-path",
        plan.index_path,
    ]
    add_optional_cost_overrides(command, plan.commission_fixed, plan.commission_rate, plan.slippage_bps)
    return shlex.join(command)


def build_benchmark_sensitivity_command_from_plan(plan: ResearchPlan) -> str:
    command = [
        "quant-lab",
        "robustness",
        "benchmark-sensitivity",
        "--strategy",
        plan.strategy_path,
        "--data",
        plan.data_path,
        "--out",
        display_path(Path(plan.output_dir) / "robustness" / "benchmarks"),
        "--initial-cash",
        str(plan.initial_cash),
        "--quantity",
        str(plan.quantity),
        "--sizing",
        plan.sizing,
        "--allocation",
        str(plan.allocation),
        "--cost-preset",
        plan.cost_preset,
        "--benchmark",
        "cash",
        "--benchmark",
        "buy-and-hold",
        "--experiments-path",
        plan.experiments_path,
        "--experiment-id",
        plan.experiment_id,
        "--index-path",
        plan.index_path,
    ]
    add_optional_cost_overrides(command, plan.commission_fixed, plan.commission_rate, plan.slippage_bps)
    return shlex.join(command)


def build_parameter_neighborhood_command_from_plan(plan: ResearchPlan) -> str:
    return shlex.join(
        [
            "quant-lab",
            "robustness",
            "parameter-neighborhood",
            "--summary",
            display_path(Path(plan.output_dir) / "sweep_001" / "summary.csv"),
            "--out",
            display_path(Path(plan.output_dir) / "robustness" / "parameters"),
        ]
    )


def build_run_trust_command(metadata_path: str) -> str:
    return shlex.join(["quant-lab", "summarize-run-trust", "--metadata", metadata_path])


def first_metadata_path(index_records: list[dict], *, run_type: str) -> str | None:
    for record in index_records:
        if str(record.get("run_type")) != run_type:
            continue
        metadata_path = str(record.get("metadata_path", "")).strip()
        if metadata_path:
            return metadata_path
    return None


def display_path(path: str | Path) -> str:
    path_string = str(path)
    if Path(path).is_absolute():
        return path_string
    return path_string.replace("\\", "/")


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
