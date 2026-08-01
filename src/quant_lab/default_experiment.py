"""Run the normal single-strategy experiment workflow as one command."""

from __future__ import annotations

import argparse
import contextlib
import io
from dataclasses import dataclass
from pathlib import Path

from .cli_runs import run_command
from .costs import COST_PRESETS
from .evidence_labels import label_strategy_evidence
from .experiment_conclusion import build_experiment_conclusion, save_experiment_conclusion_artifacts
from .experiment_summary import format_experiment_evidence_summary, save_experiment_evidence_summary
from .research_index import load_research_index
from .research_plan import create_research_plan, save_research_plan
from .research_registry import (
    append_experiment_record,
    create_experiment_decision,
    create_experiment_record,
    decide_experiment_record,
    find_experiment,
    load_experiments,
    next_experiment_id,
    normalize_tags,
    replace_experiment_record,
)
from .robustness import run_benchmark_sensitivity, run_cost_sensitivity, run_date_sensitivity
from .run_artifacts import current_git_commit
from .run_trust import summarize_run_trust
from .sweep_guardrails import summarize_sweep_guardrails
from .sweep_workflows import sweep_command


DEFAULT_CONSERVATIVE_DECISION_TAGS = ["default-workflow"]


@dataclass(frozen=True)
class DefaultExperimentResult:
    experiment_id: str
    output_dir: str
    baseline_metadata_path: str
    trust_report_path: str
    sweep_summary_path: str
    train_test_summary_path: str
    evidence_summary_path: str
    conclusion_path: str
    decision_outcome: str | None
    read_first_path: str
    captured_output: str


