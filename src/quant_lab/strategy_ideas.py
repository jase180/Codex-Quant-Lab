"""Conceptual strategy catalog loading and next-idea suggestion."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from .research_registry import load_experiments


CATALOG_SCHEMA_VERSION = "strategy_catalog_entry.v1"
REQUIRED_CATALOG_FIELDS = {
    "schema_version",
    "family_id",
    "name",
    "rationale",
    "expected_benefit",
    "failure_modes",
    "required_project_capabilities",
    "canonical_variants",
    "suggested_validation",
    "references",
    "engine_can_currently_execute",
}
REQUIRED_VARIANT_FIELDS = {
    "variant_id",
    "name",
    "description",
    "matching_terms",
    "hypothesis_template",
    "primary_metric",
    "benchmark",
    "minimum_acceptable_performance",
    "success_criteria",
    "engine_can_currently_execute",
    "research_priority",
    "capability_status",
    "next_action",
}
ALLOWED_RESEARCH_PRIORITIES = {"core", "secondary", "later"}
ALLOWED_CAPABILITY_STATUSES = {
    "executable_now",
    "small_schema_extension_required",
    "data_extension_required",
    "portfolio_extension_required",
    "unsupported_now",
}


@dataclass(frozen=True)
class CatalogEntry:
    path: Path
    payload: dict[str, Any]

    @property
    def family_id(self) -> str:
        return str(self.payload["family_id"])

    @property
    def name(self) -> str:
        return str(self.payload["name"])

    @property
    def engine_can_currently_execute(self) -> bool:
        return bool(self.payload["engine_can_currently_execute"])

    @property
    def canonical_variants(self) -> list[dict[str, Any]]:
        return list(self.payload.get("canonical_variants", []))


@dataclass(frozen=True)
class RankedStrategyIdea:
    family_id: str
    family_name: str
    variant_id: str
    variant_name: str
    score: int
    reasons: list[str]


@dataclass(frozen=True)
class StrategyIdeaSuggestion:
    family: CatalogEntry
    variant: dict[str, Any]
    score: int
    reasons: list[str]
    rankings: list[RankedStrategyIdea]
    excluded_families: list[str]
    prior_research_count: int
    draft_experiment_config: dict[str, Any]


def load_strategy_catalog(catalog_dir: str | Path) -> list[CatalogEntry]:
    """Load conceptual strategy families from JSON files.

    These files are intentionally separate from executable strategy JSON. They
    describe research ideas and prerequisites; they should not be passed to the
    backtester.
    """

    root = Path(catalog_dir)
    if not root.exists():
        raise FileNotFoundError(f"Strategy catalog directory not found: {root}")

    entries: list[CatalogEntry] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        _validate_catalog_payload(payload, path)
        entries.append(CatalogEntry(path=path, payload=payload))

    if not entries:
        raise ValueError(f"No strategy catalog JSON files found in {root}")
    return entries


def load_experiment_conclusions(conclusions_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(conclusions_dir)
    if not root.exists():
        return []

    conclusions: list[dict[str, Any]] = []
    for path in sorted(root.rglob("experiment_conclusion.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["_path"] = str(path)
        conclusions.append(payload)
    return conclusions


def load_experiment_decisions(experiments_path: str | Path) -> list[dict[str, Any]]:
    path = Path(experiments_path)
    if not path.exists():
        return []

    decisions: list[dict[str, Any]] = []
    for experiment in load_experiments(path):
        if experiment.decision_record is None:
            continue
        decisions.append(
            {
                "schema_version": "experiment_decision_memory.v1",
                "experiment_id": experiment.experiment_id,
                "title": experiment.title,
                "hypothesis": experiment.hypothesis,
                "tags": experiment.tags,
                "strategy_path": experiment.strategy_path,
                "data_path": experiment.data_path,
                "notes": experiment.notes,
                "decision": experiment.decision,
                "decision_record": experiment.decision_record.to_dict(),
            }
        )
    return decisions


def load_experiment_handoffs(handoffs_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(handoffs_dir)
    if not root.exists():
        return []

    handoffs: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        handoffs.append(
            {
                "schema_version": "experiment_handoff_memory.v1",
                "path": str(path),
                "content": text,
            }
        )
    return handoffs


def suggest_strategy_idea(
    *,
    catalog_dir: str | Path = "data/strategy_catalog",
    conclusions_dir: str | Path = "artifacts/research",
    experiments_path: str | Path = "artifacts/experiments.jsonl",
    handoffs_dir: str | Path = "docs/experiments",
) -> StrategyIdeaSuggestion:
    catalog = load_strategy_catalog(catalog_dir)
    prior_research = [
        *load_experiment_conclusions(conclusions_dir),
        *load_experiment_decisions(experiments_path),
        *load_experiment_handoffs(handoffs_dir),
    ]

    scored: list[StrategyIdeaSuggestion] = []
    excluded_families: list[str] = []
    for entry in catalog:
        if _matches_exclusion(entry, prior_research):
            excluded_families.append(entry.family_id)
            continue

        variant = _first_executable_variant(entry)
        if variant is None:
            excluded_families.append(f"{entry.family_id} (not executable)")
            continue

        score, reasons = _score_entry(entry, variant, prior_research)
        scored.append(
            StrategyIdeaSuggestion(
                family=entry,
                variant=variant,
                score=score,
                reasons=reasons,
                rankings=[],
                excluded_families=[],
                prior_research_count=len(prior_research),
                draft_experiment_config=_draft_experiment_config(entry, variant),
            )
        )

    if not scored:
        raise ValueError("No executable strategy catalog idea remains after applying do_not_repeat constraints.")

    scored.sort(key=lambda suggestion: (-suggestion.score, suggestion.family.family_id))
    selected = scored[0]
    rankings = [
        RankedStrategyIdea(
            family_id=item.family.family_id,
            family_name=item.family.name,
            variant_id=str(item.variant["variant_id"]),
            variant_name=str(item.variant["name"]),
            score=item.score,
            reasons=item.reasons,
        )
        for item in scored
    ]
    return StrategyIdeaSuggestion(
        family=selected.family,
        variant=selected.variant,
        score=selected.score,
        reasons=selected.reasons,
        rankings=rankings,
        excluded_families=excluded_families,
        prior_research_count=selected.prior_research_count,
        draft_experiment_config=selected.draft_experiment_config,
    )


def format_strategy_idea_suggestion(suggestion: StrategyIdeaSuggestion) -> str:
    config_json = json.dumps(suggestion.draft_experiment_config, indent=2, sort_keys=True)
    reasons = "\n".join(f"- {reason}" for reason in suggestion.reasons)
    rankings = "\n".join(
        f"- {item.family_name} (`{item.family_id}`), variant `{item.variant_id}`: score {item.score}"
        for item in suggestion.rankings
    )
    excluded = "\n".join(f"- {family}" for family in suggestion.excluded_families) or "- none"
    criteria = "\n".join(
        f"- {item['name']}: {item['comparison']} {item['operator']} {item['threshold']} on {item['metric']}"
        for item in suggestion.draft_experiment_config["success_criteria"]
    )

    return "\n".join(
        [
            "# Strategy Idea Suggestion",
            "",
            f"Selected family: {suggestion.family.name} (`{suggestion.family.family_id}`)",
            f"Selected variant: {suggestion.variant['name']} (`{suggestion.variant['variant_id']}`)",
            f"Prior research records read: {suggestion.prior_research_count}",
            "",
            "## Why This Ranked First",
            reasons,
            "",
            "## Compatible Family Ranking",
            rankings,
            "",
            "## Excluded Ideas",
            excluded,
            "",
            "## Proposed Hypothesis",
            suggestion.draft_experiment_config["hypothesis"],
            "",
            "## Success Criteria",
            criteria,
            "",
            "## Draft Experiment Config",
            "```json",
            config_json,
            "```",
            "",
            "No executable strategy or portfolio spec was created. Convert this idea only after human approval.",
        ]
    )


def _validate_catalog_payload(payload: dict[str, Any], path: Path) -> None:
    missing = sorted(REQUIRED_CATALOG_FIELDS.difference(payload))
    if missing:
        raise ValueError(f"{path} is missing required catalog fields: {', '.join(missing)}")
    if payload["schema_version"] != CATALOG_SCHEMA_VERSION:
        raise ValueError(f"{path} has unsupported schema_version: {payload['schema_version']}")
    if not isinstance(payload["canonical_variants"], list) or not payload["canonical_variants"]:
        raise ValueError(f"{path} must define at least one canonical variant")
    for index, variant in enumerate(payload["canonical_variants"], start=1):
        _validate_catalog_variant(variant, path, index)


def _validate_catalog_variant(variant: dict[str, Any], path: Path, index: int) -> None:
    missing = sorted(REQUIRED_VARIANT_FIELDS.difference(variant))
    if missing:
        raise ValueError(f"{path} variant {index} is missing required fields: {', '.join(missing)}")

    priority = variant["research_priority"]
    if priority not in ALLOWED_RESEARCH_PRIORITIES:
        raise ValueError(f"{path} variant {index} has unsupported research_priority: {priority}")

    capability_status = variant["capability_status"]
    if capability_status not in ALLOWED_CAPABILITY_STATUSES:
        raise ValueError(f"{path} variant {index} has unsupported capability_status: {capability_status}")

    executable = bool(variant["engine_can_currently_execute"])
    if executable and capability_status != "executable_now":
        raise ValueError(f"{path} variant {index} is executable but capability_status is {capability_status}")
    if not executable and capability_status == "executable_now":
        raise ValueError(f"{path} variant {index} is marked executable_now but is not executable")


def _first_executable_variant(entry: CatalogEntry) -> dict[str, Any] | None:
    if not entry.engine_can_currently_execute:
        return None
    for variant in entry.canonical_variants:
        if variant.get("engine_can_currently_execute"):
            return variant
    return None


def _score_entry(entry: CatalogEntry, variant: dict[str, Any], conclusions: Sequence[dict[str, Any]]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    if entry.engine_can_currently_execute:
        score += 5
        reasons.append("The catalog says the current engine can execute this family.")
    if variant.get("engine_can_currently_execute"):
        score += 2
        reasons.append("The selected canonical variant is currently executable.")
    if not _matches_any_conclusion(entry, conclusions):
        score += 2
        reasons.append("Prior conclusions do not appear to have already tested this family directly.")
    else:
        reasons.append("Prior conclusions mention this family, so treat the hypothesis as a new formulation.")
    if variant.get("research_priority") == "core":
        score += 1
        reasons.append("The catalog marks this variant as a core research idea.")

    return score, reasons


def _draft_experiment_config(entry: CatalogEntry, variant: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": f"{entry.name}: {variant['name']}",
        "strategy_family": entry.family_id,
        "catalog_variant": variant["variant_id"],
        "hypothesis": variant["hypothesis_template"],
        "intended_benefit": entry.payload["expected_benefit"],
        "benchmark": variant["benchmark"],
        "research_priority": variant["research_priority"],
        "capability_status": variant["capability_status"],
        "next_action": variant["next_action"],
        "primary_metric": variant["primary_metric"],
        "minimum_acceptable_performance": variant["minimum_acceptable_performance"],
        "important_tradeoffs": entry.payload["failure_modes"],
        "success_criteria": variant["success_criteria"],
        "suggested_validation": entry.payload["suggested_validation"],
        "requires_human_approval_before_strategy_json": True,
    }


def _exclusion_text(conclusions: Iterable[dict[str, Any]]) -> str:
    parts: list[str] = []
    for conclusion in conclusions:
        parts.extend(str(item) for item in conclusion.get("do_not_repeat", []))
        prompt = conclusion.get("next_research_prompt", {})
        parts.extend(str(item) for item in prompt.get("constraints", []))
        parts.extend(str(item) for item in prompt.get("what_failed", []))
        decision_record = conclusion.get("decision_record", {})
        if isinstance(decision_record, dict):
            parts.append(str(decision_record.get("rationale", "")))
            parts.append(str(decision_record.get("next_action", "")))
        content = conclusion.get("content")
        if isinstance(content, str):
            parts.append(_do_not_repeat_section(content))
    return " ".join(parts).lower()


def _matches_exclusion(entry: CatalogEntry, conclusions: Sequence[dict[str, Any]]) -> bool:
    for conclusion in conclusions:
        direct_exclusion = _exclusion_text([conclusion])
        if not direct_exclusion:
            continue
        if any(_term_matches(term, direct_exclusion) for term in _matching_terms(entry)):
            return True
        if _is_generic_repeat_warning(direct_exclusion) and _conclusion_mentions_entry(entry, conclusion):
            return True
    return False


def _matches_any_conclusion(entry: CatalogEntry, conclusions: Sequence[dict[str, Any]]) -> bool:
    return any(_conclusion_mentions_entry(entry, conclusion) for conclusion in conclusions)


def _conclusion_mentions_entry(entry: CatalogEntry, conclusion: dict[str, Any]) -> bool:
    corpus = json.dumps(conclusion, sort_keys=True).lower()
    return any(_term_matches(term, corpus) for term in _matching_terms(entry))


def _is_generic_repeat_warning(text: str) -> bool:
    repeat_terms = ["do not rerun", "do not repeat", "do not tune", "unchanged", "same setup", "same strategy"]
    return any(term in text for term in repeat_terms)


def _do_not_repeat_section(markdown: str) -> str:
    lines = markdown.splitlines()
    captured: list[str] = []
    in_section = False
    for line in lines:
        if line.startswith("## "):
            if in_section:
                break
            in_section = line.strip().lower() == "## do not repeat"
            continue
        if in_section:
            captured.append(line)
    return "\n".join(captured)


def _matching_terms(entry: CatalogEntry) -> list[str]:
    terms = [entry.family_id.replace("_", " "), entry.family_id, entry.name.lower()]
    for variant in entry.canonical_variants:
        terms.append(str(variant.get("variant_id", "")).replace("_", " ").lower())
        terms.append(str(variant.get("name", "")).lower())
        terms.extend(str(term).lower() for term in variant.get("matching_terms", []))
    return [term for term in terms if term]


def _term_matches(term: str, corpus: str) -> bool:
    if term in corpus:
        return True
    words = [word for word in term.replace("_", " ").split() if len(word) > 2]
    if len(words) < 2:
        return False
    return all(word in corpus for word in words)
