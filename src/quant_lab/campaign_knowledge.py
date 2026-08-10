"""Fold completed experiment conclusions into campaign-level memory."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from .campaign import CampaignConfig, CampaignState
from .research_plan_common import utc_now_iso


def update_campaign_state_after_execution(
    state: CampaignState,
    *,
    config: CampaignConfig,
    execution: Any,
    projected_run_count: int,
) -> CampaignState:
    """Fold a completed experiment conclusion into campaign memory."""

    if execution.status != "completed":
        raise ValueError("campaign state can only advance after a completed execution")
    if not execution.conclusion_json_path:
        raise ValueError("campaign execution is missing conclusion_json_path")
    conclusion = _load_conclusion(execution.conclusion_json_path)
    remaining_budget = _remaining_budget_after(
        state.remaining_budget,
        projected_run_count=projected_run_count,
        elapsed_seconds=execution.elapsed_seconds,
    )
    status, stop_reason = _next_status(
        remaining_budget,
        previous_status=state.status,
        previous_stop_reason=state.stop_reason,
    )
    return replace(
        state,
        status=status,  # type: ignore[arg-type]
        cycle_number=state.cycle_number + 1,
        elapsed_seconds=state.elapsed_seconds + execution.elapsed_seconds,
        runs_used=state.runs_used + projected_run_count,
        completed_experiments=[
            *state.completed_experiments,
            _completed_experiment_record(conclusion, execution, projected_run_count),
        ],
        current_findings=_ordered_unique([*state.current_findings, *_findings(conclusion)]),
        do_not_repeat=_ordered_unique(
            [
                *state.do_not_repeat,
                *_text_list(conclusion.get("do_not_repeat")),
                *_branch_repetition_rules(conclusion),
            ]
        ),
        unresolved_questions=_ordered_unique(
            [*state.unresolved_questions, *_text_list(conclusion.get("open_questions"))]
        ),
        remaining_budget=remaining_budget,
        stop_reason=stop_reason,
        updated_at_utc=utc_now_iso(),
    )


def complete_campaign_state(state: CampaignState, *, stop_reason: str) -> CampaignState:
    """Mark campaign state complete without consuming another experiment cycle."""

    return replace(
        state,
        status="complete",
        stop_reason=stop_reason,
        updated_at_utc=utc_now_iso(),
    )


def _remaining_budget_after(
    remaining_budget: dict[str, int],
    *,
    projected_run_count: int,
    elapsed_seconds: int,
) -> dict[str, int]:
    updated = dict(remaining_budget)
    updated["cycles"] = max(0, updated.get("cycles", 0) - 1)
    updated["runs"] = max(0, updated.get("runs", 0) - projected_run_count)
    updated["seconds"] = max(0, updated.get("seconds", 0) - elapsed_seconds)
    return updated


def _load_conclusion(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("experiment conclusion must be a JSON object")
    if str(payload.get("schema_version")) != "experiment_conclusion.v1":
        raise ValueError("unsupported experiment conclusion schema_version")
    return payload


def _completed_experiment_record(
    conclusion: dict[str, Any],
    execution: Any,
    projected_run_count: int,
) -> dict[str, Any]:
    experiment = _mapping(conclusion.get("experiment"))
    research_system = _mapping(conclusion.get("research_system_status"))
    strategy_hypothesis = _mapping(conclusion.get("strategy_hypothesis_status"))
    return {
        "experiment_id": conclusion.get("experiment_id"),
        "title": experiment.get("title"),
        "opportunity_thesis_id": _opportunity_thesis_id(experiment),
        "research_system_status": research_system.get("status"),
        "strategy_hypothesis_status": strategy_hypothesis.get("status"),
        "confidence_label": conclusion.get("confidence_label"),
        "conclusion_path": execution.conclusion_path,
        "conclusion_json_path": execution.conclusion_json_path,
        "projected_run_count": projected_run_count,
        "elapsed_seconds": execution.elapsed_seconds,
    }


def _findings(conclusion: dict[str, Any]) -> list[str]:
    experiment = _mapping(conclusion.get("experiment"))
    research_system = _mapping(conclusion.get("research_system_status"))
    strategy_hypothesis = _mapping(conclusion.get("strategy_hypothesis_status"))
    title = str(experiment.get("title") or conclusion.get("experiment_id") or "experiment")
    current = str(conclusion.get("current_conclusion") or "").strip()
    status_line = (
        f"{title}: research system `{research_system.get('status', '-')}`, "
        f"strategy hypothesis `{strategy_hypothesis.get('status', '-')}`."
    )
    return [line for line in (status_line, current) if line]


def _branch_repetition_rules(conclusion: dict[str, Any]) -> list[str]:
    experiment = _mapping(conclusion.get("experiment"))
    strategy_hypothesis = _mapping(conclusion.get("strategy_hypothesis_status"))
    if strategy_hypothesis.get("status") != "rejected":
        return []
    title = str(experiment.get("title") or "").strip()
    if not title:
        return []
    return [f"Do not repeat unchanged rejected experiment: {title}."]


def _opportunity_thesis_id(experiment: dict[str, Any]) -> str | None:
    for tag in _text_list(experiment.get("tags")):
        if tag.startswith("opportunity:"):
            thesis_id = tag.removeprefix("opportunity:").strip()
            return thesis_id or None
    return None


def _next_status(
    remaining_budget: dict[str, int],
    *,
    previous_status: str,
    previous_stop_reason: str | None,
) -> tuple[str, str | None]:
    if remaining_budget.get("cycles", 0) <= 0:
        return "complete", "maximum campaign cycles completed"
    if remaining_budget.get("runs", 0) <= 0:
        return "complete", "maximum total runs exhausted"
    if remaining_budget.get("seconds", 0) <= 0:
        return "complete", "duration budget exhausted"
    return previous_status, previous_stop_reason


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