def run_default_experiment(args: argparse.Namespace) -> DefaultExperimentResult:
    """Run the standard workflow from baseline to conclusion.

    This orchestration deliberately reuses the existing commands' Python entry
    points. The goal is fewer manual handoffs, not a second implementation of
    backtesting, sweeps, robustness, or experiment conclusions.
    """

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_id = _ensure_experiment(args)
    _write_research_plan(args, experiment_id)

    captured_output = io.StringIO()
    with contextlib.redirect_stdout(captured_output):
        baseline_dir = output_dir / "baseline"
        run_command(
            _namespace(
                strategy=args.strategy,
                data=args.data,
                out=str(baseline_dir),
                initial_cash=args.initial_cash,
                quantity=args.quantity,
                sizing=args.sizing,
                allocation=args.allocation,
                run_name=args.run_name,
                benchmark=args.benchmark,
                cost_preset=args.cost_preset,
                commission_fixed=args.commission_fixed,
                commission_rate=args.commission_rate,
                slippage_bps=args.slippage_bps,
                experiments_path=args.experiments_path,
                experiment_id=experiment_id,
                index_path=args.index_path,
                note=f"Baseline for default workflow: {args.hypothesis}",
                note_file=None,
                command_tokens=_command_tokens("run-default", "baseline"),
            )
        )
        baseline_metadata_path = baseline_dir / "run_metadata.json"
        trust_report = summarize_run_trust(baseline_metadata_path)

        sweep_dir = output_dir / "sweep_001"
        sweep_command(
            _sweep_args(
                args,
                experiment_id=experiment_id,
                out=sweep_dir,
                param=args.param,
                note=f"Parameter sweep for default workflow: {args.hypothesis}",
            )
        )
        sweep_summary_path = sweep_dir / "summary.csv"
        guardrail_report = summarize_sweep_guardrails(
            summary_path=sweep_summary_path,
            output_path=sweep_dir / "sweep_guardrails.md",
        )

        train_test_dir = output_dir / "train_test_001"
        sweep_command(
            _sweep_args(
                args,
                experiment_id=experiment_id,
                out=train_test_dir,
                param=args.param,
                train_end=args.train_end,
                test_start=args.test_start,
                select_by=args.select_by,
                note=f"Train/test validation for default workflow: {args.hypothesis}",
            )
        )
        train_test_summary_path = train_test_dir / "test_summary" / "summary.csv"

        cost_result = run_cost_sensitivity(
            _namespace(
                strategy=args.strategy,
                data=args.data,
                out=str(output_dir / "cost_sensitivity_001"),
                initial_cash=args.initial_cash,
                quantity=args.quantity,
                sizing=args.sizing,
                allocation=args.allocation,
                benchmark=args.benchmark,
                cost_preset=_cost_sensitivity_presets(args),
                experiments_path=args.experiments_path,
                experiment_id=experiment_id,
                index_path=args.index_path,
                command_tokens=_command_tokens("run-default", "cost-sensitivity"),
            )
        )
        date_result = run_date_sensitivity(
            _namespace(
                strategy=args.strategy,
                data=args.data,
                out=str(output_dir / "date_sensitivity_001"),
                initial_cash=args.initial_cash,
                quantity=args.quantity,
                sizing=args.sizing,
                allocation=args.allocation,
                benchmark=args.benchmark,
                cost_preset=args.cost_preset,
                commission_fixed=args.commission_fixed,
                commission_rate=args.commission_rate,
                slippage_bps=args.slippage_bps,
                window=args.date_window,
                experiments_path=args.experiments_path,
                experiment_id=experiment_id,
                index_path=args.index_path,
                command_tokens=_command_tokens("run-default", "date-sensitivity"),
            )
        )
        benchmark_result = run_benchmark_sensitivity(
            _namespace(
                strategy=args.strategy,
                data=args.data,
                out=str(output_dir / "benchmark_sensitivity_001"),
                initial_cash=args.initial_cash,
                quantity=args.quantity,
                sizing=args.sizing,
                allocation=args.allocation,
                benchmark=_benchmark_sensitivity_choices(args),
                cost_preset=args.cost_preset,
                commission_fixed=args.commission_fixed,
                commission_rate=args.commission_rate,
                slippage_bps=args.slippage_bps,
                experiments_path=args.experiments_path,
                experiment_id=experiment_id,
                index_path=args.index_path,
                command_tokens=_command_tokens("run-default", "benchmark-sensitivity"),
            )
        )

    evidence_summary_path, conclusion_path = _write_summary_and_conclusion(args, experiment_id)
    decision_outcome = None
    if args.decision != "none":
        decision_outcome = _record_conservative_decision(args, experiment_id)
        evidence_summary_path, conclusion_path = _write_summary_and_conclusion(args, experiment_id)

    workflow_summary_path = _write_workflow_summary(
        args=args,
        experiment_id=experiment_id,
        baseline_metadata_path=baseline_metadata_path,
        trust_report_path=Path(trust_report.report_path),
        sweep_summary_path=sweep_summary_path,
        sweep_guardrail_path=Path(guardrail_report.report_path),
        train_test_summary_path=train_test_summary_path,
        cost_report_path=Path(cost_result.report_path),
        date_report_path=Path(date_result.report_path),
        benchmark_report_path=Path(benchmark_result.report_path),
        evidence_summary_path=Path(evidence_summary_path),
        conclusion_path=Path(conclusion_path),
        decision_outcome=decision_outcome,
        captured_output=captured_output.getvalue(),
    )
    return DefaultExperimentResult(
        experiment_id=experiment_id,
        output_dir=str(output_dir),
        baseline_metadata_path=str(baseline_metadata_path),
        trust_report_path=trust_report.report_path,
        sweep_summary_path=str(sweep_summary_path),
        train_test_summary_path=str(train_test_summary_path),
        evidence_summary_path=str(evidence_summary_path),
        conclusion_path=str(conclusion_path),
        decision_outcome=decision_outcome,
        read_first_path=str(conclusion_path if Path(conclusion_path).exists() else workflow_summary_path),
        captured_output=captured_output.getvalue(),
    )


