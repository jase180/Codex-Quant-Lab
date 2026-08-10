"""Strict campaign proposal contract and deterministic validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .campaign import CampaignConfig, CampaignState
from .campaign_templates import campaign_template_strategy_family, supported_campaign_template_parameters
from .opportunity_theses import load_opportunity_catalog
from .research_plan_common import utc_now_iso, validate_required_text_fields, write_json_payload


CAMPAIGN_PROPOSAL_SCHEMA_VERSION = "campaign_proposal.v1"
CAMPAIGN_VALIDATION_SCHEMA_VERSION = "campaign_validation.v1"
PROPOSAL_JSON_FILENAME = "proposal.json"
VALIDATION_JSON_FILENAME = "proposal_validation.json"
VALIDATION_MARKDOWN_FILENAME = "proposal_validation.md"
ALLOWED_CAMPAIGN_ACTIONS = {"run_experiment", "request_human_review", "stop_campaign"}
@dataclass(frozen=True)
class CampaignProposal:
    schema_version: str
    action: Literal["run_experiment", "request_human_review", "stop_campaign"]
    title: str
    hypothesis: str
    rationale: str
    difference_from_prior_work: str
    strategy_template: str | None
    symbol: str | None
    opportunity_thesis_id: str | None
    parameters: dict[str, Any]
    success_criteria: dict[str, Any]
    validation_plan: dict[str, bool]
    created_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CampaignProposalValidation:
    schema_version: str
    proposal_action: str
    valid: bool
    reasons: list[str]
    projected_run_count: int
    created_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_campaign_proposal(payload: dict[str, Any]) -> CampaignProposal:
    if not isinstance(payload, dict):
        raise ValueError("campaign proposal must be a JSON object")
    _reject_unknown_keys(
        payload,
        {
            "schema_version",
            "action",
            "title",
            "hypothesis",
            "rationale",
            "difference_from_prior_work",
            "strategy_template",
            "symbol",
            "opportunity_thesis_id",
            "parameters",
            "success_criteria",
            "validation_plan",
            "created_at_utc",
        },
        "campaign proposal",
    )
    schema_version = str(payload.get("schema_version", ""))
    if schema_version != CAMPAIGN_PROPOSAL_SCHEMA_VERSION:
        raise ValueError(f"unsupported campaign proposal schema_version: {schema_version}")
    action = str(payload.get("action", ""))
    if action not in ALLOWED_CAMPAIGN_ACTIONS:
        raise ValueError(f"campaign proposal action must be one of {sorted(ALLOWED_CAMPAIGN_ACTIONS)}")
    proposal = CampaignProposal(
        schema_version=schema_version,
        action=action,  # type: ignore[arg-type]
        title=_required_text(payload, "title", "campaign proposal"),
        hypothesis=_required_text(payload, "hypothesis", "campaign proposal"),
        rationale=_required_text(payload, "rationale", "campaign proposal"),
        difference_from_prior_work=_required_text(payload, "difference_from_prior_work", "campaign proposal"),
        strategy_template=_optional_text(payload.get("strategy_template")),
        symbol=_optional_text(payload.get("symbol")),
        opportunity_thesis_id=_optional_text(payload.get("opportunity_thesis_id")),
        parameters=_mapping(payload.get("parameters"), "campaign proposal parameters"),
        success_criteria=_mapping(payload.get("success_criteria"), "campaign proposal success_criteria"),
        validation_plan={str(key): bool(value) for key, value in _mapping(payload.get("validation_plan"), "campaign proposal validation_plan").items()},
        created_at_utc=str(payload.get("created_at_utc") or utc_now_iso()),
    )
    validate_campaign_proposal_shape(proposal)
    return proposal


def validate_campaign_proposal_shape(proposal: CampaignProposal) -> None:
    validate_required_text_fields(
        {
            "schema_version": proposal.schema_version,
            "action": proposal.action,
            "title": proposal.title,
            "hypothesis": proposal.hypothesis,
            "rationale": proposal.rationale,
            "difference_from_prior_work": proposal.difference_from_prior_work,
            "created_at_utc": proposal.created_at_utc,
        },
        context="campaign proposal",
    )
    if proposal.action == "run_experiment":
        if not proposal.strategy_template:
            raise ValueError("campaign proposal strategy_template is required for run_experiment")
        if not proposal.symbol:
            raise ValueError("campaign proposal symbol is required for run_experiment")
        if not proposal.success_criteria:
            raise ValueError("campaign proposal success_criteria is required for run_experiment")


def deterministic_campaign_proposal(config: CampaignConfig, state: CampaignState) -> CampaignProposal:
    """Return one safe proposal from the campaign's allowed scope."""

    if state.remaining_budget.get("cycles", 0) <= 0 or state.remaining_budget.get("runs", 0) <= 0:
        return _stop_campaign_proposal("Campaign budget is exhausted.")

    symbol = config.allowed_symbols[0]
    if "sma-long-cash" in config.allowed_templates and not _has_completed_title(
        state,
        f"{symbol} SMA 200 long/cash campaign baseline",
    ):
        return _sma_long_cash_baseline_proposal(symbol)
    if "ema-trend-follow" in config.allowed_templates and not _has_completed_title(
        state,
        f"{symbol} EMA 50 RSI trend-follow campaign follow-up",
    ):
        return _ema_trend_follow_follow_up_proposal(symbol)
    return _stop_campaign_proposal("No remaining deterministic campaign proposal is materially different from prior work.")


