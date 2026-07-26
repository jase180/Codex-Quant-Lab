"""Deterministic local-agent recommendations from saved session state."""

from __future__ import annotations

from pathlib import Path

from .agent_context import AgentContext, build_agent_context
from .agent_recommendation import AgentRecommendation, create_agent_recommendation, save_agent_recommendation
from .session_manifest import SessionManifest, load_session_manifest


STEP_TO_ACTION = {
    "baseline": "baseline",
    "run_trust": "run_trust",
    "sweep": "sweep",
    "train_test": "train_test",
    "walk_forward": "walk_forward",
    "summarize": "summarize",
    "robustness_cost_sensitivity": "robustness",
    "robustness_date_sensitivity": "robustness",
    "robustness_benchmark_sensitivity": "robustness",
    "robustness_parameter_neighborhood": "robustness",
    "conclude_experiment": "conclude",
    "draft_decision": "decide",
    "done": "stop",
}


def suggest_from_manifest(manifest_path: str | Path) -> AgentRecommendation:
    """Create a validated recommendation without calling an LLM."""

    manifest = load_session_manifest(manifest_path)
    context = build_agent_context(manifest_path)
    recommended_step, reason = _recommended_step_and_reason(manifest)
    action = STEP_TO_ACTION.get(recommended_step, "needs_review")
    next_command = _next_command(manifest)
    if action == "stop":
        return create_agent_recommendation(
            recommended_action="stop",
            reason=reason or "The session is complete or has no remaining recommended command.",
            next_command=None,
            risks=[],
            do_not_repeat=_do_not_repeat(action, manifest),
            confidence="high",
        )
    if action == "needs_review" or not next_command:
        return create_agent_recommendation(
            recommended_action="needs_review",
            reason=reason or "The session does not contain a recognized next command.",
            next_command=None,
            risks=_risks(manifest, context),
            do_not_repeat=_do_not_repeat(action, manifest),
            confidence="low",
        )
    return create_agent_recommendation(
        recommended_action=action,
        reason=reason,
        next_command=next_command,
        risks=_risks(manifest, context),
        do_not_repeat=_do_not_repeat(action, manifest),
        confidence=_confidence(action, manifest),
    )


def save_agent_suggestion(recommendation: AgentRecommendation, manifest_path: str | Path, output_dir: str | Path | None = None) -> tuple[str, str]:
    manifest = load_session_manifest(manifest_path)
    destination = Path(output_dir or manifest.output_dir)
    return save_agent_recommendation(recommendation, destination)


def _recommended_step_and_reason(manifest: SessionManifest) -> tuple[str, str]:
    if manifest.current_status == "complete":
        return "done", "The session manifest is complete; no next experiment is recommended."
    if manifest.outstanding_next_steps:
        raw = manifest.outstanding_next_steps[0]
        if ":" in raw:
            step, reason = raw.split(":", 1)
            return step.strip(), reason.strip()
        return raw.strip(), raw.strip()
    command = next((command for command in manifest.commands if command.status != "executed"), None)
    if command is not None and command.label.startswith("Recommended next step:"):
        return command.label.split(":", 1)[1].strip(), "The manifest contains a pending recommended command."
    return "needs_review", "No outstanding next step is recorded in the session manifest."


def _next_command(manifest: SessionManifest) -> str | None:
    command = next((command for command in manifest.commands if command.status != "executed"), None)
    if command is None:
        return None
    return command.command.replace("\\", "/")


def _risks(manifest: SessionManifest, context: AgentContext) -> list[str]:
    risks = [warning.replace("\\", "/") for warning in manifest.warnings]
    for file in context.files:
        if not file.exists:
            risks.append(f"Referenced context file is missing: {file.path}")
        elif not file.included and file.note:
            risks.append(f"Referenced context file was not embedded: {file.path} ({file.note})")
    if manifest.conclusion_path is None and manifest.current_status not in {"planned", "complete"}:
        risks.append("Canonical experiment conclusion is not present yet.")
    return risks


def _do_not_repeat(action: str, manifest: SessionManifest) -> list[str]:
    items = ["Do not edit source code from an agent recommendation."]
    if action in {"sweep", "train_test", "robustness"}:
        items.append("Do not widen the experiment before required trust checks are complete.")
    if manifest.warnings:
        items.append("Do not ignore manifest warnings when interpreting the next result.")
    return items


def _confidence(action: str, manifest: SessionManifest) -> str:
    if manifest.warnings:
        return "medium"
    if action in {"decide", "stop"}:
        return "high"
    return "medium"
