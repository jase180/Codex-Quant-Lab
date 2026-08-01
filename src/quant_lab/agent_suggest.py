"""Deterministic local-agent recommendations from saved session state."""

from __future__ import annotations

from pathlib import Path

from .agent_context import (
    AgentContext,
    build_agent_context,
    next_research_prompt_from_context,
    next_research_prompt_items,
)
from .agent_recommendation import AgentRecommendation, create_agent_recommendation, save_agent_recommendation
from .agent_provider import (
    DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    suggest_with_openai_compatible_provider,
)
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
    "research_design": "research_design",
    "reformulate_hypothesis": "research_design",
    "done": "stop",
}


def suggest_from_manifest(
    manifest_path: str | Path,
    *,
    provider: str = "deterministic",
    base_url: str = DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
    model: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    http_post=None,
) -> AgentRecommendation:
    """Create a validated recommendation, with deterministic fallback."""

    manifest = load_session_manifest(manifest_path)
    context = build_agent_context(manifest_path)
    deterministic = _deterministic_recommendation(manifest, context)
    if deterministic.recommended_action == "stop":
        return deterministic
    if provider == "deterministic":
        return deterministic
    if provider != "openai-compatible":
        raise ValueError("provider must be deterministic or openai-compatible")
    if model is None or not model.strip():
        raise ValueError("--model is required when --provider openai-compatible")

    model_result = suggest_with_openai_compatible_provider(
        context,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        http_post=http_post,
    )
    if model_result.recommendation is not None:
        return model_result.recommendation
    return _with_fallback_risk(deterministic, model_result.error or "model provider returned no recommendation")


def _deterministic_recommendation(manifest: SessionManifest, context: AgentContext) -> AgentRecommendation:
    recommended_step, reason = _recommended_step_and_reason(manifest)
    action = STEP_TO_ACTION.get(recommended_step, "needs_review")
    next_command = _next_command(manifest)
    prompt = next_research_prompt_from_context(context)
    reason = _reason_with_prompt(reason, prompt)
    if action == "stop":
        return create_agent_recommendation(
            recommended_action="stop",
            reason=reason or "The session is complete or has no remaining recommended command.",
            next_command=None,
            risks=[],
            do_not_repeat=_do_not_repeat(action, manifest, context),
            confidence="high",
        )
    if action == "research_design":
        return create_agent_recommendation(
            recommended_action="research_design",
            reason=reason or "The next step is to reformulate the research hypothesis before running commands.",
            next_command=None,
            risks=_risks(manifest, context),
            do_not_repeat=_do_not_repeat(action, manifest, context),
            confidence=_confidence(action, manifest),
        )
    if action == "needs_review" or not next_command:
        return create_agent_recommendation(
            recommended_action="needs_review",
            reason=reason or "The session does not contain a recognized next command.",
            next_command=None,
            risks=_risks(manifest, context),
            do_not_repeat=_do_not_repeat(action, manifest, context),
            confidence="low",
        )
    return create_agent_recommendation(
        recommended_action=action,
        reason=reason,
        next_command=next_command,
        risks=_risks(manifest, context),
        do_not_repeat=_do_not_repeat(action, manifest, context),
        confidence=_confidence(action, manifest),
    )


def save_agent_suggestion(recommendation: AgentRecommendation, manifest_path: str | Path, output_dir: str | Path | None = None) -> tuple[str, str]:
    manifest = load_session_manifest(manifest_path)
    destination = Path(output_dir or manifest.output_dir)
    return save_agent_recommendation(recommendation, destination)


def _with_fallback_risk(recommendation: AgentRecommendation, error: str) -> AgentRecommendation:
    return create_agent_recommendation(
        recommended_action=recommendation.recommended_action,
        reason=f"{recommendation.reason} Deterministic fallback used because model suggestion failed.",
        next_command=recommendation.next_command,
        risks=[*recommendation.risks, f"Model provider failed or returned invalid output: {error}"],
        do_not_repeat=recommendation.do_not_repeat,
        confidence="low",
        created_at_utc=recommendation.created_at_utc,
    )


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
    prompt = next_research_prompt_from_context(context)
    risks.extend(f"Next research prompt warning: {item}" for item in next_research_prompt_items(prompt, "what_failed")[:3])
    for file in context.files:
        if not file.exists:
            risks.append(f"Referenced context file is missing: {file.path}")
        elif not file.included and file.note:
            risks.append(f"Referenced context file was not embedded: {file.path} ({file.note})")
    if manifest.conclusion_path is None and manifest.current_status not in {"planned", "complete"}:
        risks.append("Canonical experiment conclusion is not present yet.")
    return risks


def _do_not_repeat(action: str, manifest: SessionManifest, context: AgentContext) -> list[str]:
    items = ["Do not edit source code from an agent recommendation."]
    if action in {"sweep", "train_test", "robustness"}:
        items.append("Do not widen the experiment before required trust checks are complete.")
    if manifest.warnings:
        items.append("Do not ignore manifest warnings when interpreting the next result.")
    prompt = next_research_prompt_from_context(context)
    items.extend(next_research_prompt_items(prompt, "constraints")[:5])
    return items


def _reason_with_prompt(reason: str, prompt: dict | None) -> str:
    next_items = next_research_prompt_items(prompt, "next_experiment_should")
    if not next_items:
        return reason
    return f"{reason} Next research prompt says: {next_items[0]}"


def _confidence(action: str, manifest: SessionManifest) -> str:
    if manifest.warnings:
        return "medium"
    if action in {"decide", "stop"}:
        return "high"
    return "medium"
