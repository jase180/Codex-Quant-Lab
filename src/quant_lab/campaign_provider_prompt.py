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
        "unresolved_questions": state.unresolved_questions,
        "opportunity_theses": opportunity_theses,
        "provider_rules": [
            "Return one campaign_proposal.v1 JSON object only.",
            "Do not include Markdown, prose, shell commands, or extra keys.",
            "Do not propose source-code changes or unsupported strategy features.",
            "Do not repeat branches listed in do_not_repeat.",
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
    return "\n".join(
        [
            "You are a bounded quant research campaign proposer.",
            "Read the campaign context and return exactly one JSON object.",
            "You are not allowed to edit files, run commands, modify strategy engines, or expand research scope.",
            "The controller will validate your proposal before anything executes.",
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
            "Use this exact JSON shape:",
            "{",
            '  "schema_version": "campaign_proposal.v1",',
            '  "action": "run_experiment",',
            '  "title": "SPY SMA 200 long/cash campaign baseline",',
            '  "hypothesis": "A daily SPY 200-day SMA long/cash rule may reduce maximum drawdown while retaining most long-term growth after realistic costs.",',
            '  "rationale": "Start with the simplest allowed trend-defense rule tied to the liquid ETF trend-defense opportunity thesis.",',
            '  "difference_from_prior_work": "This is the first campaign baseline, so it establishes the initial reference result before any variants.",',
            '  "strategy_template": "sma-long-cash",',
            '  "symbol": "SPY",',
            '  "opportunity_thesis_id": "liquid_etf_trend_defense",',
            '  "parameters": {"sma_length": 200},',
            '  "success_criteria": {"minimum_cagr_retention": 0.8},',
            '  "validation_plan": {"cost_sensitivity": true, "date_sensitivity": true, "train_test": true}',
            "}",
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
