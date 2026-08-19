"""Join mechanism, thesis, dataset, and template catalogs for discovery review."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .experiment_templates import ExperimentTemplate, load_experiment_template_catalog
from .opportunity_theses import OpportunityThesis, load_opportunity_catalog
from .research_datasets import ResearchDatasetPlan, load_research_dataset_plans
from .research_mechanisms import ResearchMechanism, load_research_mechanisms


@dataclass(frozen=True)
class DiscoveryMapEntry:
    mechanism_id: str
    mechanism_title: str
    mechanism_engine_fit: str
    dataset_statuses: list[str]
    opportunity_theses: list[str]
    thesis_decisions: list[str]
    thesis_engine_fits: list[str]
    ready_template_ids: list[str]
    disposition: str
    next_action: str


def build_discovery_map(
    *,
    mechanism_catalog_dir: str | Path = "data/research_mechanisms",
    opportunity_catalog_dir: str | Path = "data/opportunity_catalog",
    dataset_plan_dir: str | Path = "data/research_datasets",
    experiment_template_catalog_dir: str | Path = "data/experiment_template_catalog",
) -> list[DiscoveryMapEntry]:
    """Build a compact map of what is researchable now versus blocked.

    This is intentionally informational. It does not create strategies or run
    experiments; it tells a human or provider where the next bounded candidate
    can honestly come from.
    """

    mechanisms = load_research_mechanisms(mechanism_catalog_dir)
    opportunities = load_opportunity_catalog(opportunity_catalog_dir, mechanism_catalog_dir=mechanism_catalog_dir)
    dataset_plans = load_research_dataset_plans(dataset_plan_dir)
    templates = load_experiment_template_catalog(experiment_template_catalog_dir)

    opportunities_by_mechanism = _opportunities_by_mechanism(opportunities)
    datasets_by_mechanism = _datasets_by_mechanism(dataset_plans)
    template_ids_by_family = _template_ids_by_family(templates)

    return [
        _entry(
            mechanism,
            opportunities=opportunities_by_mechanism.get(mechanism.mechanism_id, []),
            datasets=datasets_by_mechanism.get(mechanism.mechanism_id, []),
            template_ids_by_family=template_ids_by_family,
        )
        for mechanism in mechanisms
    ]


def format_discovery_map(entries: list[DiscoveryMapEntry]) -> str:
    lines = [
        "# Discovery Map",
        "",
        "This map shows which market mechanisms have usable raw material, testable opportunity theses, and campaign-safe templates.",
        "",
        "| mechanism | mechanism fit | datasets | theses | templates | disposition | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        lines.append(
            " | ".join(
                [
                    f"| `{entry.mechanism_id}`",
                    f"`{entry.mechanism_engine_fit}`",
                    _inline_list(entry.dataset_statuses),
                    _inline_list(_thesis_labels(entry)),
                    _inline_list(entry.ready_template_ids),
                    f"`{entry.disposition}`",
                    entry.next_action.replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Disposition meanings:",
            "- `testable_now`: raw material and at least one thesis/template pair are ready for a bounded test.",
            "- `proxy_testable`: a bounded template exists, but it is only a rough proxy for a data-limited mechanism.",
            "- `needs_data`: the mechanism or its theses need better raw data before a real backtest.",
            "- `watchlist`: structurally interesting but not currently the next test.",
            "- `blocked`: current engine/data cannot honestly measure it.",
        ]
    )
    return "\n".join(lines)


def _entry(
    mechanism: ResearchMechanism,
    *,
    opportunities: list[OpportunityThesis],
    datasets: list[ResearchDatasetPlan],
    template_ids_by_family: dict[str, list[str]],
) -> DiscoveryMapEntry:
    ready_templates = _ready_templates(opportunities, template_ids_by_family)
    thesis_decisions = [thesis.decision for thesis in opportunities]
    thesis_engine_fits = [thesis.engine_fit for thesis in opportunities]
    dataset_statuses = [f"{plan.dataset_id}:{plan.status}" for plan in datasets]
    disposition = _disposition(
        mechanism=mechanism,
        opportunities=opportunities,
        ready_templates=ready_templates,
        dataset_statuses=dataset_statuses,
    )
    return DiscoveryMapEntry(
        mechanism_id=mechanism.mechanism_id,
        mechanism_title=mechanism.title,
        mechanism_engine_fit=mechanism.engine_fit,
        dataset_statuses=dataset_statuses,
        opportunity_theses=[thesis.thesis_id for thesis in opportunities],
        thesis_decisions=thesis_decisions,
        thesis_engine_fits=thesis_engine_fits,
        ready_template_ids=ready_templates,
        disposition=disposition,
        next_action=_next_action(mechanism, opportunities, datasets, ready_templates, disposition),
    )


def _opportunities_by_mechanism(opportunities: list[OpportunityThesis]) -> dict[str, list[OpportunityThesis]]:
    grouped: dict[str, list[OpportunityThesis]] = {}
    for thesis in opportunities:
        grouped.setdefault(thesis.mechanism_id, []).append(thesis)
    return grouped


def _datasets_by_mechanism(dataset_plans: list[ResearchDatasetPlan]) -> dict[str, list[ResearchDatasetPlan]]:
    grouped: dict[str, list[ResearchDatasetPlan]] = {}
    for plan in dataset_plans:
        grouped.setdefault(plan.mechanism_id, []).append(plan)
    return grouped


def _template_ids_by_family(templates: list[ExperimentTemplate]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for template in templates:
        if template.engine_support_status != "ready":
            continue
        grouped.setdefault(template.strategy_family, []).append(template.template_id)
    return {family: sorted(ids) for family, ids in grouped.items()}


def _ready_templates(
    opportunities: list[OpportunityThesis],
    template_ids_by_family: dict[str, list[str]],
) -> list[str]:
    template_ids: set[str] = set()
    for thesis in opportunities:
        if thesis.decision != "test_now" or thesis.engine_fit != "ready":
            continue
        for family in thesis.compatible_strategy_families:
            template_ids.update(template_ids_by_family.get(family, []))
    return sorted(template_ids)


def _disposition(
    *,
    mechanism: ResearchMechanism,
    opportunities: list[OpportunityThesis],
    ready_templates: list[str],
    dataset_statuses: list[str],
) -> str:
    if ready_templates:
        if mechanism.engine_fit == "ready" or any(status.endswith(":available") for status in dataset_statuses):
            return "testable_now"
        return "proxy_testable"
    if mechanism.engine_fit == "needs_data" or any(thesis.decision == "investigate_data" for thesis in opportunities):
        return "needs_data"
    if any(thesis.decision == "watchlist" for thesis in opportunities) or mechanism.engine_fit == "proxy_only":
        return "watchlist"
    if mechanism.engine_fit == "blocked" or any(thesis.engine_fit == "blocked" for thesis in opportunities):
        return "blocked"
    if not dataset_statuses:
        return "needs_data"
    return "watchlist"


def _next_action(
    mechanism: ResearchMechanism,
    opportunities: list[OpportunityThesis],
    datasets: list[ResearchDatasetPlan],
    ready_templates: list[str],
    disposition: str,
) -> str:
    if disposition == "testable_now":
        return "Generate a campaign candidate menu; do not add parameters beyond the cataloged template."
    if disposition == "proxy_testable":
        return "Use only as a clearly labeled proxy test, or improve the dataset plan before treating it as mechanism evidence."
    if datasets:
        return str(datasets[0].payload["next_action"])
    if opportunities:
        return "Write or improve a dataset plan before attempting a campaign run."
    return f"Create one opportunity thesis from mechanism `{mechanism.mechanism_id}` before strategy work."


def _thesis_labels(entry: DiscoveryMapEntry) -> list[str]:
    labels: list[str] = []
    for thesis_id, decision, engine_fit in zip(
        entry.opportunity_theses,
        entry.thesis_decisions,
        entry.thesis_engine_fits,
    ):
        labels.append(f"{thesis_id}:{decision}/{engine_fit}")
    return labels


def _inline_list(values: list[str]) -> str:
    if not values:
        return "-"
    return "<br>".join(f"`{value}`" for value in values)
