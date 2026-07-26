"""Local-model provider adapters for agent recommendations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable
from urllib import request
from urllib.error import HTTPError, URLError

from .agent_context import AgentContext, agent_context_to_json
from .agent_recommendation import (
    AGENT_RECOMMENDATION_SCHEMA_VERSION,
    RECOMMENDATION_KEYS,
    AgentRecommendation,
    create_agent_recommendation,
)


DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "http://localhost:11434/v1"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_TEMPERATURE = 0.0


@dataclass(frozen=True)
class ModelSuggestionResult:
    recommendation: AgentRecommendation | None
    raw_response: str | None
    error: str | None


def suggest_with_openai_compatible_provider(
    context: AgentContext,
    *,
    base_url: str,
    model: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    temperature: float = DEFAULT_TEMPERATURE,
    http_post: Callable[[str, dict, float], dict] | None = None,
) -> ModelSuggestionResult:
    """Ask an OpenAI-compatible local model for an agent recommendation."""

    if not model.strip():
        raise ValueError("model is required for openai-compatible provider")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    post = http_post or _post_json
    try:
        payload = post(
            _chat_completions_url(base_url),
            _request_payload(context, model=model, temperature=temperature),
            timeout_seconds,
        )
        content = _extract_message_content(payload)
        recommendation = _recommendation_from_model_content(content)
        return ModelSuggestionResult(recommendation=recommendation, raw_response=content, error=None)
    except Exception as exc:
        return ModelSuggestionResult(recommendation=None, raw_response=None, error=str(exc))


def build_agent_prompt(context: AgentContext) -> str:
    return "\n".join(
        [
            "You are a bounded quant research advisor.",
            "Read the context bundle and return exactly one JSON object.",
            "Do not include Markdown, prose, code fences, or extra keys.",
            "Do not edit source code. Do not run commands.",
            "Recommend the next experiment or analysis step and stop.",
            "The JSON must validate as agent_recommendation.v1.",
            "",
            "Required keys:",
            "schema_version, recommended_action, reason, next_command, risks, do_not_repeat, confidence",
            "",
            "Required value types:",
            "schema_version: string",
            "recommended_action: string",
            "reason: string",
            "next_command: string or null",
            "risks: array of strings",
            "do_not_repeat: array of strings",
            "confidence: string",
            "",
            "Allowed recommended_action values:",
            "baseline, run_trust, sweep, train_test, walk_forward, summarize, robustness, conclude, decide, stop, needs_review",
            "",
            "Allowed confidence values: low, medium, high",
            "Runnable actions require next_command starting with 'quant-lab '.",
            "stop and needs_review may use null next_command.",
            "",
            "Use this exact JSON shape:",
            "{",
            '  "schema_version": "agent_recommendation.v1",',
            '  "recommended_action": "run_trust",',
            '  "reason": "One concise reason.",',
            '  "next_command": "quant-lab example",',
            '  "risks": ["One risk."],',
            '  "do_not_repeat": ["One thing not to repeat."],',
            '  "confidence": "medium"',
            "}",
            "",
            "Context bundle JSON:",
            agent_context_to_json(context),
        ]
    )


def _request_payload(context: AgentContext, *, model: str, temperature: float) -> dict:
    return {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You return strict JSON only. You are not allowed to edit files or run commands.",
            },
            {
                "role": "user",
                "content": build_agent_prompt(context),
            },
        ],
    }


def _post_json(url: str, payload: dict, timeout_seconds: float) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"provider HTTP error {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"provider connection error: {exc.reason}") from exc
    return json.loads(response_body)


def _chat_completions_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return f"{cleaned}/chat/completions"


def _extract_message_content(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("provider response missing choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("provider response missing message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("provider response missing message content")
    return content.strip()


def _recommendation_from_model_content(content: str) -> AgentRecommendation:
    try:
        payload = json.loads(_strip_json_fence(content))
    except json.JSONDecodeError as exc:
        raise ValueError(f"model output was not valid JSON: {exc}") from exc

    return _recommendation_from_payload(payload)


def _recommendation_from_payload(payload: dict) -> AgentRecommendation:
    if not isinstance(payload, dict):
        raise ValueError("model output must be a JSON object")
    unknown_keys = set(payload) - RECOMMENDATION_KEYS
    if unknown_keys:
        raise ValueError(f"model output has unknown field(s): {sorted(unknown_keys)}")
    missing_keys = {
        "schema_version",
        "recommended_action",
        "reason",
        "risks",
        "do_not_repeat",
        "confidence",
    } - set(payload)
    if missing_keys:
        raise ValueError(f"model output is missing field(s): {sorted(missing_keys)}")
    if payload.get("schema_version") != AGENT_RECOMMENDATION_SCHEMA_VERSION:
        raise ValueError(f"model output schema_version must be {AGENT_RECOMMENDATION_SCHEMA_VERSION}")
    risks = payload.get("risks", [])
    do_not_repeat = payload.get("do_not_repeat", [])
    if not isinstance(risks, list):
        raise ValueError("model output risks must be a list")
    if not isinstance(do_not_repeat, list):
        raise ValueError("model output do_not_repeat must be a list")
    return create_agent_recommendation(
        recommended_action=str(payload.get("recommended_action", "")),
        reason=str(payload.get("reason", "")),
        next_command=payload.get("next_command"),
        risks=[str(item) for item in risks],
        do_not_repeat=[str(item) for item in do_not_repeat],
        confidence=str(payload.get("confidence", "")),
        created_at_utc=str(payload.get("created_at_utc")) if payload.get("created_at_utc") else None,
    )


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped
