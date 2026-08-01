"""Human-gated local-agent cycle records.

The cycle command is intentionally one step at a time for now. It packages the
context and recommendation into a single audit artifact, then stops before any
suggested command can run.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .agent_context import AgentContext, build_agent_context, save_agent_context
from .agent_recommendation import AgentRecommendation, save_agent_recommendation
from .agent_suggest import suggest_from_manifest
from .research_plan_common import utc_now_iso, write_json_payload
from .session_manifest import load_session_manifest


AGENT_CYCLE_SCHEMA_VERSION = "agent_cycle.v1"
AGENT_CYCLE_JSON_FILENAME = "agent_cycle.json"
AGENT_CYCLE_MARKDOWN_FILENAME = "agent_cycle.md"


@dataclass(frozen=True)
class AgentCycleResult:
    schema_version: str
    created_at_utc: str
    manifest_path: str
    dry_run: bool
    provider: str
    model: str | None
    context_json_path: str
    context_markdown_path: str
    recommendation_json_path: str
    recommendation_markdown_path: str
    cycle_json_path: str
    cycle_markdown_path: str
    recommended_action: str
    proposed_command: str | None
    stop_reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def run_agent_cycle(
    manifest_path: str | Path,
    *,
    dry_run: bool,
    provider: str = "deterministic",
    base_url: str = "http://localhost:11434/v1",
    model: str | None = None,
    timeout_seconds: float = 60.0,
    output_dir: str | Path | None = None,
    http_post=None,
) -> AgentCycleResult:
    """Create one bounded cycle artifact without executing the recommendation."""

    if not dry_run:
        raise ValueError("agent cycle currently supports --dry-run only")

    manifest = load_session_manifest(manifest_path)
    destination = Path(output_dir or Path(manifest.output_dir) / "agent_cycle")
    context = build_agent_context(manifest_path)
    context_json_path, context_markdown_path = save_agent_context(context, destination)
    recommendation = suggest_from_manifest(
        manifest_path,
        provider=provider,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        http_post=http_post,
    )
    recommendation_json_path, recommendation_markdown_path = save_agent_recommendation(recommendation, destination)
    cycle_json_path = (destination / AGENT_CYCLE_JSON_FILENAME).as_posix()
    cycle_markdown_path = (destination / AGENT_CYCLE_MARKDOWN_FILENAME).as_posix()
    result = _cycle_result(
        manifest_path=manifest_path,
        dry_run=dry_run,
        provider=provider,
        model=model,
        context=context,
        recommendation=recommendation,
        context_json_path=context_json_path,
        context_markdown_path=context_markdown_path,
        recommendation_json_path=recommendation_json_path,
        recommendation_markdown_path=recommendation_markdown_path,
        cycle_json_path=cycle_json_path,
        cycle_markdown_path=cycle_markdown_path,
    )
    _save_agent_cycle(result, destination)
    return result


def format_agent_cycle_markdown(result: AgentCycleResult) -> str:
    return "\n".join(
        [
            "# Agent Cycle",
            "",
            "Report role: human-gated advisor cycle.",
            "",
            "## Status",
            "",
            f"- Dry run: `{result.dry_run}`",
            f"- Provider: `{result.provider}`",
            f"- Model: `{result.model or '-'}`",
            f"- Created at UTC: `{result.created_at_utc}`",
            "",
            "## Recommendation",
            "",
            f"- Action: `{result.recommended_action}`",
            f"- Stop reason: {result.stop_reason}",
            "",
            "## Proposed Command",
            "",
            *_command_lines(result.proposed_command),
            "",
            "## Artifacts",
            "",
            f"- Context JSON: `{result.context_json_path}`",
            f"- Context Markdown: `{result.context_markdown_path}`",
            f"- Recommendation JSON: `{result.recommendation_json_path}`",
            f"- Recommendation Markdown: `{result.recommendation_markdown_path}`",
            f"- Cycle JSON: `{result.cycle_json_path}`",
            f"- Cycle Markdown: `{result.cycle_markdown_path}`",
            "",
        ]
    )


def agent_cycle_to_json(result: AgentCycleResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True)


def _cycle_result(
    *,
    manifest_path: str | Path,
    dry_run: bool,
    provider: str,
    model: str | None,
    context: AgentContext,
    recommendation: AgentRecommendation,
    context_json_path: str,
    context_markdown_path: str,
    recommendation_json_path: str,
    recommendation_markdown_path: str,
    cycle_json_path: str,
    cycle_markdown_path: str,
) -> AgentCycleResult:
    return AgentCycleResult(
        schema_version=AGENT_CYCLE_SCHEMA_VERSION,
        created_at_utc=utc_now_iso(),
        manifest_path=Path(manifest_path).as_posix(),
        dry_run=dry_run,
        provider=provider,
        model=model,
        context_json_path=context_json_path,
        context_markdown_path=context_markdown_path,
        recommendation_json_path=recommendation_json_path,
        recommendation_markdown_path=recommendation_markdown_path,
        cycle_json_path=cycle_json_path,
        cycle_markdown_path=cycle_markdown_path,
        recommended_action=recommendation.recommended_action,
        proposed_command=recommendation.next_command,
        stop_reason=_stop_reason(context, recommendation),
    )


def _save_agent_cycle(result: AgentCycleResult, output_dir: str | Path) -> tuple[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / AGENT_CYCLE_JSON_FILENAME
    markdown_path = destination / AGENT_CYCLE_MARKDOWN_FILENAME
    write_json_payload(json_path, result.to_dict())
    markdown_path.write_text(format_agent_cycle_markdown(result), encoding="utf-8")
    return json_path.as_posix(), markdown_path.as_posix()


def _stop_reason(context: AgentContext, recommendation: AgentRecommendation) -> str:
    if recommendation.recommended_action in {"research_design", "stop", "needs_review"}:
        return f"Recommendation action is {recommendation.recommended_action}; human review required."
    if context.warnings:
        return "Dry run stopped before execution because the session manifest has warnings."
    return "Dry run stopped before execution by design."


def _command_lines(command: str | None) -> list[str]:
    if command is None:
        return ["- none"]
    return ["```bash", command, "```"]