def _sma_long_cash_baseline_proposal(symbol: str) -> CampaignProposal:
    return CampaignProposal(
        schema_version=CAMPAIGN_PROPOSAL_SCHEMA_VERSION,
        action="run_experiment",
        title=f"{symbol} SMA 200 long/cash campaign baseline",
        hypothesis=(
            f"A daily {symbol} 200-day SMA long/cash rule may reduce maximum drawdown "
            "while retaining most long-term growth after realistic costs."
        ),
        rationale="Start with the simplest allowed drawdown-control baseline before testing variants.",
        difference_from_prior_work="First campaign proposal; establishes the campaign baseline.",
        strategy_template="sma-long-cash",
        symbol=symbol,
        opportunity_thesis_id="liquid_etf_trend_defense",
        parameters={"sma_length": 200},
        success_criteria={
            "minimum_cagr_retention": 0.8,
            "minimum_relative_drawdown_reduction": 0.25,
        },
        validation_plan={
            "cost_sensitivity": True,
            "date_sensitivity": True,
            "train_test": True,
        },
    )


def _ema_trend_follow_follow_up_proposal(symbol: str) -> CampaignProposal:
    return CampaignProposal(
        schema_version=CAMPAIGN_PROPOSAL_SCHEMA_VERSION,
        action="run_experiment",
        title=f"{symbol} EMA 50 RSI trend-follow campaign follow-up",
        hypothesis=(
            f"A daily {symbol} EMA trend-follow rule with RSI confirmation may reduce drawdown "
            "while avoiding some SMA 200 whipsaw after realistic costs."
        ),
        rationale=(
            "The prior SMA 200 long/cash branch reduced drawdown too little and sacrificed too much CAGR; "
            "this follow-up tests a different existing trend template before adding any new strategy features."
        ),
        difference_from_prior_work="Uses EMA trend confirmation plus RSI momentum instead of a single SMA long/cash threshold.",
        strategy_template="ema-trend-follow",
        symbol=symbol,
        opportunity_thesis_id="liquid_etf_trend_defense",
        parameters={},
        success_criteria={
            "minimum_cagr_retention": 0.75,
            "minimum_relative_drawdown_reduction": 0.20,
        },
        validation_plan={
            "cost_sensitivity": True,
            "date_sensitivity": True,
            "train_test": True,
        },
    )


