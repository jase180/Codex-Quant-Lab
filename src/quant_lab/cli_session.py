"""CLI command handlers for session manifests."""

from __future__ import annotations

import argparse
from pathlib import Path

from .research_index import filter_index_records, load_research_index
from .research_plan import load_research_plan, research_plan_markdown_path
from .research_plan_workflow import (
    evidence_summary_exists,
    experiment_conclusion_exists,
    experiment_has_decision,
    parameter_neighborhood_exists,
    recommend_next_step,
    run_trust_report_exists,
)
from .research_registry import load_experiments
from .session_manifest import (
    SessionArtifact,
    SessionCommand,
    create_session_manifest,
    format_session_replay_plan,
    format_session_status,
    load_session_manifest,
    save_session_manifest,
)


def session_status_command(args: argparse.Namespace) -> int:
    manifest = load_session_manifest(args.manifest)
    print(format_session_status(manifest))
    return 0


def session_replay_plan_command(args: argparse.Namespace) -> int:
    manifest = load_session_manifest(args.manifest)
    print(format_session_replay_plan(manifest, include_executed=args.include_executed))
    return 0


def session_refresh_command(args: argparse.Namespace) -> int:
    manifest = build_session_manifest_from_research_plan(args.plan)
    json_path, markdown_path = save_session_manifest(manifest)

    print(f"Session manifest refreshed: {json_path}")
    print(f"markdown: {markdown_path}")
    print(f"status: {manifest.current_status}")
    if manifest.outstanding_next_steps:
        print(f"next: {manifest.outstanding_next_steps[0]}")
    return 0


def build_session_manifest_from_research_plan(plan_path: str | Path):
    plan_file = Path(plan_path)
    plan = load_research_plan(plan_file)
    output_dir = Path(plan.output_dir)
    index_records = filter_index_records(load_research_index(plan.index_path), experiment_id=plan.experiment_id)
    experiments = load_experiments(plan.experiments_path)
    experiment = next((record for record in experiments if record.experiment_id == plan.experiment_id), None)
    has_decision = experiment_has_decision(experiment)
    recommendation = recommend_next_step(
        plan,
        index_records,
        experiment_has_decision=has_decision,
        run_trust_report_exists=run_trust_report_exists(index_records),
        evidence_summary_exists=evidence_summary_exists(plan.output_dir),
        parameter_neighborhood_exists=parameter_neighborhood_exists(plan.output_dir),
        experiment_conclusion_exists=experiment_conclusion_exists(plan.output_dir),
    )

    return create_session_manifest(
        session_id=f"session-{plan.experiment_id.lower()}",
        experiment_id=plan.experiment_id,
        title=plan.title,
        hypothesis=plan.hypothesis,
        plan_path=plan_file,
        output_dir=output_dir,
        data_sources=[plan.data_path],
        strategy_paths=[plan.strategy_path],
        commands=_session_commands(recommendation),
        key_artifacts=_key_artifacts(plan_file, output_dir, index_records),
        conclusion_path=_conclusion_path(output_dir),
        decision_path=f"experiment:{plan.experiment_id}" if has_decision else None,
        current_status=_manifest_status(recommendation.step),
        outstanding_next_steps=_outstanding_next_steps(recommendation),
        warnings=_manifest_warnings(output_dir, recommendation.step, index_records, experiment_has_decision=has_decision),
    )


def _session_commands(recommendation) -> list[SessionCommand]:
    if recommendation.command is None:
        return []
    return [
        SessionCommand(
            label=f"Recommended next step: {recommendation.step}",
            command=recommendation.command,
            status="suggested",
        )
    ]


def _key_artifacts(plan_file: Path, output_dir: Path, index_records: list[dict]) -> list[SessionArtifact]:
    artifacts = [SessionArtifact(kind="research_plan", path=str(plan_file), role="plan")]
    plan_markdown = research_plan_markdown_path(output_dir)
    if plan_markdown.exists():
        artifacts.append(SessionArtifact(kind="research_plan_markdown", path=str(plan_markdown), role="plan"))

    known_paths = [
        ("experiment_conclusion", output_dir / "experiment_conclusion.md", "main"),
        ("experiment_conclusion_json", output_dir / "experiment_conclusion.json", "main"),
        ("agent_context", output_dir / "agent_context.md", "supporting"),
        ("evidence_summary", output_dir / "evidence_summary.md", "supporting"),
        ("parameter_neighborhood", output_dir / "robustness" / "parameters" / "parameter_neighborhood_report.md", "supporting"),
    ]
    for kind, path, role in known_paths:
        if path.exists():
            artifacts.append(SessionArtifact(kind=kind, path=str(path), role=role))

    for metadata_path in _metadata_paths(index_records):
        artifacts.append(SessionArtifact(kind="run_metadata", path=metadata_path, role="raw_audit"))
        trust_path = Path(metadata_path).parent / "run_trust_report.md"
        if trust_path.exists():
            artifacts.append(SessionArtifact(kind="run_trust_report", path=str(trust_path), role="supporting"))
    return artifacts


