"""Strict provider choice contract for campaign candidate menus."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .campaign_candidates import CampaignCandidateMenu, find_campaign_candidate
from .research_plan_common import utc_now_iso, write_json_payload


CAMPAIGN_CANDIDATE_CHOICE_SCHEMA_VERSION = "campaign_candidate_choice.v1"
CAMPAIGN_CANDIDATE_CHOICE_VALIDATION_SCHEMA_VERSION = "campaign_candidate_choice_validation.v1"
CHOICE_JSON_FILENAME = "candidate_choice.json"
CHOICE_VALIDATION_JSON_FILENAME = "candidate_choice_validation.json"
CHOICE_VALIDATION_MARKDOWN_FILENAME = "candidate_choice_validation.md"
ALLOWED_CHOICE_ACTIONS = {"choose_candidate", "request_human_review", "stop_campaign"}


@dataclass(frozen=True)
class CampaignCandidateChoice:
    schema_version: str
    action: Literal["choose_candidate", "request_human_review", "stop_campaign"]
    candidate_id: str | None
    rationale: str
    created_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CampaignCandidateChoiceValidation:
    schema_version: str
    choice_action: str
    valid: bool
    reasons: list[str]
    selected_candidate_id: str | None
    created_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_campaign_candidate_choice(payload: dict[str, Any]) -> CampaignCandidateChoice:
    if not isinstance(payload, dict):
        raise ValueError("campaign candidate choice must be a JSON object")
    _reject_unknown_keys(
        payload,
        {"schema_version", "action", "candidate_id", "rationale", "created_at_utc"},
        "campaign candidate choice",
    )
    schema_version = str(payload.get("schema_version", ""))
    if schema_version != CAMPAIGN_CANDIDATE_CHOICE_SCHEMA_VERSION:
        raise ValueError(f"unsupported campaign candidate choice schema_version: {schema_version}")
    action = str(payload.get("action", ""))
    if action not in ALLOWED_CHOICE_ACTIONS:
        raise ValueError(f"campaign candidate choice action must be one of {sorted(ALLOWED_CHOICE_ACTIONS)}")
    choice = CampaignCandidateChoice(
        schema_version=schema_version,
        action=action,  # type: ignore[arg-type]
        candidate_id=_optional_text(payload.get("candidate_id")),
        rationale=_required_text(payload, "rationale", "campaign candidate choice"),
        created_at_utc=str(payload.get("created_at_utc") or utc_now_iso()),
    )
    return choice


def validate_campaign_candidate_choice(
    choice: CampaignCandidateChoice,
    *,
    menu: CampaignCandidateMenu,
) -> CampaignCandidateChoiceValidation:
    reasons: list[str] = []
    selected_candidate_id = choice.candidate_id if choice.action == "choose_candidate" else None
    if choice.action == "choose_candidate":
        if not choice.candidate_id:
            reasons.append("choose_candidate requires candidate_id")
        elif find_campaign_candidate(menu, choice.candidate_id) is None:
            reasons.append(f"candidate_id is not in candidate menu: {choice.candidate_id}")
        if menu.status != "ready":
            reasons.append(f"candidate menu is not ready: {menu.status}")
    else:
        if choice.candidate_id is not None:
            reasons.append("non-choice actions must set candidate_id to null")
    return CampaignCandidateChoiceValidation(
        schema_version=CAMPAIGN_CANDIDATE_CHOICE_VALIDATION_SCHEMA_VERSION,
        choice_action=choice.action,
        valid=not reasons,
        reasons=reasons,
        selected_candidate_id=selected_candidate_id,
    )


def save_campaign_candidate_choice_artifacts(
    choice: CampaignCandidateChoice,
    validation: CampaignCandidateChoiceValidation,
    output_dir: str | Path,
) -> tuple[str, str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    choice_path = destination / CHOICE_JSON_FILENAME
    validation_path = destination / CHOICE_VALIDATION_JSON_FILENAME
    markdown_path = destination / CHOICE_VALIDATION_MARKDOWN_FILENAME
    write_json_payload(choice_path, choice.to_dict())
    write_json_payload(validation_path, validation.to_dict())
    markdown_path.write_text(format_campaign_candidate_choice_validation_markdown(choice, validation), encoding="utf-8")
    return str(choice_path), str(validation_path), str(markdown_path)


def format_campaign_candidate_choice_validation_markdown(
    choice: CampaignCandidateChoice,
    validation: CampaignCandidateChoiceValidation,
) -> str:
    return "\n".join(
        [
            "# Campaign Candidate Choice Validation",
            "",
            "Report role: provider candidate-choice gate.",
            "",
            "## Choice",
            "",
            f"- Action: `{choice.action}`",
            f"- Candidate ID: `{choice.candidate_id or '-'}`",
            f"- Rationale: {choice.rationale}",
            "",
            "## Validation",
            "",
            f"- Valid: `{validation.valid}`",
            "",
            "## Reasons",
            "",
            *_bullet_lines(validation.reasons),
            "",
        ]
    )


def deterministic_candidate_choice(menu: CampaignCandidateMenu) -> CampaignCandidateChoice:
    if menu.candidates:
        candidate = sorted(
            menu.candidates,
            key=lambda item: (
                _rank_baseline_preference(item.title),
                _rank_information_gain(item.expected_information_gain),
                _rank_mining_risk(item.parameter_mining_risk),
                item.candidate_id,
            ),
        )[0]
        return CampaignCandidateChoice(
            schema_version=CAMPAIGN_CANDIDATE_CHOICE_SCHEMA_VERSION,
            action="choose_candidate",
            candidate_id=candidate.candidate_id,
            rationale="Selected the highest-ranked deterministic candidate from the bounded menu.",
        )
    return CampaignCandidateChoice(
        schema_version=CAMPAIGN_CANDIDATE_CHOICE_SCHEMA_VERSION,
        action="stop_campaign",
        candidate_id=None,
        rationale="SEARCH_SPACE_EXHAUSTED: no valid candidate remains in the bounded menu.",
    )


def _rank_baseline_preference(title: str) -> int:
    # Prefer the canonical baseline when a fresh campaign has several valid variants.
    # Later cycles still rely on completed-title and do_not_repeat filtering to move on.
    return 0 if "baseline" in title.lower() else 1


def _rank_information_gain(value: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(value, 3)


def _rank_mining_risk(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(value, 3)


def _required_text(payload: dict[str, Any], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} {key} must be a non-empty string")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _reject_unknown_keys(payload: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{context} contains unsupported fields: {unknown}")


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- none"]
