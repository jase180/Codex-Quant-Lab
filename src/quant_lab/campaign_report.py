"""Final campaign report generation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .campaign import CampaignConfig, CampaignPaths, CampaignState
from .research_plan_common import utc_now_iso, write_json_payload


CAMPAIGN_FINAL_REPORT_SCHEMA_VERSION = "campaign_final_report.v1"


@dataclass(frozen=True)
class CampaignFinalReport:
    schema_version: str
    title: str
    objective: str
    status: str
    stop_reason: str | None
    generated_at_utc: str
    experiments_attempted: list[dict[str, Any]]
    technically_invalid_experiments: list[dict[str, Any]]
    hypothesis_status_counts: dict[str, int]
    cumulative_findings: list[str]
    do_not_repeat: list[str]
    unresolved_risks: list[str]
    best_remaining_candidate: dict[str, Any] | None
    consumed_budget: dict[str, int]
    remaining_budget: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def save_final_campaign_report(
    config: CampaignConfig,
    state: CampaignState,
    paths: CampaignPaths,
) -> tuple[str, str]:
    report = build_final_campaign_report(config, state)
    write_json_payload(paths.final_report_json_path, report.to_dict())
    Path(paths.final_report_markdown_path).write_text(_format_final_report_markdown(report), encoding="utf-8")
    return paths.final_report_json_path, paths.final_report_markdown_path


def build_final_campaign_report(config: CampaignConfig, state: CampaignState) -> CampaignFinalReport:
    conclusions = [_load_optional_conclusion(item) for item in state.completed_experiments]
    experiments = [_experiment_summary(item, conclusion) for item, conclusion in zip(state.completed_experiments, conclusions)]
    invalid = [
        item
        for item in experiments
        if item.get("research_system_status") == "invalid"
    ]
    return CampaignFinalReport(
        schema_version=CAMPAIGN_FINAL_REPORT_SCHEMA_VERSION,
        title=config.title,
        objective=config.objective,
        status=state.status,
        stop_reason=state.stop_reason,
        generated_at_utc=utc_now_iso(),
        experiments_attempted=experiments,
        technically_invalid_experiments=invalid,
        hypothesis_status_counts=_status_counts(experiments),
        cumulative_findings=state.current_findings,
        do_not_repeat=state.do_not_repeat,
        unresolved_risks=state.unresolved_questions,
        best_remaining_candidate=_best_remaining_candidate(experiments),
        consumed_budget={
            "cycles": state.cycle_number,
            "runs": state.runs_used,
            "seconds": state.elapsed_seconds,
        },
        remaining_budget=dict(state.remaining_budget),
    )


def _load_optional_conclusion(experiment_record: dict[str, Any]) -> dict[str, Any] | None:
    path = str(experiment_record.get("conclusion_json_path") or "").strip()
    if not path or not Path(path).exists():
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


def _experiment_summary(record: dict[str, Any], conclusion: dict[str, Any] | None) -> dict[str, Any]:
    strategy_status = str(record.get("strategy_hypothesis_status") or "-")
    research_status = str(record.get("research_system_status") or "-")
    summary = {
        "experiment_id": record.get("experiment_id"),
        "title": record.get("title"),
        "research_system_status": research_status,
        "strategy_hypothesis_status": strategy_status,
        "confidence_label": record.get("confidence_label"),
        "conclusion_json_path": record.get("conclusion_json_path"),
        "conclusion_path": record.get("conclusion_path"),
        "projected_run_count": record.get("projected_run_count"),
        "elapsed_seconds": record.get("elapsed_seconds"),
    }
    if conclusion is not None:
        summary["current_conclusion"] = conclusion.get("current_conclusion")
        summary["criteria_results"] = _criteria_results(conclusion)
        summary["robustness_status"] = _robustness_status(conclusion)
    return summary


def _criteria_results(conclusion: dict[str, Any]) -> list[dict[str, Any]]:
    strategy_status = conclusion.get("strategy_hypothesis_status")
    if not isinstance(strategy_status, dict):
        return []
    results = strategy_status.get("criteria_results")
    return list(results) if isinstance(results, list) else []


def _robustness_status(conclusion: dict[str, Any]) -> list[dict[str, Any]]:
    notes = conclusion.get("robustness_notes")
    if not isinstance(notes, list):
        return []
    return [
        {"check": item.get("check"), "status": item.get("status"), "summary": item.get("summary")}
        for item in notes
        if isinstance(item, dict)
    ]


def _status_counts(experiments: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for experiment in experiments:
        status = str(experiment.get("strategy_hypothesis_status") or "-")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _best_remaining_candidate(experiments: list[dict[str, Any]]) -> dict[str, Any] | None:
    for status in ("supported", "partially_supported", "inconclusive"):
        for experiment in experiments:
            if experiment.get("strategy_hypothesis_status") == status:
                return {
                    "title": experiment.get("title"),
                    "strategy_hypothesis_status": status,
                    "confidence_label": experiment.get("confidence_label"),
                    "note": "Candidate only; review the conclusion and unresolved risks before treating it as investable.",
                    "conclusion_json_path": experiment.get("conclusion_json_path"),
                }
    return None


def _format_final_report_markdown(report: CampaignFinalReport) -> str:
    best = report.best_remaining_candidate
    return "\n".join(
        [
            f"# Final Campaign Report: {report.title}",
            "",
            "Report role: campaign front door.",
            "",
            "This report summarizes what the campaign tested. It does not claim a profitable strategy.",
            "",
            "## Objective",
            "",
            report.objective,
            "",
            "## Stop Reason",
            "",
            f"- Status: `{report.status}`",
            f"- Stop reason: {report.stop_reason or '-'}",
            "",
            "## Experiments Attempted",
            "",
            *_experiment_lines(report.experiments_attempted),
            "",
            "## Hypothesis Outcomes",
            "",
            *[f"- {status}: `{count}`" for status, count in sorted(report.hypothesis_status_counts.items())],
            "",
            "## Cumulative Findings",
            "",
            *_bullet_lines(report.cumulative_findings),
            "",
            "## Do Not Repeat",
            "",
            *_bullet_lines(report.do_not_repeat),
            "",
            "## Unresolved Risks",
            "",
            *_bullet_lines(report.unresolved_risks),
            "",
            "## Best Remaining Candidate",
            "",
            _best_candidate_line(best),
            "",
            "## Budget",
            "",
            f"- Runs used: `{report.consumed_budget.get('runs', 0)}`",
            f"- Cycles used: `{report.consumed_budget.get('cycles', 0)}`",
            f"- Seconds used: `{report.consumed_budget.get('seconds', 0)}`",
            f"- Remaining runs: `{report.remaining_budget.get('runs', 0)}`",
            f"- Remaining cycles: `{report.remaining_budget.get('cycles', 0)}`",
            "",
        ]
    )


def _experiment_lines(experiments: list[dict[str, Any]]) -> list[str]:
    if not experiments:
        return ["- none"]
    return [
        (
            f"- `{item.get('experiment_id', '-')}` {item.get('title', '-')}: "
            f"research `{item.get('research_system_status', '-')}`, "
            f"hypothesis `{item.get('strategy_hypothesis_status', '-')}`, "
            f"confidence `{item.get('confidence_label', '-')}`. "
            f"Conclusion: `{item.get('conclusion_path', '-')}`"
        )
        for item in experiments
    ]


def _best_candidate_line(candidate: dict[str, Any] | None) -> str:
    if candidate is None:
        return "- none"
    return (
        f"- {candidate.get('title', '-')}: `{candidate.get('strategy_hypothesis_status', '-')}`. "
        f"{candidate.get('note', '')} Conclusion JSON: `{candidate.get('conclusion_json_path', '-')}`"
    )


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- none"]
