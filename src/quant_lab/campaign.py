"""Campaign config and state persistence.

Campaigns are deliberately a thin orchestration layer above existing research
commands. JSON is the source of truth; Markdown is only the human-readable view.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .research_plan_common import utc_now_iso, validate_required_text_fields, write_json_payload


CAMPAIGN_CONFIG_SCHEMA_VERSION = "campaign_config.v1"
CAMPAIGN_STATE_SCHEMA_VERSION = "campaign_state.v1"
CAMPAIGN_CONFIG_FILENAME = "campaign_config.json"
CAMPAIGN_STATE_FILENAME = "campaign_state.json"
CAMPAIGN_STATE_MARKDOWN_FILENAME = "campaign_state.md"
CAMPAIGN_STATUSES = {"running", "stopped", "complete", "blocked"}
CAMPAIGN_PROVIDERS = {"deterministic", "ollama", "codex"}


@dataclass(frozen=True)
class CampaignConfig:
    schema_version: str
    title: str
    objective: str
    allowed_symbols: list[str]
    allowed_templates: list[str]
    benchmark: str
    data_paths: dict[str, str]
    cost_preset: str
    max_cycles: int
    max_total_runs: int
    max_variants_per_experiment: int
    duration_minutes: int
    provider: str
    created_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CampaignState:
    schema_version: str
    status: Literal["running", "stopped", "complete", "blocked"]
    cycle_number: int
    elapsed_seconds: int
    runs_used: int
    completed_experiments: list[dict[str, Any]]
    current_findings: list[str]
    do_not_repeat: list[str]
    unresolved_questions: list[str]
    remaining_budget: dict[str, int]
    stop_reason: str | None
    created_at_utc: str
    updated_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CampaignPaths:
    output_dir: str
    config_path: str
    state_path: str
    state_markdown_path: str
    cycles_dir: str
    final_report_markdown_path: str
    final_report_json_path: str


def load_campaign_config(path: str | Path) -> CampaignConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("campaign config must be a JSON object")
    return parse_campaign_config(payload)


def parse_campaign_config(payload: dict[str, Any]) -> CampaignConfig:
    _reject_unknown_keys(
        payload,
        {
            "schema_version",
            "title",
            "objective",
            "allowed_symbols",
            "allowed_templates",
            "benchmark",
            "data_paths",
            "cost_preset",
            "max_cycles",
            "max_total_runs",
            "max_variants_per_experiment",
            "duration_minutes",
            "provider",
            "created_at_utc",
        },
        "campaign config",
    )
    schema_version = str(payload.get("schema_version", CAMPAIGN_CONFIG_SCHEMA_VERSION))
    if schema_version != CAMPAIGN_CONFIG_SCHEMA_VERSION:
        raise ValueError(f"unsupported campaign config schema_version: {schema_version}")
    config = CampaignConfig(
        schema_version=schema_version,
        title=_required_text(payload, "title", "campaign config"),
        objective=_required_text(payload, "objective", "campaign config"),
        allowed_symbols=_required_text_list(payload, "allowed_symbols", "campaign config"),
        allowed_templates=_required_text_list(payload, "allowed_templates", "campaign config"),
        benchmark=_required_text(payload, "benchmark", "campaign config"),
        data_paths=_required_data_paths(payload),
        cost_preset=_required_text(payload, "cost_preset", "campaign config"),
        max_cycles=_required_positive_int(payload, "max_cycles", "campaign config"),
        max_total_runs=_required_positive_int(payload, "max_total_runs", "campaign config"),
        max_variants_per_experiment=_required_positive_int(
            payload,
            "max_variants_per_experiment",
            "campaign config",
        ),
        duration_minutes=_required_positive_int(payload, "duration_minutes", "campaign config"),
        provider=_provider(payload),
        created_at_utc=str(payload.get("created_at_utc") or utc_now_iso()),
    )
    validate_campaign_config(config)
    return config


def validate_campaign_config(config: CampaignConfig) -> None:
    validate_required_text_fields(
        {
            "schema_version": config.schema_version,
            "title": config.title,
            "objective": config.objective,
            "benchmark": config.benchmark,
            "cost_preset": config.cost_preset,
            "provider": config.provider,
            "created_at_utc": config.created_at_utc,
        },
        context="campaign config",
    )
    if config.provider not in CAMPAIGN_PROVIDERS:
        raise ValueError(f"campaign config provider must be one of {sorted(CAMPAIGN_PROVIDERS)}")
    if not config.allowed_symbols:
        raise ValueError("campaign config allowed_symbols must not be empty")
    if not config.allowed_templates:
        raise ValueError("campaign config allowed_templates must not be empty")
    missing_data = [symbol for symbol in config.allowed_symbols if symbol not in config.data_paths]
    if missing_data:
        raise ValueError(f"campaign config data_paths missing allowed symbols: {missing_data}")


def initialize_campaign(config: CampaignConfig, output_dir: str | Path, *, overwrite: bool = False) -> CampaignPaths:
    validate_campaign_config(config)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    cycles_dir = destination / "cycles"
    cycles_dir.mkdir(exist_ok=True)
    config_path = destination / CAMPAIGN_CONFIG_FILENAME
    state_path = destination / CAMPAIGN_STATE_FILENAME
    state_markdown_path = destination / CAMPAIGN_STATE_MARKDOWN_FILENAME
    if not overwrite:
        for path in (config_path, state_path, state_markdown_path):
            if path.exists():
                raise FileExistsError(f"campaign artifact already exists: {path}")

    write_json_payload(config_path, config.to_dict())
    state = create_initial_campaign_state(config)
    save_campaign_state(state, destination, config=config)
    return campaign_paths(destination)


def create_initial_campaign_state(config: CampaignConfig) -> CampaignState:
    now = utc_now_iso()
    return CampaignState(
        schema_version=CAMPAIGN_STATE_SCHEMA_VERSION,
        status="running",
        cycle_number=0,
        elapsed_seconds=0,
        runs_used=0,
        completed_experiments=[],
        current_findings=[],
        do_not_repeat=[],
        unresolved_questions=[],
        remaining_budget={
            "cycles": config.max_cycles,
            "runs": config.max_total_runs,
            "seconds": config.duration_minutes * 60,
            "variants_per_experiment": config.max_variants_per_experiment,
        },
        stop_reason=None,
        created_at_utc=now,
        updated_at_utc=now,
    )


def load_campaign_state(path: str | Path) -> CampaignState:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("campaign state must be a JSON object")
    return parse_campaign_state(payload)


def parse_campaign_state(payload: dict[str, Any]) -> CampaignState:
    schema_version = str(payload.get("schema_version", ""))
    if schema_version != CAMPAIGN_STATE_SCHEMA_VERSION:
        raise ValueError(f"unsupported campaign state schema_version: {schema_version}")
    status = str(payload.get("status", ""))
    if status not in CAMPAIGN_STATUSES:
        raise ValueError(f"campaign state status must be one of {sorted(CAMPAIGN_STATUSES)}")
    return CampaignState(
        schema_version=schema_version,
        status=status,  # type: ignore[arg-type]
        cycle_number=int(payload.get("cycle_number", 0)),
        elapsed_seconds=int(payload.get("elapsed_seconds", 0)),
        runs_used=int(payload.get("runs_used", 0)),
        completed_experiments=list(payload.get("completed_experiments", [])),
        current_findings=[str(item) for item in payload.get("current_findings", [])],
        do_not_repeat=[str(item) for item in payload.get("do_not_repeat", [])],
        unresolved_questions=[str(item) for item in payload.get("unresolved_questions", [])],
        remaining_budget={str(key): int(value) for key, value in payload.get("remaining_budget", {}).items()},
        stop_reason=_optional_str(payload.get("stop_reason")),
        created_at_utc=str(payload.get("created_at_utc", "")),
        updated_at_utc=str(payload.get("updated_at_utc", "")),
    )


def save_campaign_state(
    state: CampaignState,
    output_dir: str | Path,
    *,
    config: CampaignConfig,
) -> tuple[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    state_path = destination / CAMPAIGN_STATE_FILENAME
    markdown_path = destination / CAMPAIGN_STATE_MARKDOWN_FILENAME
    write_json_payload(state_path, state.to_dict())
    markdown_path.write_text(format_campaign_state_markdown(config, state), encoding="utf-8")
    return str(state_path), str(markdown_path)


def campaign_paths(output_dir: str | Path) -> CampaignPaths:
    destination = Path(output_dir)
    return CampaignPaths(
        output_dir=str(destination),
        config_path=str(destination / CAMPAIGN_CONFIG_FILENAME),
        state_path=str(destination / CAMPAIGN_STATE_FILENAME),
        state_markdown_path=str(destination / CAMPAIGN_STATE_MARKDOWN_FILENAME),
        cycles_dir=str(destination / "cycles"),
        final_report_markdown_path=str(destination / "final_report.md"),
        final_report_json_path=str(destination / "final_report.json"),
    )


def format_campaign_state_markdown(config: CampaignConfig, state: CampaignState) -> str:
    return "\n".join(
        [
            f"# Campaign State: {config.title}",
            "",
            "Report role: campaign control state.",
            "",
            "## What Are We Trying To Learn?",
            "",
            config.objective,
            "",
            "## Status",
            "",
            f"- Status: `{state.status}`",
            f"- Cycle number: `{state.cycle_number}`",
            f"- Runs used: `{state.runs_used}`",
            f"- Elapsed seconds: `{state.elapsed_seconds}`",
            f"- Provider: `{config.provider}`",
            f"- Stop reason: {state.stop_reason or '-'}",
            "",
            "## Scope",
            "",
            f"- Allowed symbols: `{', '.join(config.allowed_symbols)}`",
            f"- Allowed templates: `{', '.join(config.allowed_templates)}`",
            f"- Benchmark: `{config.benchmark}`",
            f"- Cost preset: `{config.cost_preset}`",
            "",
            "## What Has Been Tested?",
            "",
            *_experiment_lines(state.completed_experiments),
            "",
            "## What Have We Learned?",
            "",
            *_bullet_lines(state.current_findings),
            "",
            "## Do Not Repeat",
            "",
            *_bullet_lines(state.do_not_repeat),
            "",
            "## What Remains Uncertain?",
            "",
            *_bullet_lines(state.unresolved_questions),
            "",
            "## What Budget Remains?",
            "",
            *[f"- {key}: `{value}`" for key, value in sorted(state.remaining_budget.items())],
            "",
        ]
    )


def format_campaign_status(config: CampaignConfig, state: CampaignState, paths: CampaignPaths) -> str:
    return "\n".join(
        [
            "Campaign Status",
            "===============",
            "",
            f"Title: {config.title}",
            f"Status: {state.status}",
            f"Cycle: {state.cycle_number}/{config.max_cycles}",
            f"Runs used: {state.runs_used}/{config.max_total_runs}",
            f"Provider: {config.provider}",
            f"Stop reason: {state.stop_reason or '-'}",
            f"Read first: {paths.state_markdown_path}",
        ]
    )


def _required_text(payload: dict[str, Any], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} {key} must be a non-empty string")
    return value.strip()


def _required_text_list(payload: dict[str, Any], key: str, context: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{context} {key} must be a list")
    normalized = [str(item).strip().upper() if key == "allowed_symbols" else str(item).strip() for item in value]
    normalized = [item for item in normalized if item]
    if not normalized:
        raise ValueError(f"{context} {key} must not be empty")
    return normalized


def _required_positive_int(payload: dict[str, Any], key: str, context: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{context} {key} must be a positive integer")
    return value


def _required_data_paths(payload: dict[str, Any]) -> dict[str, str]:
    value = payload.get("data_paths")
    if not isinstance(value, dict):
        raise ValueError("campaign config data_paths must be an object")
    return {str(symbol).strip().upper(): str(path).strip() for symbol, path in value.items() if str(path).strip()}


def _provider(payload: dict[str, Any]) -> str:
    provider = str(payload.get("provider", "deterministic")).strip().lower()
    if provider not in CAMPAIGN_PROVIDERS:
        raise ValueError(f"campaign config provider must be one of {sorted(CAMPAIGN_PROVIDERS)}")
    return provider


def _reject_unknown_keys(payload: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{context} contains unsupported fields: {unknown}")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- none"]


def _experiment_lines(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"- `{item.get('experiment_id', '-')}`: {item.get('title', '-')}" for item in items]
