"""Campaign provider context and prompt construction."""

from __future__ import annotations

import json
from pathlib import Path

from .campaign import CampaignConfig, CampaignState
from .campaign_proposal import ALLOWED_CAMPAIGN_ACTIONS, CAMPAIGN_PROPOSAL_SCHEMA_VERSION
from .campaign_templates import campaign_strategy_families_for_templates
from .opportunity_theses import OpportunityThesis, load_opportunity_catalog


CAMPAIGN_PROPOSAL_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "campaign_proposal",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
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
            ],
            "properties": {
                "schema_version": {"type": "string", "const": CAMPAIGN_PROPOSAL_SCHEMA_VERSION},
                "action": {"type": "string", "enum": sorted(ALLOWED_CAMPAIGN_ACTIONS)},
                "title": {"type": "string"},
                "hypothesis": {"type": "string"},
                "rationale": {"type": "string"},
                "difference_from_prior_work": {"type": "string"},
                "strategy_template": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "symbol": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "opportunity_thesis_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "parameters": {"type": "object"},
                "success_criteria": {"type": "object"},
                "validation_plan": {
                    "type": "object",
                    "additionalProperties": {"type": "boolean"},
                },
            },
        },
    },
}


def build_campaign_provider_context(
    config: CampaignConfig,
    state: CampaignState,
    *,
    opportunity_catalog_dir: str | Path | None = "data/opportunity_catalog",
    prior_attempt_feedback: list[str] | None = None,
) -> dict:
    """Build the exact context a model can see before proposing one cycle."""

    opportunity_theses = _campaign_opportunity_summaries(config, opportunity_catalog_dir)
    forbidden_proposals = _forbidden_proposal_summaries(state)
    context = {
        "schema_version": "campaign_provider_context.v1",
        "campaign": {
            "title": config.title,
            "objective": config.objective,
            "allowed_symbols": config.allowed_symbols,
            "allowed_templates": config.allowed_templates,
            "benchmark": config.benchmark,
            "data_paths": config.data_paths,
            "cost_preset": config.cost_preset,
        },
        "budgets": {
            "max_cycles": config.max_cycles,
            "max_total_runs": config.max_total_runs,
            "max_variants_per_experiment": config.max_variants_per_experiment,
            "duration_minutes": config.duration_minutes,
            "remaining": state.remaining_budget,
            "runs_used": state.runs_used,
            "cycle_number": state.cycle_number,
            "elapsed_seconds": state.elapsed_seconds,
        },
        "completed_experiments": state.completed_experiments,
        "current_findings": state.current_findings,
        "do_not_repeat": state.do_not_repeat,
        "forbidden_proposals": forbidden_proposals,
        "unresolved_questions": state.unresolved_questions,
        "opportunity_theses": opportunity_theses,
        "provider_rules": [
            "Return one campaign_proposal.v1 JSON object only.",
            "Do not include Markdown, prose, shell commands, or extra keys.",
            "Do not propose source-code changes or unsupported strategy features.",
            "Do not repeat branches listed in do_not_repeat.",
            "Do not repeat any title, template, thesis, or parameter set listed in forbidden_proposals.",
            "Use only allowed_symbols and allowed_templates.",
            "Prefer proposals with an opportunity_thesis_id from opportunity_theses when one fits.",
            "Prespecify success_criteria before seeing results.",
            "Prefer stop_campaign when no justified experiment remains.",
        ],
    }
    if prior_attempt_feedback:
        context["prior_attempt_feedback"] = prior_attempt_feedback
    return context


