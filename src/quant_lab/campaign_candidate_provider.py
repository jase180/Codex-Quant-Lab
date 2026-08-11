"""Provider adapters for choosing from deterministic campaign candidates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .agent_provider import (
    DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    _chat_completions_url,
    _extract_message_content,
    _post_json,
    _strip_json_fence,
)
from .campaign import CampaignConfig, CampaignState
from .campaign_candidate_choice import (
    CAMPAIGN_CANDIDATE_CHOICE_SCHEMA_VERSION,
    CampaignCandidateChoice,
    deterministic_candidate_choice,
    parse_campaign_candidate_choice,
)
from .campaign_candidates import CampaignCandidateMenu
from .campaign_provider import (
    CAMPAIGN_PROVIDER_CONTEXT_FILENAME,
    CAMPAIGN_PROVIDER_PARSED_PROPOSAL_FILENAME,
    CAMPAIGN_PROVIDER_PROMPT_FILENAME,
    CAMPAIGN_PROVIDER_RAW_RESPONSE_FILENAME,
)
from .research_plan_common import write_json_payload


CAMPAIGN_CANDIDATE_CHOICE_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "campaign_candidate_choice",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "action", "candidate_id", "rationale"],
            "properties": {
                "schema_version": {"type": "string", "const": CAMPAIGN_CANDIDATE_CHOICE_SCHEMA_VERSION},
                "action": {
                    "type": "string",
                    "enum": ["choose_candidate", "request_human_review", "stop_campaign"],
                },
                "candidate_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "rationale": {"type": "string"},
            },
        },
    },
}


@dataclass(frozen=True)
class CampaignCandidateProviderResult:
    provider: str
    choice: CampaignCandidateChoice
    raw_response: str | None
    context_path: str | None
    prompt_path: str | None
    raw_response_path: str | None
    parsed_choice_path: str | None


def campaign_candidate_provider_result(
    config: CampaignConfig,
    state: CampaignState,
    menu: CampaignCandidateMenu,
    *,
    cycle_dir: str | Path | None,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    http_post: Callable[[str, dict, float], dict] | None = None,
    prior_attempt_feedback: list[str] | None = None,
) -> CampaignCandidateProviderResult:
    if config.provider == "deterministic":
        return CampaignCandidateProviderResult(
            provider=config.provider,
            choice=deterministic_candidate_choice(menu),
            raw_response=None,
            context_path=None,
            prompt_path=None,
            raw_response_path=None,
            parsed_choice_path=None,
        )
    if config.provider == "codex":
        context = build_candidate_choice_context(config, state, menu, prior_attempt_feedback=prior_attempt_feedback)
        prompt = build_candidate_choice_prompt(context)
        paths = _write_candidate_provider_artifacts(context, prompt, cycle_dir)
        choice = CampaignCandidateChoice(
            schema_version=CAMPAIGN_CANDIDATE_CHOICE_SCHEMA_VERSION,
            action="request_human_review",
            candidate_id=None,
            rationale=(
                "The standalone campaign CLI wrote candidate-menu context for Codex review; "
                "this chat session must choose a candidate or stop."
            ),
        )
        parsed_choice_path = _write_json_artifact(paths["parsed_choice_path"], choice.to_dict())
        return CampaignCandidateProviderResult(
            provider=config.provider,
            choice=choice,
            raw_response=None,
            context_path=paths["context_path"],
            prompt_path=paths["prompt_path"],
            raw_response_path=None,
            parsed_choice_path=parsed_choice_path,
        )
    if config.provider == "ollama":
        return _ollama_candidate_provider_result(
            config,
            state,
            menu,
            cycle_dir=cycle_dir,
            base_url=base_url or DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
            model=model or "llama3.1:8b",
            timeout_seconds=timeout_seconds,
            http_post=http_post,
            prior_attempt_feedback=prior_attempt_feedback,
        )
    raise ValueError(f"unsupported campaign provider for candidate choice: {config.provider}")


def build_candidate_choice_context(
    config: CampaignConfig,
    state: CampaignState,
    menu: CampaignCandidateMenu,
    *,
    prior_attempt_feedback: list[str] | None = None,
) -> dict:
    context = {
        "schema_version": "campaign_candidate_choice_context.v1",
        "campaign": {
            "title": config.title,
            "objective": config.objective,
            "provider": config.provider,
        },
        "budgets": {
            "remaining": state.remaining_budget,
            "runs_used": state.runs_used,
            "cycle_number": state.cycle_number,
        },
        "candidate_menu": menu.to_dict(),
        "provider_rules": [
            "Return one campaign_candidate_choice.v1 JSON object only.",
            "Choose only a candidate_id present in candidate_menu.candidates.",
            "Do not invent new candidates, strategy templates, parameters, indicators, or shell commands.",
            "Use request_human_review when the menu is ambiguous or exhausted.",
            "Use stop_campaign when candidate_menu.status is SEARCH_SPACE_EXHAUSTED.",
        ],
    }
    if prior_attempt_feedback:
        context["prior_attempt_feedback"] = prior_attempt_feedback
    return context


def build_candidate_choice_prompt(context: dict) -> str:
    feedback = _prior_feedback_prompt_lines(context.get("prior_attempt_feedback"))
    return "\n".join(
        [
            "You are choosing from a bounded quant research candidate menu.",
            "Do not invent an experiment. Choose one candidate ID, request human review, or stop.",
            "",
            "Required JSON schema:",
            "- schema_version: campaign_candidate_choice.v1",
            "- action: choose_candidate, request_human_review, or stop_campaign",
            "- candidate_id: candidate ID from candidate_menu.candidates, or null for non-choice actions",
            "- rationale: concise reason focused on information value",
            *feedback,
            "",
            "Candidate choice context JSON:",
            json.dumps(context, indent=2, sort_keys=True),
            "",
            "Return JSON only.",
        ]
    )


def _ollama_candidate_provider_result(
    config: CampaignConfig,
    state: CampaignState,
    menu: CampaignCandidateMenu,
    *,
    cycle_dir: str | Path | None,
    base_url: str,
    model: str,
    timeout_seconds: float,
    http_post: Callable[[str, dict, float], dict] | None,
    prior_attempt_feedback: list[str] | None,
) -> CampaignCandidateProviderResult:
    if not model.strip():
        raise ValueError("model is required for ollama candidate provider")
    context = build_candidate_choice_context(config, state, menu, prior_attempt_feedback=prior_attempt_feedback)
    prompt = build_candidate_choice_prompt(context)
    paths = _write_candidate_provider_artifacts(context, prompt, cycle_dir)
    post = http_post or _post_json
    payload = post(
        _chat_completions_url(base_url),
        _request_payload(prompt, model=model),
        timeout_seconds,
    )
    raw_response = _extract_message_content(payload)
    raw_response_path = _write_text_artifact(paths["raw_response_path"], raw_response)
    parsed_payload = json.loads(_strip_json_fence(raw_response))
    choice = parse_campaign_candidate_choice(parsed_payload)
    parsed_choice_path = _write_json_artifact(paths["parsed_choice_path"], choice.to_dict())
    return CampaignCandidateProviderResult(
        provider=config.provider,
        choice=choice,
        raw_response=raw_response,
        context_path=paths["context_path"],
        prompt_path=paths["prompt_path"],
        raw_response_path=raw_response_path,
        parsed_choice_path=parsed_choice_path,
    )


def _request_payload(prompt: str, *, model: str) -> dict:
    return {
        "model": model,
        "temperature": 0.0,
        "response_format": CAMPAIGN_CANDIDATE_CHOICE_RESPONSE_FORMAT,
        "messages": [
            {
                "role": "system",
                "content": "You return strict JSON only. You choose from candidate IDs only.",
            },
            {"role": "user", "content": prompt},
        ],
    }


def _write_candidate_provider_artifacts(context: dict, prompt: str, cycle_dir: str | Path | None) -> dict[str, str | None]:
    if cycle_dir is None:
        return {
            "context_path": None,
            "prompt_path": None,
            "raw_response_path": None,
            "parsed_choice_path": None,
        }
    destination = Path(cycle_dir)
    destination.mkdir(parents=True, exist_ok=True)
    context_path = destination / CAMPAIGN_PROVIDER_CONTEXT_FILENAME
    prompt_path = destination / CAMPAIGN_PROVIDER_PROMPT_FILENAME
    write_json_payload(context_path, context)
    prompt_path.write_text(prompt, encoding="utf-8")
    return {
        "context_path": str(context_path),
        "prompt_path": str(prompt_path),
        "raw_response_path": str(destination / CAMPAIGN_PROVIDER_RAW_RESPONSE_FILENAME),
        "parsed_choice_path": str(destination / CAMPAIGN_PROVIDER_PARSED_PROPOSAL_FILENAME),
    }


def _write_text_artifact(path: str | None, content: str) -> str | None:
    if path is None:
        return None
    Path(path).write_text(content, encoding="utf-8")
    return path


def _write_json_artifact(path: str | None, payload: dict) -> str | None:
    if path is None:
        return None
    write_json_payload(path, payload)
    return path


def _prior_feedback_prompt_lines(feedback: object) -> list[str]:
    if not isinstance(feedback, list) or not feedback:
        return []
    lines = ["", "Previous provider attempt was rejected. Fix these issues exactly:"]
    lines.extend(f"- {item}" for item in feedback if str(item).strip())
    return lines
