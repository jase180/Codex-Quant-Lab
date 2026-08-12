"""Deterministic campaign candidate-menu generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any

from .campaign import CampaignConfig, CampaignState
from .campaign_proposal import projected_run_count
from .campaign_proposal import CampaignProposal
from .experiment_templates import (
    ExperimentTemplate,
    ParameterNeighborhood,
    find_parameter_neighborhood,
    load_experiment_template_catalog,
    load_parameter_neighborhood_catalog,
)
from .opportunity_theses import OpportunityThesis, load_opportunity_catalog
from .research_plan_common import utc_now_iso, write_json_payload


CAMPAIGN_CANDIDATE_SCHEMA_VERSION = "campaign_candidate.v1"
CAMPAIGN_CANDIDATE_MENU_SCHEMA_VERSION = "campaign_candidate_menu.v1"
CANDIDATE_MENU_JSON_FILENAME = "candidate_menu.json"
CANDIDATE_MENU_MARKDOWN_FILENAME = "candidate_menu.md"


@dataclass(frozen=True)
class CampaignCandidate:
    schema_version: str
    candidate_id: str
    title: str
    opportunity_thesis_id: str
    template_id: str
    strategy_template: str
    symbol: str
    parameters: dict[str, Any]
    hypothesis: str
    tests_claim: str
    distinguishes_from_prior: list[str]
    novelty_reason: str
    prior_overlap: str
    expected_information_gain: str
    parameter_mining_risk: str
    engine_support_status: str
    success_criteria: dict[str, float]
    validation_plan: dict[str, bool]
    projected_run_count: int
    created_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateRejection:
    template_id: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class CampaignCandidateMenu:
    schema_version: str
    campaign_title: str
    cycle_number: int
    status: str
    candidates: list[CampaignCandidate]
    total_candidates_before_shortlist: int
    shortlist_policy: str
    rejected_candidates: list[CandidateRejection]
    forbidden_titles: list[str]
    do_not_repeat: list[str]
    created_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "campaign_title": self.campaign_title,
            "cycle_number": self.cycle_number,
            "status": self.status,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "total_candidates_before_shortlist": self.total_candidates_before_shortlist,
            "shortlist_policy": self.shortlist_policy,
            "rejected_candidates": [rejection.to_dict() for rejection in self.rejected_candidates],
            "forbidden_titles": list(self.forbidden_titles),
            "do_not_repeat": list(self.do_not_repeat),
            "created_at_utc": self.created_at_utc,
        }


def campaign_candidate_to_proposal(candidate: CampaignCandidate) -> CampaignProposal:
    """Convert a validated candidate into the existing campaign proposal shape."""

    return CampaignProposal(
        schema_version="campaign_proposal.v1",
        action="run_experiment",
        title=candidate.title,
        hypothesis=candidate.hypothesis,
        rationale=candidate.novelty_reason,
        difference_from_prior_work="Selected from deterministic campaign candidate menu.",
        strategy_template=candidate.strategy_template,
        symbol=candidate.symbol,
        opportunity_thesis_id=candidate.opportunity_thesis_id,
        parameters=dict(candidate.parameters),
        success_criteria=dict(candidate.success_criteria),
        validation_plan=dict(candidate.validation_plan),
    )


def find_campaign_candidate(menu: CampaignCandidateMenu, candidate_id: str) -> CampaignCandidate | None:
    for candidate in menu.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    return None


def build_campaign_candidate_menu(
    config: CampaignConfig,
    state: CampaignState,
    *,
    opportunity_catalog_dir: str | Path = "data/opportunity_catalog",
    experiment_template_catalog_dir: str | Path = "data/experiment_template_catalog",
    parameter_neighborhoods_dir: str | Path = "data/parameter_neighborhoods",
) -> CampaignCandidateMenu:
    """Build a deterministic menu of valid next experiment candidates."""

    opportunities = load_opportunity_catalog(opportunity_catalog_dir)
    templates = load_experiment_template_catalog(experiment_template_catalog_dir)
    neighborhoods = load_parameter_neighborhood_catalog(parameter_neighborhoods_dir)
    forbidden_titles = _forbidden_titles(state)
    rejected: list[CandidateRejection] = []
    candidates: list[CampaignCandidate] = []

    for template in templates:
        rejection = _template_rejection(template, config=config, neighborhoods=neighborhoods)
        if rejection is not None:
            rejected.append(rejection)
            continue
        neighborhood = find_parameter_neighborhood(neighborhoods, template.parameter_neighborhood_id)
        if neighborhood is None:
            rejected.append(CandidateRejection(template.template_id, "parameter neighborhood not found"))
            continue
        compatible_opportunities = _compatible_opportunities(template, opportunities)
        if not compatible_opportunities:
            rejected.append(CandidateRejection(template.template_id, "no compatible ready opportunity thesis"))
            continue
        for symbol in config.allowed_symbols:
            if symbol not in config.data_paths or not Path(config.data_paths[symbol]).exists():
                rejected.append(CandidateRejection(template.template_id, f"required data file is missing for {symbol}"))
                continue
            for opportunity in compatible_opportunities:
                for index, parameters in enumerate(_campaign_parameter_variants(template, neighborhood), start=1):
                    candidate = _candidate(
                        config=config,
                        state=state,
                        template=template,
                        opportunity=opportunity,
                        symbol=symbol,
                        parameters=parameters,
                        variant_index=index,
                    )
                    if candidate.title in forbidden_titles:
                        rejected.append(CandidateRejection(template.template_id, f"forbidden completed title: {candidate.title}"))
                        continue
                    if _violates_do_not_repeat(candidate, state):
                        rejected.append(CandidateRejection(template.template_id, f"violates do_not_repeat: {candidate.title}"))
                        continue
                    if candidate.projected_run_count > state.remaining_budget.get("runs", 0):
                        rejected.append(CandidateRejection(template.template_id, f"run budget too small: {candidate.title}"))
                        continue
                    candidates.append(candidate)

    total_candidates_before_shortlist = len(candidates)
    candidates = _shortlisted_candidates(candidates, config=config)
    status = "ready" if candidates else "SEARCH_SPACE_EXHAUSTED"
    return CampaignCandidateMenu(
        schema_version=CAMPAIGN_CANDIDATE_MENU_SCHEMA_VERSION,
        campaign_title=config.title,
        cycle_number=state.cycle_number + 1,
        status=status,
        candidates=candidates,
        total_candidates_before_shortlist=total_candidates_before_shortlist,
        shortlist_policy=_shortlist_policy(config),
        rejected_candidates=rejected,
        forbidden_titles=forbidden_titles,
        do_not_repeat=list(state.do_not_repeat),
        created_at_utc=utc_now_iso(),
    )


def save_campaign_candidate_menu(menu: CampaignCandidateMenu, cycle_dir: str | Path) -> tuple[str, str]:
    destination = Path(cycle_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / CANDIDATE_MENU_JSON_FILENAME
    markdown_path = destination / CANDIDATE_MENU_MARKDOWN_FILENAME
    write_json_payload(json_path, menu.to_dict())
    markdown_path.write_text(format_campaign_candidate_menu_markdown(menu), encoding="utf-8")
    return str(json_path), str(markdown_path)


def format_campaign_candidate_menu_markdown(menu: CampaignCandidateMenu) -> str:
    return "\n".join(
        [
            f"# Campaign Candidate Menu: {menu.campaign_title}",
            "",
            "Report role: bounded next-experiment candidate menu.",
            "",
            "## Status",
            "",
            f"- Status: `{menu.status}`",
            f"- Cycle: `{menu.cycle_number}`",
            f"- Candidates: `{len(menu.candidates)}`",
            f"- Total valid before shortlist: `{menu.total_candidates_before_shortlist}`",
            f"- Shortlist policy: {menu.shortlist_policy}",
            f"- Rejected candidates: `{len(menu.rejected_candidates)}`",
            "",
            "## Candidate Menu",
            "",
            *_candidate_lines(menu.candidates),
            "",
            "## Forbidden Titles",
            "",
            *_bullet_lines(menu.forbidden_titles),
            "",
            "## Do Not Repeat",
            "",
            *_bullet_lines(menu.do_not_repeat),
            "",
            "## Rejected Candidate Reasons",
            "",
            *_rejection_lines(menu.rejected_candidates),
            "",
        ]
    )


def _template_rejection(
    template: ExperimentTemplate,
    *,
    config: CampaignConfig,
    neighborhoods: list[ParameterNeighborhood],
) -> CandidateRejection | None:
    if template.engine_support_status != "ready":
        return CandidateRejection(template.template_id, "template engine support is not ready")
    if template.campaign_strategy_template not in config.allowed_templates:
        return CandidateRejection(template.template_id, "campaign strategy template is not allowed")
    if find_parameter_neighborhood(neighborhoods, template.parameter_neighborhood_id) is None:
        return CandidateRejection(template.template_id, "parameter neighborhood not found")
    return None


def _compatible_opportunities(
    template: ExperimentTemplate,
    opportunities: list[OpportunityThesis],
) -> list[OpportunityThesis]:
    return [
        opportunity
        for opportunity in opportunities
        if opportunity.decision == "test_now"
        and opportunity.engine_fit == "ready"
        and template.strategy_family in opportunity.compatible_strategy_families
    ]


def _campaign_parameter_variants(
    template: ExperimentTemplate,
    neighborhood: ParameterNeighborhood,
) -> list[dict[str, Any]]:
    mapping = template.payload["executable_mapping"]["parameter_map"]
    if not mapping:
        return [{}]
    names = list(mapping)
    values = [neighborhood.parameters[name] for name in names if name in neighborhood.parameters]
    variants: list[dict[str, Any]] = []
    for combo in product(*values):
        campaign_parameters = {str(mapping[name]): value for name, value in zip(names, combo)}
        variants.append(campaign_parameters)
    return variants[: neighborhood.max_variants]


def _candidate(
    *,
    config: CampaignConfig,
    state: CampaignState,
    template: ExperimentTemplate,
    opportunity: OpportunityThesis,
    symbol: str,
    parameters: dict[str, Any],
    variant_index: int,
) -> CampaignCandidate:
    title = _candidate_title(symbol=symbol, template=template, parameters=parameters)
    proposal = CampaignProposal(
        schema_version="campaign_proposal.v1",
        action="run_experiment",
        title=title,
        hypothesis=_hypothesis(symbol=symbol, template=template, opportunity=opportunity, parameters=parameters),
        rationale=str(template.payload["rationale"]),
        difference_from_prior_work=_difference_from_prior_work(template, parameters, state),
        strategy_template=template.campaign_strategy_template,
        symbol=symbol,
        opportunity_thesis_id=opportunity.thesis_id,
        parameters=parameters,
        success_criteria=dict(template.payload["default_success_criteria"]),
        validation_plan=dict(template.payload["default_validation_plan"]),
    )
    return CampaignCandidate(
        schema_version=CAMPAIGN_CANDIDATE_SCHEMA_VERSION,
        candidate_id=_candidate_id(template.template_id, symbol, variant_index),
        title=title,
        opportunity_thesis_id=opportunity.thesis_id,
        template_id=template.template_id,
        strategy_template=template.campaign_strategy_template,
        symbol=symbol,
        parameters=parameters,
        hypothesis=proposal.hypothesis,
        tests_claim=str(template.payload["tests_claim"]),
        distinguishes_from_prior=_distinguishes_from_prior(template, state),
        novelty_reason=_novelty_reason(template, parameters),
        prior_overlap=_prior_overlap(title, template, state),
        expected_information_gain=str(template.payload["expected_information_gain"]),
        parameter_mining_risk=str(template.payload["parameter_mining_risk"]),
        engine_support_status=template.engine_support_status,
        success_criteria=proposal.success_criteria,
        validation_plan=proposal.validation_plan,
        projected_run_count=projected_run_count(proposal),
        created_at_utc=proposal.created_at_utc,
    )


def _candidate_title(*, symbol: str, template: ExperimentTemplate, parameters: dict[str, Any]) -> str:
    if template.template_id == "price_vs_sma_trend":
        length = parameters.get("sma_length", "unknown")
        if length == 200:
            return f"{symbol} SMA 200 long/cash campaign baseline"
        return f"{symbol} SMA {length} long/cash candidate"
    if template.template_id == "ema_rsi_trend_confirmation":
        return f"{symbol} EMA 50 RSI trend-follow campaign follow-up"
    return f"{symbol} {template.payload['title']}"


def _hypothesis(
    *,
    symbol: str,
    template: ExperimentTemplate,
    opportunity: OpportunityThesis,
    parameters: dict[str, Any],
) -> str:
    if template.template_id == "price_vs_sma_trend":
        length = parameters.get("sma_length", "unknown")
        return (
            f"A daily {symbol} {length}-day SMA long/cash rule may clarify whether "
            f"{opportunity.title} depends on slow trend-state timing."
        )
    return f"{template.payload['tests_claim']} Applied to {symbol} under the {opportunity.title} thesis."


def _difference_from_prior_work(
    template: ExperimentTemplate,
    parameters: dict[str, Any],
    state: CampaignState,
) -> str:
    if not state.completed_experiments:
        return "First candidate for this campaign."
    if template.template_id == "price_vs_sma_trend":
        return "Changes the prespecified SMA lookback while keeping the same trend-state template."
    return "Uses a distinct campaign-safe experiment template from prior candidates."


def _distinguishes_from_prior(template: ExperimentTemplate, state: CampaignState) -> list[str]:
    if not state.completed_experiments:
        return ["Establishes the first bounded experiment for this campaign."]
    if template.template_id == "price_vs_sma_trend":
        return [
            "Tests whether the prior trend-defense result was sensitive to the selected lookback.",
            "Does not introduce a new indicator or execution assumption.",
        ]
    if template.template_id == "ema_rsi_trend_confirmation":
        return [
            "Tests whether confirmation logic changes participation versus single-average trend state.",
            "Keeps the campaign inside existing executable templates.",
        ]
    return ["Tests a different cataloged experiment template."]


def _novelty_reason(template: ExperimentTemplate, parameters: dict[str, Any]) -> str:
    if template.template_id == "price_vs_sma_trend":
        return f"Uses prespecified catalog lookback parameters: {parameters}."
    return "Uses a separate cataloged template rather than freeform model invention."


def _prior_overlap(title: str, template: ExperimentTemplate, state: CampaignState) -> str:
    if title in _forbidden_titles(state):
        return "high"
    completed_titles = " ".join(str(item.get("title", "")) for item in state.completed_experiments).lower()
    if template.campaign_strategy_template.replace("-", " ") in completed_titles:
        return "medium"
    return "low" if state.completed_experiments else "none"


def _forbidden_titles(state: CampaignState) -> list[str]:
    return [str(item.get("title")).strip() for item in state.completed_experiments if str(item.get("title", "")).strip()]


def _violates_do_not_repeat(candidate: CampaignCandidate, state: CampaignState) -> bool:
    corpus = " ".join(state.do_not_repeat).lower()
    if not corpus:
        return False
    if _violates_weakened_branch_rule(candidate, corpus):
        return True
    if "do not keep widening this branch" in corpus and _same_completed_branch(candidate, state):
        return True
    terms = [
        candidate.title,
        candidate.strategy_template,
        *[str(key) for key in candidate.parameters],
        *[str(value) for value in candidate.parameters.values()],
    ]
    return any(term.strip().lower() and term.strip().lower() in corpus for term in terms)


def _violates_weakened_branch_rule(candidate: CampaignCandidate, corpus: str) -> bool:
    rule = (
        "do not repeat weakened branch: "
        f"opportunity={candidate.opportunity_thesis_id.lower()}; "
        f"template={candidate.strategy_template.lower()}."
    )
    return rule in corpus


def _same_completed_branch(candidate: CampaignCandidate, state: CampaignState) -> bool:
    completed_titles = " ".join(str(item.get("title", "")) for item in state.completed_experiments).lower()
    if candidate.strategy_template == "sma-long-cash" and "sma" in completed_titles:
        return True
    if candidate.strategy_template == "ema-trend-follow" and "ema" in completed_titles:
        return True
    return False


def _candidate_id(template_id: str, symbol: str, variant_index: int) -> str:
    return f"{symbol.lower()}_{template_id}_{variant_index:03d}"


def _shortlisted_candidates(candidates: list[CampaignCandidate], *, config: CampaignConfig) -> list[CampaignCandidate]:
    limit = config.max_candidate_menu_size
    if limit is None or len(candidates) <= limit:
        return sorted(candidates, key=_candidate_quality_key)

    selected: list[CampaignCandidate] = []
    remaining = list(candidates)
    symbol_counts: dict[str, int] = {}
    template_counts: dict[str, int] = {}
    thesis_counts: dict[str, int] = {}
    while remaining and len(selected) < limit:
        candidate = min(
            remaining,
            key=lambda item: (
                _candidate_quality_score(item)
                + (symbol_counts.get(item.symbol, 0) * 4)
                + (template_counts.get(item.template_id, 0) * 2)
                + (thesis_counts.get(item.opportunity_thesis_id, 0) * 2),
                _candidate_quality_key(item),
            ),
        )
        selected.append(candidate)
        remaining.remove(candidate)
        symbol_counts[candidate.symbol] = symbol_counts.get(candidate.symbol, 0) + 1
        template_counts[candidate.template_id] = template_counts.get(candidate.template_id, 0) + 1
        thesis_counts[candidate.opportunity_thesis_id] = thesis_counts.get(candidate.opportunity_thesis_id, 0) + 1
    return selected


def _shortlist_policy(config: CampaignConfig) -> str:
    limit = config.max_candidate_menu_size
    if limit is None:
        return "uncapped: all valid candidates are shown"
    return (
        f"capped at {limit}: greedy ranking by information gain, low mining risk, low prior overlap, "
        "and diversity across symbols, templates, and opportunity theses"
    )


def _candidate_quality_score(candidate: CampaignCandidate) -> int:
    return (
        _rank_information_gain(candidate.expected_information_gain) * 4
        + _rank_mining_risk(candidate.parameter_mining_risk) * 2
        + _rank_prior_overlap(candidate.prior_overlap) * 2
        + _baseline_penalty(candidate.title)
    )


def _candidate_quality_key(candidate: CampaignCandidate) -> tuple[int, int, int, int, str]:
    return (
        _rank_information_gain(candidate.expected_information_gain),
        _rank_mining_risk(candidate.parameter_mining_risk),
        _rank_prior_overlap(candidate.prior_overlap),
        _baseline_penalty(candidate.title),
        candidate.candidate_id,
    )


def _rank_information_gain(value: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(value, 3)


def _rank_mining_risk(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(value, 3)


def _rank_prior_overlap(value: str) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3}.get(value, 4)


def _baseline_penalty(title: str) -> int:
    return 0 if "baseline" in title.lower() else 1


def _candidate_lines(candidates: list[CampaignCandidate]) -> list[str]:
    if not candidates:
        return ["- none"]
    lines: list[str] = []
    for candidate in candidates:
        lines.extend(
            [
                f"- `{candidate.candidate_id}`: {candidate.title}",
                f"  - Thesis: `{candidate.opportunity_thesis_id}`",
                f"  - Template: `{candidate.strategy_template}`",
                f"  - Parameters: `{candidate.parameters}`",
                f"  - Information gain: `{candidate.expected_information_gain}`",
                f"  - Mining risk: `{candidate.parameter_mining_risk}`",
                f"  - Prior overlap: `{candidate.prior_overlap}`",
                f"  - Projected runs: `{candidate.projected_run_count}`",
            ]
        )
    return lines


def _rejection_lines(rejections: list[CandidateRejection]) -> list[str]:
    if not rejections:
        return ["- none"]
    return [f"- `{item.template_id}`: {item.reason}" for item in rejections]


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- none"]