def build_campaign_provider_prompt(context: dict) -> str:
    allowed_actions = ", ".join(sorted(ALLOWED_CAMPAIGN_ACTIONS))
    forbidden = _forbidden_prompt_lines(context.get("forbidden_proposals"))
    prior_feedback = _prior_feedback_prompt_lines(context.get("prior_attempt_feedback"))
    return "\n".join(
        [
            "You are a bounded quant research campaign proposer.",
            "Read the campaign context and return exactly one JSON object.",
            "You are not allowed to edit files, run commands, modify strategy engines, or expand research scope.",
            "The controller will validate your proposal before anything executes.",
            "",
            "Most important constraints:",
            "- First check forbidden_proposals and do_not_repeat.",
            "- If your idea matches a forbidden title, template/parameter set, or unchanged rejected branch, do not propose it.",
            "- If no materially different supported experiment remains, return action stop_campaign.",
            *prior_feedback,
            *forbidden,
            "",
            "Required proposal schema:",
            "- schema_version: campaign_proposal.v1",
            f"- action: one of {allowed_actions}",
            "- title: concise experiment title",
            "- hypothesis: prespecified investment hypothesis",
            "- rationale: why this is the next justified test",
            "- difference_from_prior_work: why this is materially different from completed work",
            "- strategy_template: allowed template name, or null for non-run actions",
            "- symbol: allowed symbol, or null for non-run actions",
            "- opportunity_thesis_id: matching opportunity_theses id, or null when no thesis fits",
            "- parameters: object using only parameters supported by the chosen template",
            "- success_criteria: measurable thresholds set before execution",
            "- validation_plan: object of booleans such as cost_sensitivity, date_sensitivity, train_test",
            "",
            "Return a JSON object with exactly those keys. Do not copy a previous proposal from the context.",
            "",
            "Campaign context JSON:",
            json.dumps(context, indent=2, sort_keys=True),
            "",
            "Return the proposal now. Return JSON only.",
        ]
    )


def _campaign_opportunity_summaries(
    config: CampaignConfig,
    catalog_dir: str | Path | None,
) -> list[dict]:
    if catalog_dir is None:
        return []
    root = Path(catalog_dir)
    if not root.exists():
        return []

    theses = load_opportunity_catalog(root)
    allowed_families = campaign_strategy_families_for_templates(config.allowed_templates)
    return [
        _opportunity_summary(thesis)
        for thesis in theses
        if thesis.decision == "test_now"
        and thesis.engine_fit == "ready"
        and allowed_families.intersection(thesis.compatible_strategy_families)
    ]

def _opportunity_summary(thesis: OpportunityThesis) -> dict:
    payload = thesis.payload
    evidence = payload["institutional_constraint_evidence"]
    rubric = payload["rubric"]
    return {
        "thesis_id": thesis.thesis_id,
        "title": thesis.title,
        "market_niche": payload["market_niche"],
        "counterparty_or_forced_actor": payload["counterparty_or_forced_actor"],
        "why_edge_might_exist": payload["why_edge_might_exist"],
        "why_large_funds_might_ignore_it": payload["why_large_funds_might_ignore_it"],
        "evidence_quality": evidence["evidence_quality"],
        "edge_decay_trigger": payload["edge_decay_trigger"],
        "observable_prediction": payload["observable_prediction"],
        "falsification_tests": payload["falsification_tests"],
        "compatible_strategy_families": thesis.compatible_strategy_families,
        "rubric": rubric,
    }


def _forbidden_proposal_summaries(state: CampaignState) -> list[dict]:
    """Return compact anti-examples so local models see prior work as off-limits."""

    forbidden = []
    for item in state.completed_experiments:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        forbidden.append(
            {
                "title": title,
                "opportunity_thesis_id": item.get("opportunity_thesis_id"),
                "strategy_hypothesis_status": item.get("strategy_hypothesis_status"),
                "thesis_status": item.get("thesis_status"),
                "reason": "completed experiment; do not repeat unchanged",
            }
        )
    return forbidden


def _prior_feedback_prompt_lines(feedback: object) -> list[str]:
    if not isinstance(feedback, list) or not feedback:
        return []
    lines = ["", "Previous provider attempt was rejected. Fix these issues exactly:"]
    lines.extend(f"- {item}" for item in feedback if str(item).strip())
    return lines


def _forbidden_prompt_lines(forbidden: object) -> list[str]:
    if not isinstance(forbidden, list) or not forbidden:
        return []
    lines = ["", "Forbidden proposal titles from prior completed work:"]
    for item in forbidden:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if title:
            lines.append(f"- {title}")
    return lines