def _stop_campaign_proposal(rationale: str) -> CampaignProposal:
    return CampaignProposal(
        schema_version=CAMPAIGN_PROPOSAL_SCHEMA_VERSION,
        action="stop_campaign",
        title="Stop campaign",
        hypothesis="No further deterministic experiment should run.",
        rationale=rationale,
        difference_from_prior_work="No new experiment.",
        strategy_template=None,
        symbol=None,
        opportunity_thesis_id=None,
        parameters={},
        success_criteria={},
        validation_plan={},
    )


def validate_campaign_proposal(
    proposal: CampaignProposal,
    *,
    config: CampaignConfig,
    state: CampaignState,
    opportunity_catalog_dir: str | Path | None = "data/opportunity_catalog",
) -> CampaignProposalValidation:
    reasons: list[str] = []
    projected_runs = projected_run_count(proposal)

    if proposal.action not in ALLOWED_CAMPAIGN_ACTIONS:
        reasons.append(f"action is not permitted: {proposal.action}")
    if proposal.action == "run_experiment":
        _validate_run_experiment_proposal(
            proposal,
            config=config,
            state=state,
            reasons=reasons,
            projected_runs=projected_runs,
            opportunity_catalog_dir=opportunity_catalog_dir,
        )
    if proposal.action in {"request_human_review", "stop_campaign"} and projected_runs != 0:
        reasons.append("non-run actions must not consume runs")

    return CampaignProposalValidation(
        schema_version=CAMPAIGN_VALIDATION_SCHEMA_VERSION,
        proposal_action=proposal.action,
        valid=not reasons,
        reasons=reasons,
        projected_run_count=projected_runs,
    )


def projected_run_count(proposal: CampaignProposal) -> int:
    if proposal.action != "run_experiment":
        return 0
    variant_count = max(1, _parameter_variant_count(proposal.parameters))
    count = 1  # baseline
    count += variant_count  # sweep
    if proposal.validation_plan.get("train_test"):
        count += variant_count + 1
    if proposal.validation_plan.get("cost_sensitivity"):
        count += 3
    if proposal.validation_plan.get("date_sensitivity"):
        count += 2
    count += 2  # benchmark sensitivity: buy-and-hold and cash
    return count


def save_campaign_proposal_artifacts(
    proposal: CampaignProposal,
    validation: CampaignProposalValidation,
    cycle_dir: str | Path,
) -> tuple[str, str, str]:
    destination = Path(cycle_dir)
    destination.mkdir(parents=True, exist_ok=True)
    proposal_path = destination / PROPOSAL_JSON_FILENAME
    validation_path = destination / VALIDATION_JSON_FILENAME
    markdown_path = destination / VALIDATION_MARKDOWN_FILENAME
    write_json_payload(proposal_path, proposal.to_dict())
    write_json_payload(validation_path, validation.to_dict())
    markdown_path.write_text(format_campaign_validation_markdown(proposal, validation), encoding="utf-8")
    return str(proposal_path), str(validation_path), str(markdown_path)