def _metadata_paths(index_records: list[dict]) -> list[str]:
    paths: list[str] = []
    for record in index_records:
        metadata_path = str(record.get("metadata_path") or "").strip()
        if metadata_path and metadata_path not in paths:
            paths.append(metadata_path)
    return paths


def _conclusion_path(output_dir: Path) -> str | None:
    markdown_path = output_dir / "experiment_conclusion.md"
    if markdown_path.exists():
        return str(markdown_path)
    return None


def _manifest_status(recommended_step: str) -> str:
    if recommended_step == "baseline":
        return "planned"
    if recommended_step == "conclude_experiment":
        return "needs_conclusion"
    if recommended_step == "draft_decision":
        return "needs_decision"
    if recommended_step == "done":
        return "complete"
    return "in_progress"


def _outstanding_next_steps(recommendation) -> list[str]:
    if recommendation.step == "done":
        return []
    return [f"{recommendation.step}: {recommendation.reason}"]


def _manifest_warnings(
    output_dir: Path,
    recommended_step: str,
    index_records: list[dict],
    *,
    experiment_has_decision: bool = False,
) -> list[str]:
    warnings: list[str] = []
    conclusion_markdown = output_dir / "experiment_conclusion.md"
    conclusion_json = output_dir / "experiment_conclusion.json"
    evidence_summary = output_dir / "evidence_summary.md"
    parameter_report = output_dir / "robustness" / "parameters" / "parameter_neighborhood_report.md"
    if conclusion_json.exists() and not conclusion_markdown.exists():
        warnings.append("experiment_conclusion.json exists, but experiment_conclusion.md is missing.")
    if conclusion_markdown.exists() and not conclusion_json.exists():
        warnings.append("experiment_conclusion.md exists, but experiment_conclusion.json is missing.")
    if recommended_step == "conclude_experiment":
        warnings.append("Canonical conclusion is missing; run the recommended conclusion command before deciding.")
    if experiment_has_decision and not conclusion_markdown.exists():
        warnings.append("A registry decision exists, but experiment_conclusion.md is missing.")
    if conclusion_markdown.exists() and evidence_summary.exists() and evidence_summary.stat().st_mtime > conclusion_markdown.stat().st_mtime:
        warnings.append("evidence_summary.md is newer than experiment_conclusion.md; refresh the canonical conclusion before relying on it.")
    if conclusion_markdown.exists() and parameter_report.exists() and parameter_report.stat().st_mtime > conclusion_markdown.stat().st_mtime:
        warnings.append(
            "parameter_neighborhood_report.md is newer than experiment_conclusion.md; refresh the canonical conclusion before relying on it."
        )
    warnings.extend(_missing_metadata_warnings(index_records))
    warnings.extend(_missing_run_trust_warnings(index_records))
    return warnings


def _missing_metadata_warnings(index_records: list[dict]) -> list[str]:
    warnings: list[str] = []
    for metadata_path in _metadata_paths(index_records):
        if not Path(metadata_path).exists():
            warnings.append(f"Linked run metadata is missing: {metadata_path}")
    return warnings


def _missing_run_trust_warnings(index_records: list[dict]) -> list[str]:
    warnings: list[str] = []
    for record in index_records:
        if str(record.get("run_type")) != "run":
            continue
        metadata_path = str(record.get("metadata_path") or "").strip()
        if not metadata_path:
            continue
        trust_path = Path(metadata_path).parent / "run_trust_report.md"
        if Path(metadata_path).exists() and not trust_path.exists():
            warnings.append(f"Baseline run metadata exists, but run_trust_report.md is missing beside {metadata_path}.")
    return warnings