def _ensure_experiment(args: argparse.Namespace) -> str:
    records = load_experiments(args.experiments_path)
    existing_ids = {record.experiment_id for record in records}
    experiment_id = args.experiment_id or next_experiment_id(records)
    if experiment_id in existing_ids:
        return experiment_id
    record = create_experiment_record(
        experiment_id=experiment_id,
        title=args.title,
        hypothesis=args.hypothesis,
        status="planned",
        tags=normalize_tags(args.tag),
        strategy_path=args.strategy,
        data_path=args.data,
        notes="Created by experiment run-default.",
    )
    append_experiment_record(record, args.experiments_path)
    return experiment_id


def _write_research_plan(args: argparse.Namespace, experiment_id: str) -> None:
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
    save_research_plan(plan)


def _sweep_args(
    args: argparse.Namespace,
    *,
    experiment_id: str,
    out: Path,
    param: list[str],
    train_end: str | None = None,
    test_start: str | None = None,
    select_by: str = "sharpe_ratio",
    note: str,
) -> argparse.Namespace:
    return _namespace(
        strategy=args.strategy,
        data=args.data,
        out=str(out),
        param=param,
        initial_cash=args.initial_cash,
        quantity=args.quantity,
        sizing=args.sizing,
        allocation=args.allocation,
        run_name=args.run_name,
        train_end=train_end,
        test_start=test_start,
        select_by=select_by,
        walk_forward_window=[],
        benchmark=args.benchmark,
        cost_preset=args.cost_preset,
        commission_fixed=args.commission_fixed,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
        experiments_path=args.experiments_path,
        experiment_id=experiment_id,
        index_path=args.index_path,
        note=note,
        note_file=None,
        command_tokens=_command_tokens("run-default", "sweep"),
    )


def _write_summary_and_conclusion(args: argparse.Namespace, experiment_id: str) -> tuple[str, str]:
    records = load_experiments(args.experiments_path)
    experiment = find_experiment(records, experiment_id)
    index_records = load_research_index(args.index_path)
    summary = format_experiment_evidence_summary(experiment, index_records)
    evidence_summary_path = save_experiment_evidence_summary(summary, Path(args.out) / "evidence_summary.md")
    conclusion = build_experiment_conclusion(
        experiment,
        index_records,
        generator_version=current_git_commit(),
    )
    artifact_paths = save_experiment_conclusion_artifacts(conclusion, args.out, force=True)
    return evidence_summary_path, artifact_paths["markdown"]


def _record_conservative_decision(args: argparse.Namespace, experiment_id: str) -> str:
    records = load_experiments(args.experiments_path)
    experiment = find_experiment(records, experiment_id)
    index_records = load_research_index(args.index_path)
    linked_records = _linked_records(experiment, index_records)
    evidence_label = label_strategy_evidence(linked_records)
    outcome = _decision_outcome(args.decision, evidence_label.label)
    supporting_run = _metadata_path(_best_record(linked_records, "excess_total_return"))
    contradicting_run = _metadata_path(_weakest_record(linked_records, "excess_total_return"))
    decision = create_experiment_decision(
        outcome=outcome,
        rationale=_decision_rationale(evidence_label),
        supporting_run=supporting_run,
        contradicting_run=contradicting_run,
        next_action=_decision_next_action(outcome, evidence_label.label),
    )
    updated = decide_experiment_record(
        experiment,
        decision,
        add_tags=[*DEFAULT_CONSERVATIVE_DECISION_TAGS, *args.tag],
    )
    replace_experiment_record(updated, args.experiments_path)
    return outcome


