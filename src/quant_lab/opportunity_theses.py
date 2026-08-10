"""Opportunity-thesis catalog loading and validation.

Opportunity theses sit above executable strategies. They describe why a market
imperfection might exist before the project asks whether a specific strategy can
measure it. Keeping this layer conceptual helps future agent workflows search
for economic mechanisms instead of blindly rotating through parameterized rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


OPPORTUNITY_SCHEMA_VERSION = "opportunity_thesis.v1"
REQUIRED_OPPORTUNITY_FIELDS = {
    "schema_version",
    "thesis_id",
    "title",
    "market_niche",
    "universe",
    "phenomenon",
    "counterparty_or_forced_actor",
    "why_edge_might_exist",
    "why_large_funds_might_ignore_it",
    "institutional_constraint_evidence",
    "expected_capacity",
    "expected_holding_period",
    "execution_constraints",
    "persistence_mechanism",
    "crowding_risk",
    "edge_decay_trigger",
    "observable_prediction",
    "falsification_tests",
    "required_project_capabilities",
    "compatible_strategy_families",
    "suggested_validation",
    "references",
    "engine_fit",
    "rubric",
    "decision",
}
REQUIRED_CONSTRAINT_EVIDENCE_FIELDS = {
    "expected_daily_dollar_volume",
    "estimated_position_size",
    "estimated_strategy_capacity",
    "number_of_opportunities_per_year",
    "estimated_absolute_pnl_at_capacity",
    "evidence_quality",
}
REQUIRED_RUBRIC_FIELDS = {
    "structural_plausibility",
    "small_capital_advantage",
    "falsifiability",
    "deployability",
    "engine_fit",
}
ALLOWED_EVIDENCE_QUALITY = {"unknown", "speculative", "estimated", "measured"}
ALLOWED_RUBRIC_VALUES = {
    "structural_plausibility": {"pass", "weak", "fail"},
    "small_capital_advantage": {"pass", "weak", "fail"},
    "falsifiability": {"pass", "fail"},
    "deployability": {"pass", "blocked"},
    "engine_fit": {"ready", "blocked"},
}
ALLOWED_DECISIONS = {"test_now", "investigate_data", "watchlist", "reject"}


@dataclass(frozen=True)
class OpportunityThesis:
    path: Path
    payload: dict[str, Any]

    @property
    def thesis_id(self) -> str:
        return str(self.payload["thesis_id"])

    @property
    def title(self) -> str:
        return str(self.payload["title"])

    @property
    def compatible_strategy_families(self) -> list[str]:
        return [str(item) for item in self.payload.get("compatible_strategy_families", [])]

    @property
    def decision(self) -> str:
        return str(self.payload["decision"])

    @property
    def engine_fit(self) -> str:
        return str(self.payload["engine_fit"])


def load_opportunity_catalog(catalog_dir: str | Path) -> list[OpportunityThesis]:
    """Load conceptual opportunity theses from JSON files."""

    root = Path(catalog_dir)
    if not root.exists():
        raise FileNotFoundError(f"Opportunity catalog directory not found: {root}")

    theses: list[OpportunityThesis] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_opportunity_thesis(payload, path)
        theses.append(OpportunityThesis(path=path, payload=payload))

    if not theses:
        raise ValueError(f"No opportunity thesis JSON files found in {root}")
    return theses


def validate_opportunity_thesis(payload: dict[str, Any], path: Path | None = None) -> None:
    label = str(path) if path is not None else "opportunity thesis"
    missing = sorted(REQUIRED_OPPORTUNITY_FIELDS.difference(payload))
    if missing:
        raise ValueError(f"{label} is missing required opportunity fields: {', '.join(missing)}")
    if payload["schema_version"] != OPPORTUNITY_SCHEMA_VERSION:
        raise ValueError(f"{label} has unsupported schema_version: {payload['schema_version']}")

    for list_field in (
        "execution_constraints",
        "falsification_tests",
        "required_project_capabilities",
        "compatible_strategy_families",
        "suggested_validation",
        "references",
    ):
        if not isinstance(payload[list_field], list) or not payload[list_field]:
            raise ValueError(f"{label} must define a non-empty {list_field} list")

    evidence = payload["institutional_constraint_evidence"]
    if not isinstance(evidence, dict):
        raise ValueError(f"{label} institutional_constraint_evidence must be an object")
    missing_evidence = sorted(REQUIRED_CONSTRAINT_EVIDENCE_FIELDS.difference(evidence))
    if missing_evidence:
        raise ValueError(
            f"{label} institutional_constraint_evidence is missing fields: {', '.join(missing_evidence)}"
        )
    if evidence["evidence_quality"] not in ALLOWED_EVIDENCE_QUALITY:
        raise ValueError(f"{label} has unsupported evidence_quality: {evidence['evidence_quality']}")

    rubric = payload["rubric"]
    if not isinstance(rubric, dict):
        raise ValueError(f"{label} rubric must be an object")
    missing_rubric = sorted(REQUIRED_RUBRIC_FIELDS.difference(rubric))
    if missing_rubric:
        raise ValueError(f"{label} rubric is missing fields: {', '.join(missing_rubric)}")
    for field, allowed_values in ALLOWED_RUBRIC_VALUES.items():
        if rubric[field] not in allowed_values:
            raise ValueError(f"{label} rubric.{field} has unsupported value: {rubric[field]}")

    if payload["decision"] not in ALLOWED_DECISIONS:
        raise ValueError(f"{label} has unsupported decision: {payload['decision']}")


def find_opportunity_for_strategy_family(
    theses: list[OpportunityThesis],
    family_id: str,
) -> OpportunityThesis | None:
    """Return the first currently testable thesis compatible with a strategy family."""

    candidates = [
        thesis
        for thesis in theses
        if family_id in thesis.compatible_strategy_families
        and thesis.decision == "test_now"
        and thesis.engine_fit == "ready"
    ]
    return candidates[0] if candidates else None
