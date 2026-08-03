"""Guided research workflow plan files."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .research_plan_common import (
    normalize_recommended_steps,
    optional_float,
    utc_now_iso,
    validate_required_text_fields,
    write_json_payload,
)


RESEARCH_PLAN_SCHEMA_VERSION = "research_plan.v1"
DEFAULT_RECOMMENDED_STEPS = (
    "baseline",
    "sweep",
    "train_test",
    "walk_forward",
    "summarize",
    "decide",
)


@dataclass(frozen=True)
class SuccessCriterion:
    name: str
    metric: str
    comparison: str
    operator: str
    threshold: float | str | list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class InvestmentObjective:
    intended_benefit: str
    benchmark: str
    primary_metric: str
    minimum_acceptable_performance: str
    important_tradeoffs: list[str] = field(default_factory=list)
    success_criteria: list[SuccessCriterion] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intended_benefit": self.intended_benefit,
            "benchmark": self.benchmark,
            "primary_metric": self.primary_metric,
            "minimum_acceptable_performance": self.minimum_acceptable_performance,
            "important_tradeoffs": list(self.important_tradeoffs),
            "success_criteria": [criterion.to_dict() for criterion in self.success_criteria],
        }


@dataclass(frozen=True)
class ResearchPlan:
    """Durable local state for one guided research question.

    The plan stores intent and paths only. Run results continue to live in
    `run_metadata.json`, the research index, experiment records, and summary
    artifacts so the workflow stays transparent instead of hiding evidence in a
    second state store.
    """

    schema_version: str
    title: str
    hypothesis: str
    strategy_path: str
    data_path: str
    symbol: str
    experiment_id: str
    experiments_path: str
    index_path: str
    output_dir: str
    initial_cash: float = 100_000.0
    quantity: float = 1.0
    sizing: str = "percent-equity"
    allocation: float = 1.0
    benchmark: str = "buy-and-hold"
    cost_preset: str = "none"
    commission_fixed: float | None = None
    commission_rate: float | None = None
    slippage_bps: float | None = None
    investment_objective: InvestmentObjective | None = None
    recommended_steps: list[str] = field(default_factory=lambda: list(DEFAULT_RECOMMENDED_STEPS))
    tags: list[str] = field(default_factory=list)
    created_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


def create_research_plan(
    *,
    title: str,
    hypothesis: str,
    strategy_path: str | Path,
    data_path: str | Path,
    symbol: str,
    experiment_id: str,
    output_dir: str | Path,
    experiments_path: str | Path = "artifacts/experiments.jsonl",
    index_path: str | Path = "artifacts/research_index.jsonl",
    initial_cash: float = 100_000.0,
    quantity: float = 1.0,
    sizing: str = "percent-equity",
    allocation: float = 1.0,
    benchmark: str = "buy-and-hold",
    cost_preset: str = "none",
    commission_fixed: float | None = None,
    commission_rate: float | None = None,
    slippage_bps: float | None = None,
    intended_benefit: str | None = None,
    primary_metric: str | None = None,
    minimum_acceptable_performance: str | None = None,
    important_tradeoffs: Iterable[str] | None = None,
    success_criteria: Iterable[SuccessCriterion | dict] | None = None,
    tags: Iterable[str] | None = None,
    recommended_steps: Iterable[str] = DEFAULT_RECOMMENDED_STEPS,
    created_at_utc: str | None = None,
) -> ResearchPlan:
    plan = ResearchPlan(
        schema_version=RESEARCH_PLAN_SCHEMA_VERSION,
        title=title.strip(),
        hypothesis=hypothesis.strip(),
        strategy_path=str(strategy_path),
        data_path=str(data_path),
        symbol=symbol.strip().upper(),
        experiment_id=experiment_id.strip(),
        experiments_path=str(experiments_path),
        index_path=str(index_path),
        output_dir=str(output_dir),
        initial_cash=float(initial_cash),
        quantity=float(quantity),
        sizing=sizing,
        allocation=float(allocation),
        benchmark=benchmark,
        cost_preset=cost_preset,
        commission_fixed=float(commission_fixed) if commission_fixed is not None else None,
        commission_rate=float(commission_rate) if commission_rate is not None else None,
        slippage_bps=float(slippage_bps) if slippage_bps is not None else None,
        investment_objective=create_investment_objective(
            intended_benefit=intended_benefit,
            benchmark=benchmark,
            primary_metric=primary_metric,
            minimum_acceptable_performance=minimum_acceptable_performance,
            important_tradeoffs=important_tradeoffs or [],
            success_criteria=success_criteria or [],
        ),
        recommended_steps=normalize_recommended_steps(recommended_steps),
        tags=normalize_plan_tags(tags or []),
        created_at_utc=created_at_utc or utc_now_iso(),
    )
    validate_research_plan(plan)
    return plan


def normalize_plan_tags(tags: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for raw_tag in tags:
        for tag in str(raw_tag).split(","):
            cleaned = tag.strip().lower()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
    return normalized


def create_investment_objective(
    *,
    intended_benefit: str | None,
    benchmark: str,
    primary_metric: str | None,
    minimum_acceptable_performance: str | None,
    important_tradeoffs: Iterable[str],
    success_criteria: Iterable[SuccessCriterion | dict],
) -> InvestmentObjective | None:
    tradeoff_values = list(important_tradeoffs)
    criterion_values = list(success_criteria)
    if not any([intended_benefit, primary_metric, minimum_acceptable_performance, tradeoff_values, criterion_values]):
        return None
    criteria = [
        criterion if isinstance(criterion, SuccessCriterion) else success_criterion_from_dict(criterion)
        for criterion in criterion_values
    ]
    return InvestmentObjective(
        intended_benefit=(intended_benefit or "Not prespecified.").strip(),
        benchmark=benchmark,
        primary_metric=(primary_metric or "Not prespecified.").strip(),
        minimum_acceptable_performance=(
            minimum_acceptable_performance or "Not prespecified; strategy status should be inconclusive."
        ).strip(),
        important_tradeoffs=[str(tradeoff).strip() for tradeoff in tradeoff_values if str(tradeoff).strip()],
        success_criteria=criteria,
    )


def success_criterion_from_dict(payload: dict) -> SuccessCriterion:
    return SuccessCriterion(
        name=str(payload.get("name", "")),
        metric=str(payload.get("metric", "")),
        comparison=str(payload.get("comparison", "")),
        operator=str(payload.get("operator", "")),
        threshold=payload.get("threshold"),
    )


def validate_research_plan(plan: ResearchPlan) -> None:
    required_fields = {
        "schema_version": plan.schema_version,
        "title": plan.title,
        "hypothesis": plan.hypothesis,
        "strategy_path": plan.strategy_path,
        "data_path": plan.data_path,
        "symbol": plan.symbol,
        "experiment_id": plan.experiment_id,
        "experiments_path": plan.experiments_path,
        "index_path": plan.index_path,
        "output_dir": plan.output_dir,
        "created_at_utc": plan.created_at_utc,
    }
    validate_required_text_fields(required_fields, context="research plan")
    if plan.schema_version != RESEARCH_PLAN_SCHEMA_VERSION:
        raise ValueError(f"unsupported research plan schema: {plan.schema_version}")
    if not plan.recommended_steps:
        raise ValueError("research plan recommended_steps must not be empty")
    if plan.investment_objective is not None:
        validate_investment_objective(plan.investment_objective)


def validate_investment_objective(objective: InvestmentObjective) -> None:
    validate_required_text_fields(
        {
            "intended_benefit": objective.intended_benefit,
            "benchmark": objective.benchmark,
            "primary_metric": objective.primary_metric,
            "minimum_acceptable_performance": objective.minimum_acceptable_performance,
        },
        context="investment objective",
    )
    for criterion in objective.success_criteria:
        validate_required_text_fields(
            {
                "criterion name": criterion.name,
                "criterion metric": criterion.metric,
                "criterion comparison": criterion.comparison,
                "criterion operator": criterion.operator,
            },
            context="success criterion",
        )
        if criterion.threshold is None:
            raise ValueError("success criterion threshold must not be null")


def research_plan_json_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / "research_plan.json"


def research_plan_markdown_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / "research_plan.md"


def save_research_plan(plan: ResearchPlan) -> tuple[str, str]:
    output_dir = Path(plan.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = research_plan_json_path(output_dir)
    write_json_payload(json_path, plan.to_dict())

    markdown_path = research_plan_markdown_path(output_dir)
    markdown_path.write_text(render_research_plan_markdown(plan), encoding="utf-8")
    return str(json_path), str(markdown_path)


def load_research_plan(plan_path: str | Path) -> ResearchPlan:
    payload = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    plan = ResearchPlan(
        schema_version=str(payload.get("schema_version", "")),
        title=str(payload.get("title", "")),
        hypothesis=str(payload.get("hypothesis", "")),
        strategy_path=str(payload.get("strategy_path", "")),
        data_path=str(payload.get("data_path", "")),
        symbol=str(payload.get("symbol", "")),
        experiment_id=str(payload.get("experiment_id", "")),
        experiments_path=str(payload.get("experiments_path", "")),
        index_path=str(payload.get("index_path", "")),
        output_dir=str(payload.get("output_dir", "")),
        initial_cash=float(payload.get("initial_cash", 100_000.0)),
        quantity=float(payload.get("quantity", 1.0)),
        sizing=str(payload.get("sizing", "percent-equity")),
        allocation=float(payload.get("allocation", 1.0)),
        benchmark=str(payload.get("benchmark", "buy-and-hold")),
        cost_preset=str(payload.get("cost_preset", "none")),
        commission_fixed=optional_float(payload.get("commission_fixed")),
        commission_rate=optional_float(payload.get("commission_rate")),
        slippage_bps=optional_float(payload.get("slippage_bps")),
        investment_objective=investment_objective_from_dict(payload.get("investment_objective")),
        recommended_steps=[str(step) for step in payload.get("recommended_steps", [])],
        tags=[str(tag) for tag in payload.get("tags", [])],
        created_at_utc=str(payload.get("created_at_utc", "")),
    )
    validate_research_plan(plan)
    return plan


def investment_objective_from_dict(payload: object) -> InvestmentObjective | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("investment_objective must be an object or null")
    return InvestmentObjective(
        intended_benefit=str(payload.get("intended_benefit", "")),
        benchmark=str(payload.get("benchmark", "")),
        primary_metric=str(payload.get("primary_metric", "")),
        minimum_acceptable_performance=str(payload.get("minimum_acceptable_performance", "")),
        important_tradeoffs=[str(item) for item in payload.get("important_tradeoffs", [])],
        success_criteria=[
            success_criterion_from_dict(item)
            for item in payload.get("success_criteria", [])
        ],
    )


def render_research_plan_markdown(plan: ResearchPlan) -> str:
    tag_lines = "\n".join(f"- `{tag}`" for tag in plan.tags) if plan.tags else "- none"
    step_lines = "\n".join(f"- {step}" for step in plan.recommended_steps)
    return f"""# {plan.title}