def _write_workflow_summary(
    *,
    args: argparse.Namespace,
    experiment_id: str,
    baseline_metadata_path: Path,
    trust_report_path: Path,
    sweep_summary_path: Path,
    sweep_guardrail_path: Path,
    train_test_summary_path: Path,
    cost_report_path: Path,
    date_report_path: Path,
    benchmark_report_path: Path,
    evidence_summary_path: Path,
    conclusion_path: Path,
    decision_outcome: str | None,
    captured_output: str,
) -> str:
    path = Path(args.out) / "default_workflow_summary.md"
    lines = [
        "# Default Experiment Workflow Summary",
        "",
        "Report role: supporting interpretation.",
        "",
        f"- Experiment id: `{experiment_id}`",
        f"- Title: {args.title}",
        f"- Decision outcome: {decision_outcome or 'not recorded'}",
        f"- Read first: `{conclusion_path}`",
        "",
        "## Artifacts",
        "",
        f"- Baseline metadata: `{baseline_metadata_path}`",
        f"- Run trust report: `{trust_report_path}`",
        f"- Sweep summary: `{sweep_summary_path}`",
        f"- Sweep guardrails: `{sweep_guardrail_path}`",
        f"- Train/test test summary: `{train_test_summary_path}`",
        f"- Cost sensitivity report: `{cost_report_path}`",
        f"- Date sensitivity report: `{date_report_path}`",
        f"- Benchmark sensitivity report: `{benchmark_report_path}`",
        f"- Evidence summary: `{evidence_summary_path}`",
        f"- Experiment conclusion: `{conclusion_path}`",
        "",
        "## Captured Command Output",
        "",
        "The default workflow suppresses detailed child command output on stdout.",
        "The captured output is saved here for auditability.",
        "",
        "```text",
        captured_output.strip() or "No child command output captured.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def _cost_sensitivity_presets(args: argparse.Namespace) -> list[str]:
    if args.cost_sensitivity_preset:
        return _ordered_unique(args.cost_sensitivity_preset)
    return _ordered_unique([args.cost_preset, "retail-conservative", "high-friction"])


def _benchmark_sensitivity_choices(args: argparse.Namespace) -> list[str]:
    return _ordered_unique([args.benchmark, "cash", "buy-and-hold"])


def _decision_outcome(mode: str, evidence_label: str) -> str:
    if mode == "continue":
        return "continue"
    if evidence_label == "rejected":
        return "reject"
    if evidence_label == "promising":
        return "continue"
    return "continue"


def _decision_rationale(evidence_label) -> str:
    return " ".join(evidence_label.reasons)


def _decision_next_action(outcome: str, evidence_label: str) -> str:
    if outcome == "reject":
        return "Stop this branch or reformulate the hypothesis before widening the search."
    if evidence_label == "promising":
        return "Review the canonical conclusion before deciding whether this deserves a stricter follow-up."
    return "Review weak or mixed evidence before adding more variants."


def _linked_records(experiment, index_records: list[dict]) -> list[dict]:
    linked_paths = set(experiment.linked_runs)
    return [
        record
        for record in index_records
        if str(record.get("experiment_id")) == experiment.experiment_id
        or str(record.get("metadata_path") or "") in linked_paths
    ]


def _best_record(records: list[dict], field: str) -> dict | None:
    return max(records, key=lambda record: _numeric(record.get(field)), default=None)


def _weakest_record(records: list[dict], field: str) -> dict | None:
    return min(records, key=lambda record: _numeric(record.get(field), missing=float("inf")), default=None)


def _numeric(value: object, *, missing: float = float("-inf")) -> float:
    if value is None:
        return missing
    try:
        return float(value)
    except (TypeError, ValueError):
        return missing


def _metadata_path(record: dict | None) -> str | None:
    if not record:
        return None
    value = str(record.get("metadata_path") or "").strip()
    return value or None


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _namespace(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def _command_tokens(*parts: str) -> list[str]:
    return ["quant-lab", *parts]


def validate_default_experiment_args(args: argparse.Namespace) -> None:
    if not args.param:
        raise ValueError("experiment run-default requires at least one --param sweep.")
    if not args.date_window:
        raise ValueError("experiment run-default requires at least one --date-window.")
    unknown_presets = [preset for preset in _cost_sensitivity_presets(args) if preset not in COST_PRESETS]
    if unknown_presets:
        raise ValueError(f"unknown cost sensitivity preset: {unknown_presets[0]}")