def format_campaign_validation_markdown(
    proposal: CampaignProposal,
    validation: CampaignProposalValidation,
) -> str:
    return "\n".join(
        [
            f"# Campaign Proposal Validation: {proposal.title}",
            "",
            "Report role: campaign proposal gate.",
            "",
            "## Proposal",
            "",
            f"- Action: `{proposal.action}`",
            f"- Template: `{proposal.strategy_template or '-'}`",
            f"- Symbol: `{proposal.symbol or '-'}`",
            f"- Opportunity thesis: `{proposal.opportunity_thesis_id or '-'}`",
            f"- Projected run count: `{validation.projected_run_count}`",
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


def _validate_run_experiment_proposal(
    proposal: CampaignProposal,
    *,
    config: CampaignConfig,
    state: CampaignState,
    reasons: list[str],
    projected_runs: int,
    opportunity_catalog_dir: str | Path | None,
) -> None:
    if proposal.strategy_template not in config.allowed_templates:
        reasons.append(f"template is not allowed: {proposal.strategy_template}")
    if proposal.symbol not in config.allowed_symbols:
        reasons.append(f"symbol is not allowed: {proposal.symbol}")
    if proposal.symbol and proposal.symbol not in config.data_paths:
        reasons.append(f"required data path is missing for symbol: {proposal.symbol}")
    elif proposal.symbol and not Path(config.data_paths[proposal.symbol]).exists():
        reasons.append(f"required data file does not exist: {config.data_paths[proposal.symbol]}")
    supported_params = supported_campaign_template_parameters(str(proposal.strategy_template))
    unsupported_params = sorted(set(proposal.parameters) - supported_params)
    if unsupported_params:
        reasons.append(f"unsupported parameters for template {proposal.strategy_template}: {unsupported_params}")
    variant_count = _parameter_variant_count(proposal.parameters)
    if variant_count > state.remaining_budget.get("variants_per_experiment", 0):
        reasons.append("proposal variants exceed remaining variants-per-experiment budget")
    if projected_runs > state.remaining_budget.get("runs", 0):
        reasons.append("projected run count exceeds remaining run budget")
    if state.remaining_budget.get("cycles", 0) <= 0:
        reasons.append("no campaign cycles remain")
    if not proposal.success_criteria:
        reasons.append("success criteria are required before execution")
    if _violates_do_not_repeat(proposal, state):
        reasons.append("proposal appears to violate do_not_repeat campaign memory")
    _validate_opportunity_thesis_reference(
        proposal,
        reasons=reasons,
        opportunity_catalog_dir=opportunity_catalog_dir,
    )


def _has_completed_title(state: CampaignState, title: str) -> bool:
    return any(str(item.get("title") or "") == title for item in state.completed_experiments)


def _parameter_variant_count(parameters: dict[str, Any]) -> int:
    count = 1
    for value in parameters.values():
        if isinstance(value, list):
            count *= max(1, len(value))
    return count


def _violates_do_not_repeat(proposal: CampaignProposal, state: CampaignState) -> bool:
    corpus = " ".join(state.do_not_repeat).lower()
    if not corpus:
        return False
    terms = [
        proposal.title,
        proposal.hypothesis,
        proposal.strategy_template or "",
        *[str(key) for key in proposal.parameters],
        *[str(value) for value in proposal.parameters.values()],
    ]
    return any(str(term).strip().lower() and str(term).strip().lower() in corpus for term in terms)


def _validate_opportunity_thesis_reference(
    proposal: CampaignProposal,
    *,
    reasons: list[str],
    opportunity_catalog_dir: str | Path | None,
) -> None:
    if not proposal.opportunity_thesis_id:
        return
    if opportunity_catalog_dir is None:
        reasons.append("opportunity_thesis_id was provided but opportunity catalog validation is disabled")
        return

    root = Path(opportunity_catalog_dir)
    if not root.exists():
        reasons.append(f"opportunity_thesis_id was provided but opportunity catalog does not exist: {root}")
        return

    theses = {thesis.thesis_id: thesis for thesis in load_opportunity_catalog(root)}
    thesis = theses.get(proposal.opportunity_thesis_id)
    if thesis is None:
        reasons.append(f"opportunity_thesis_id is not in the opportunity catalog: {proposal.opportunity_thesis_id}")
        return
    if thesis.decision != "test_now":
        reasons.append(f"opportunity thesis is not marked test_now: {proposal.opportunity_thesis_id}")
    if thesis.engine_fit != "ready":
        reasons.append(f"opportunity thesis engine_fit is not ready: {proposal.opportunity_thesis_id}")

    strategy_family = campaign_template_strategy_family(str(proposal.strategy_template))
    if strategy_family is None:
        reasons.append(f"no strategy-family mapping exists for template: {proposal.strategy_template}")
        return
    if strategy_family not in thesis.compatible_strategy_families:
        reasons.append(
            "opportunity thesis is not compatible with template "
            f"{proposal.strategy_template}: {proposal.opportunity_thesis_id}"
        )


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


def _mapping(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return dict(value)


def _reject_unknown_keys(payload: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{context} contains unsupported fields: {unknown}")


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- none"]