## Hypothesis

{plan.hypothesis}

## Investment Objective

{_render_investment_objective(plan.investment_objective)}

## Inputs

- Strategy: `{plan.strategy_path}`
- Data: `{plan.data_path}`
- Symbol: `{plan.symbol}`
- Experiment: `{plan.experiment_id}`
- Experiment registry: `{plan.experiments_path}`
- Research index: `{plan.index_path}`
- Output directory: `{plan.output_dir}`
- Created at UTC: `{plan.created_at_utc}`

## Run Defaults

- Initial cash: `{plan.initial_cash}`
- Quantity: `{plan.quantity}`
- Sizing: `{plan.sizing}`
- Allocation: `{plan.allocation}`
- Benchmark: `{plan.benchmark}`
- Cost preset: `{plan.cost_preset}`
- Commission fixed: `{plan.commission_fixed}`
- Commission rate: `{plan.commission_rate}`
- Slippage bps: `{plan.slippage_bps}`

## Tags

{tag_lines}

## Recommended Steps

{step_lines}

## Skeptic Reminder

This plan organizes research. It does not prove a trading edge. Treat every
result as local evidence tied to the selected data, strategy, costs, benchmark,
and date range.
"""


def _render_investment_objective(objective: InvestmentObjective | None) -> str:
    if objective is None:
        return "\n".join(
            [
                "- Intended benefit: `not_prespecified`",
                "- Primary metric: `not_prespecified`",
                "- Minimum acceptable performance: `not_prespecified`",
                "- Success criteria: `not_prespecified`",
            ]
        )
    tradeoffs = "\n".join(f"  - {item}" for item in objective.important_tradeoffs) or "  - none"
    criteria = "\n".join(
        (
            f"  - `{criterion.name}`: `{criterion.metric}` "
            f"{criterion.comparison} {criterion.operator} `{criterion.threshold}`"
        )
        for criterion in objective.success_criteria
    ) or "  - none"
    return "\n".join(
        [
            f"- Intended benefit: {objective.intended_benefit}",
            f"- Benchmark: `{objective.benchmark}`",
            f"- Primary metric: `{objective.primary_metric}`",
            f"- Minimum acceptable performance: {objective.minimum_acceptable_performance}",
            "- Important trade-offs:",
            tradeoffs,
            "- Success criteria:",
            criteria,
        ]
    )
