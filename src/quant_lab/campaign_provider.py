"""Campaign proposal provider boundary.

Campaign providers are intentionally narrow: they may read campaign context and
return one strict proposal, but they do not execute commands or mutate campaign
state. That boundary lets a model help choose research while Python keeps the
keys to budgets, validation, and backtest execution.
"""

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
from .campaign_proposal import (
    CampaignProposal,
    deterministic_campaign_proposal,
    parse_campaign_proposal,
)
from .campaign_provider_prompt import (
    CAMPAIGN_PROPOSAL_RESPONSE_FORMAT,
    build_campaign_provider_context,
    build_campaign_provider_prompt,
)
from .research_plan_common import utc_now_iso, write_json_payload


DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
CAMPAIGN_PROVIDER_CONTEXT_FILENAME = "provider_context.json"
CAMPAIGN_PROVIDER_PROMPT_FILENAME = "provider_prompt.md"
CAMPAIGN_PROVIDER_RAW_RESPONSE_FILENAME = "provider_raw_response.txt"
CAMPAIGN_PROVIDER_PARSED_PROPOSAL_FILENAME = "provider_proposal.json"
CAMPAIGN_PROVIDER_ERROR_JSON_FILENAME = "provider_error.json"
CAMPAIGN_PROVIDER_ERROR_MARKDOWN_FILENAME = "provider_error.md"
@dataclass(frozen=True)
class CampaignProviderResult:
    provider: str
    proposal: CampaignProposal
    raw_response: str | None
    context_path: str | None
    prompt_path: str | None
    raw_response_path: str | None
    parsed_proposal_path: str | None


def campaign_provider_proposal(config: CampaignConfig, state: CampaignState) -> CampaignProposal:
    """Return one campaign proposal from the configured provider.

    The controller owns validation, execution, budgets, and persistence. A
    provider only returns a strict `CampaignProposal`, which keeps future model
    adapters from gaining control over the campaign loop.
    """

    if config.provider == "deterministic":
        return deterministic_campaign_proposal(config, state)
    if config.provider == "ollama":
        result = campaign_provider_result(config, state, cycle_dir=None)
        return result.proposal
    if config.provider == "codex":
        raise NotImplementedError(
            f"campaign provider {config.provider!r} is not implemented yet; use provider 'deterministic'"
        )
    raise ValueError(f"unsupported campaign provider: {config.provider}")


def campaign_provider_result(
    config: CampaignConfig,
    state: CampaignState,
    *,
    cycle_dir: str | Path | None,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    http_post: Callable[[str, dict, float], dict] | None = None,
) -> CampaignProviderResult:
    """Return one provider proposal and save model-provider artifacts when possible."""

    if config.provider == "deterministic":
        return CampaignProviderResult(
            provider=config.provider,
            proposal=deterministic_campaign_proposal(config, state),
            raw_response=None,
            context_path=None,
            prompt_path=None,
            raw_response_path=None,
            parsed_proposal_path=None,
        )
    if config.provider == "ollama":
        return _ollama_campaign_provider_result(
            config,
            state,
            cycle_dir=cycle_dir,
            base_url=base_url or DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
            model=model or DEFAULT_OLLAMA_MODEL,
            timeout_seconds=timeout_seconds,
            http_post=http_post,
        )
    if config.provider == "codex":
        raise NotImplementedError(
            f"campaign provider {config.provider!r} is not implemented yet; use provider 'deterministic'"
        )
    raise ValueError(f"unsupported campaign provider: {config.provider}")


def save_campaign_provider_error_artifacts(
    *,
    cycle_dir: str | Path,
    provider: str,
    error: str,
) -> tuple[str, str]:
    """Persist a failed provider attempt so the campaign does not fail silently."""

    destination = Path(cycle_dir)
    destination.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "campaign_provider_error.v1",
        "provider": provider,
        "error": error,
        "created_at_utc": utc_now_iso(),
    }
    json_path = destination / CAMPAIGN_PROVIDER_ERROR_JSON_FILENAME
    markdown_path = destination / CAMPAIGN_PROVIDER_ERROR_MARKDOWN_FILENAME
    write_json_payload(json_path, payload)
    markdown_path.write_text(
        "\n".join(
            [
                "# Campaign Provider Error",
                "",
                "Report role: failed provider attempt receipt.",
                "",
                f"- Provider: `{provider}`",
                f"- Error: {error}",
                "",
                "No experiment was executed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return str(json_path), str(markdown_path)


def _ollama_campaign_provider_result(
    config: CampaignConfig,
    state: CampaignState,
    *,
    cycle_dir: str | Path | None,
    base_url: str,
    model: str,
    timeout_seconds: float,
    http_post: Callable[[str, dict, float], dict] | None,
) -> CampaignProviderResult:
    if not model.strip():
        raise ValueError("model is required for ollama campaign provider")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    context = build_campaign_provider_context(config, state)
    prompt = build_campaign_provider_prompt(context)
    paths = _write_provider_prompt_artifacts(context, prompt, cycle_dir)
    post = http_post or _post_json
    payload = post(
        _chat_completions_url(base_url),
        _request_payload(prompt, model=model),
        timeout_seconds,
    )
    raw_response = _extract_message_content(payload)
    raw_response_path = _write_text_artifact(paths["raw_response_path"], raw_response)
    parsed_payload = json.loads(_strip_json_fence(raw_response))
    proposal = parse_campaign_proposal(parsed_payload)
    parsed_proposal_path = _write_json_artifact(paths["parsed_proposal_path"], proposal.to_dict())
    return CampaignProviderResult(
        provider=config.provider,
        proposal=proposal,
        raw_response=raw_response,
        context_path=paths["context_path"],
        prompt_path=paths["prompt_path"],
        raw_response_path=raw_response_path,
        parsed_proposal_path=parsed_proposal_path,
    )


def _request_payload(prompt: str, *, model: str) -> dict:
    return {
        "model": model,
        "temperature": 0.0,
        "response_format": CAMPAIGN_PROPOSAL_RESPONSE_FORMAT,
        "messages": [
            {
                "role": "system",
                "content": "You return strict JSON only. You are not allowed to edit files or run commands.",
            },
            {"role": "user", "content": prompt},
        ],
    }


def _write_provider_prompt_artifacts(context: dict, prompt: str, cycle_dir: str | Path | None) -> dict[str, str | None]:
    if cycle_dir is None:
        return {
            "context_path": None,
            "prompt_path": None,
            "raw_response_path": None,
            "parsed_proposal_path": None,
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
        "parsed_proposal_path": str(destination / CAMPAIGN_PROVIDER_PARSED_PROPOSAL_FILENAME),
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
