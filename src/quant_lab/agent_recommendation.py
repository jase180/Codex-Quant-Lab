"""Strict recommendation contract for local-agent advisor output."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .research_plan_common import utc_now_iso, validate_required_text_fields, write_json_payload


AGENT_RECOMMENDATION_SCHEMA_VERSION = "agent_recommendation.v1"
AGENT_RECOMMENDATION_JSON_FILENAME = "agent_recommendation.json"
AGENT_RECOMMENDATION_MARKDOWN_FILENAME = "agent_recommendation.md"
ALLOWED_RECOMMENDED_ACTIONS = {
    "baseline",
    "run_trust",
    "sweep",
    "train_test",
    "walk_forward",
    "summarize",
    "robustness",
    "conclude",
    "decide",
    "research_design",
    "stop",
    "needs_review",
}
CONFIDENCE_VALUES = {"low", "medium", "high"}
COMMAND_REQUIRED_ACTIONS = ALLOWED_RECOMMENDED_ACTIONS - {"research_design", "stop", "needs_review"}
RECOMMENDATION_KEYS = {
    "schema_version",
    "recommended_action",
    "reason",
    "next_command",
    "risks",
    "do_not_repeat",
    "confidence",
    "created_at_utc",
}


@dataclass(frozen=True)
class AgentRecommendation:
    schema_version: str
    recommended_action: str
    reason: str
    next_command: str | None
    risks: list[str] = field(default_factory=list)
    do_not_repeat: list[str] = field(default_factory=list)
    confidence: str = "medium"
    created_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


def create_agent_recommendation(
    *,
    recommended_action: str,
    reason: str,
    next_command: str | None = None,
    risks: list[str] | None = None,
    do_not_repeat: list[str] | None = None,
    confidence: str = "medium",
    created_at_utc: str | None = None,
) -> AgentRecommendation:
    recommendation = AgentRecommendation(
        schema_version=AGENT_RECOMMENDATION_SCHEMA_VERSION,
        recommended_action=recommended_action.strip(),
        reason=reason.strip(),
        next_command=_optional_str(next_command),
        risks=_normalize_text_list(risks or []),
        do_not_repeat=_normalize_text_list(do_not_repeat or []),
        confidence=confidence.strip().lower(),
        created_at_utc=created_at_utc or utc_now_iso(),
    )
    validate_agent_recommendation(recommendation)
    return recommendation


def validate_agent_recommendation(recommendation: AgentRecommendation) -> None:
    validate_required_text_fields(
        {
            "schema_version": recommendation.schema_version,
            "recommended_action": recommendation.recommended_action,
            "reason": recommendation.reason,
            "confidence": recommendation.confidence,
            "created_at_utc": recommendation.created_at_utc,
        },
        context="agent recommendation",
    )
    if recommendation.schema_version != AGENT_RECOMMENDATION_SCHEMA_VERSION:
        raise ValueError(f"unsupported agent recommendation schema: {recommendation.schema_version}")
    if recommendation.recommended_action not in ALLOWED_RECOMMENDED_ACTIONS:
        raise ValueError(f"recommended_action must be one of {sorted(ALLOWED_RECOMMENDED_ACTIONS)}")
    if recommendation.confidence not in CONFIDENCE_VALUES:
        raise ValueError(f"confidence must be one of {sorted(CONFIDENCE_VALUES)}")
    if recommendation.recommended_action in COMMAND_REQUIRED_ACTIONS and not recommendation.next_command:
        raise ValueError(f"next_command is required for action {recommendation.recommended_action}")
    if recommendation.next_command and not recommendation.next_command.startswith("quant-lab "):
        raise ValueError("next_command must start with 'quant-lab '")
    if recommendation.next_command:
        _validate_action_matches_command(recommendation.recommended_action, recommendation.next_command)


def load_agent_recommendation(path: str | Path) -> AgentRecommendation:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("agent recommendation must be a JSON object")
    unknown_keys = set(payload) - RECOMMENDATION_KEYS
    if unknown_keys:
        raise ValueError(f"unknown agent recommendation field(s): {sorted(unknown_keys)}")
    missing_keys = {
        "schema_version",
        "recommended_action",
        "reason",
        "risks",
        "do_not_repeat",
        "confidence",
    } - set(payload)
    if missing_keys:
        raise ValueError(f"missing agent recommendation field(s): {sorted(missing_keys)}")

    recommendation = AgentRecommendation(
        schema_version=str(payload.get("schema_version", "")),
        recommended_action=str(payload.get("recommended_action", "")),
        reason=str(payload.get("reason", "")),
        next_command=_optional_str(payload.get("next_command")),
        risks=_list_from_payload(payload.get("risks"), field_name="risks"),
        do_not_repeat=_list_from_payload(payload.get("do_not_repeat"), field_name="do_not_repeat"),
        confidence=str(payload.get("confidence", "")),
        created_at_utc=str(payload.get("created_at_utc") or utc_now_iso()),
    )
    validate_agent_recommendation(recommendation)
    return recommendation


def save_agent_recommendation(recommendation: AgentRecommendation, output_dir: str | Path) -> tuple[str, str]:
    validate_agent_recommendation(recommendation)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / AGENT_RECOMMENDATION_JSON_FILENAME
    markdown_path = destination / AGENT_RECOMMENDATION_MARKDOWN_FILENAME
    write_json_payload(json_path, recommendation.to_dict())
    markdown_path.write_text(format_agent_recommendation_markdown(recommendation), encoding="utf-8")
    return _display_path(json_path), _display_path(markdown_path)


def format_agent_recommendation_markdown(recommendation: AgentRecommendation) -> str:
    validate_agent_recommendation(recommendation)
    return "\n".join(
        [
            "# Agent Recommendation",
            "",
            "Report role: bounded advisor output.",
            "",
            "## Recommendation",
            "",
            f"- Action: `{recommendation.recommended_action}`",
            f"- Confidence: `{recommendation.confidence}`",
            f"- Created at UTC: `{recommendation.created_at_utc}`",
            "",
            "## Reason",
            "",
            recommendation.reason,
            "",
            "## Next Command",
            "",
            *_command_lines(recommendation.next_command),
            "",
            "## Risks",
            "",
            *_bullet_lines(recommendation.risks),
            "",
            "## Do Not Repeat",
            "",
            *_bullet_lines(recommendation.do_not_repeat),
            "",
        ]
    )


def agent_recommendation_to_json(recommendation: AgentRecommendation) -> str:
    validate_agent_recommendation(recommendation)
    return json.dumps(recommendation.to_dict(), indent=2, sort_keys=True)


def _list_from_payload(value, *, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return _normalize_text_list([str(item) for item in value])


def _normalize_text_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def _optional_str(value) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _command_lines(command: str | None) -> list[str]:
    if command is None:
        return ["- none"]
    return ["```bash", command, "```"]


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- none"]


def _display_path(path: str | Path) -> str:
    return Path(path).as_posix()


def _validate_action_matches_command(action: str, command: str) -> None:
    command_tokens = command.split()
    if len(command_tokens) < 2:
        raise ValueError("next_command must include a quant-lab subcommand")
    subcommand = command_tokens[1]
    expected = {
        "baseline": {"run"},
        "run_trust": {"summarize-run-trust"},
        "sweep": {"sweep"},
        "summarize": {"summarize-experiment", "summarize-portfolio-experiment", "summarize-sweep-guardrails"},
        "conclude": {"conclude-experiment"},
        "decide": {"draft-decision", "decide-experiment"},
    }.get(action)
    if expected is not None and subcommand not in expected:
        raise ValueError(f"next_command subcommand {subcommand!r} does not match recommended_action {action!r}")
