"""Guided research workflow plan files for portfolio ideas."""

from __future__ import annotations

import json
import shlex
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from .research_plan import normalize_plan_tags

PORTFOLIO_RESEARCH_PLAN_SCHEMA_VERSION = "portfolio_research_plan.v1"
DEFAULT_PORTFOLIO_RECOMMENDED_STEPS = (
    "baseline",
    "inspect",
    "compare",
    "summarize",
    "decide",
)


@dataclass(frozen=True)
class PortfolioResearchPlan:
    """Durable local state for one guided portfolio research question."""

    schema_version: str
    title: str
    hypothesis: str
    portfolio_path: str
    experiment_id: str
    experiments_path: str
    index_path: str
    output_dir: str
    initial_cash: float = 100_000.0
    cost_preset: str = "none"
    commission_fixed: float | None = None
    commission_rate: float | None = None
    slippage_bps: float | None = None
    recommended_steps: list[str] = field(default_factory=lambda: list(DEFAULT_PORTFOLIO_RECOMMENDED_STEPS))
    tags: list[str] = field(default_factory=list)
    created_at_utc: str = field(default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioPlanRecommendation:
    step: str
    reason: str
    command: str | None


def create_portfolio_research_plan(
    *,
    title: str,
    hypothesis: str,
    portfolio_path: str | Path,
    experiment_id: str,
    output_dir: str | Path,
    experiments_path: str | Path = "artifacts/experiments.jsonl",
    index_path: str | Path = "artifacts/research_index.jsonl",
    initial_cash: float = 100_000.0,
    cost_preset: str = "none",
    commission_fixed: float | None = None,
    commission_rate: float | None = None,
    slippage_bps: float | None = None,
    tags: Iterable[str] | None = None,
    recommended_steps: Iterable[str] = DEFAULT_PORTFOLIO_RECOMMENDED_STEPS,
    created_at_utc: str | None = None,
) -> PortfolioResearchPlan:
    plan = PortfolioResearchPlan(
        schema_version=PORTFOLIO_RESEARCH_PLAN_SCHEMA_VERSION,
        title=title.strip(),
        hypothesis=hypothesis.strip(),
        portfolio_path=str(portfolio_path),
        experiment_id=experiment_id.strip(),
        experiments_path=str(experiments_path),
        index_path=str(index_path),
        output_dir=str(output_dir),
        initial_cash=float(initial_cash),
        cost_preset=cost_preset,
        commission_fixed=float(commission_fixed) if commission_fixed is not None else None,
        commission_rate=float(commission_rate) if commission_rate is not None else None,
        slippage_bps=float(slippage_bps) if slippage_bps is not None else None,
        recommended_steps=[str(step).strip() for step in recommended_steps if str(step).strip()],
        tags=normalize_plan_tags(tags or []),
        created_at_utc=created_at_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    validate_portfolio_research_plan(plan)
    return plan


def validate_portfolio_research_plan(plan: PortfolioResearchPlan) -> None:
    required_fields = {
        "schema_version": plan.schema_version,
        "title": plan.title,
        "hypothesis": plan.hypothesis,
        "portfolio_path": plan.portfolio_path,
        "experiment_id": plan.experiment_id,
        "experiments_path": plan.experiments_path,
        "index_path": plan.index_path,
        "output_dir": plan.output_dir,
        "created_at_utc": plan.created_at_utc,
    }
    for field_name, value in required_fields.items():
        if not str(value).strip():
            raise ValueError(f"portfolio research plan {field_name} must not be empty")
    if plan.schema_version != PORTFOLIO_RESEARCH_PLAN_SCHEMA_VERSION:
        raise ValueError(f"unsupported portfolio research plan schema: {plan.schema_version}")
    if not plan.recommended_steps:
        raise ValueError("portfolio research plan recommended_steps must not be empty")


def portfolio_research_plan_json_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / "portfolio_research_plan.json"


def portfolio_research_plan_markdown_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / "portfolio_research_plan.md"


def save_portfolio_research_plan(plan: PortfolioResearchPlan) -> tuple[str, str]:
    output_dir = Path(plan.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = portfolio_research_plan_json_path(output_dir)
    json_path.write_text(json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    markdown_path = portfolio_research_plan_markdown_path(output_dir)
    markdown_path.write_text(render_portfolio_research_plan_markdown(plan), encoding="utf-8")
    return str(json_path), str(markdown_path)


def load_portfolio_research_plan(plan_path: str | Path) -> PortfolioResearchPlan:
    payload = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    plan = PortfolioResearchPlan(
        schema_version=str(payload.get("schema_version", "")),
        title=str(payload.get("title", "")),
        hypothesis=str(payload.get("hypothesis", "")),
        portfolio_path=str(payload.get("portfolio_path", "")),
        experiment_id=str(payload.get("experiment_id", "")),
        experiments_path=str(payload.get("experiments_path", "")),
        index_path=str(payload.get("index_path", "")),
        output_dir=str(payload.get("output_dir", "")),
        initial_cash=float(payload.get("initial_cash", 100_000.0)),
        cost_preset=str(payload.get("cost_preset", "none")),
        commission_fixed=_optional_float(payload.get("commission_fixed")),
        commission_rate=_optional_float(payload.get("commission_rate")),
        slippage_bps=_optional_float(payload.get("slippage_bps")),
        recommended_steps=[str(step) for step in payload.get("recommended_steps", [])],
        tags=[str(tag) for tag in payload.get("tags", [])],
        created_at_utc=str(payload.get("created_at_utc", "")),
    )
    validate_portfolio_research_plan(plan)
    return plan


def render_portfolio_research_plan_markdown(plan: PortfolioResearchPlan) -> str:
    tag_lines = "\n".join(f"- `{tag}`" for tag in plan.tags) if plan.tags else "- none"
    step_lines = "\n".join(f"- {step}" for step in plan.recommended_steps)
    return f"""# {plan.title}

## Hypothesis

{plan.hypothesis}

## Inputs

- Portfolio: `{plan.portfolio_path}`
- Experiment: `{plan.experiment_id}`
- Experiment registry: `{plan.experiments_path}`
- Research index: `{plan.index_path}`
- Output directory: `{plan.output_dir}`
- Created at UTC: `{plan.created_at_utc}`

## Run Defaults

- Initial cash: `{plan.initial_cash}`
- Cost preset: `{plan.cost_preset}`
- Commission fixed: `{plan.commission_fixed}`
- Commission rate: `{plan.commission_rate}`
- Slippage bps: `{plan.slippage_bps}`

## Tags

{tag_lines}

## Recommended Steps

{step_lines}

## Skeptic Reminder

This plan organizes portfolio research. It does not prove that an allocation is
robust. Treat every result as local evidence tied to the selected data,
weights, rebalance rule, costs, benchmark, and date range.
"""


def recommend_portfolio_next_step(
    plan: PortfolioResearchPlan,
    index_records: list[dict],
    *,
    experiment_has_decision: bool = False,
) -> PortfolioPlanRecommendation:
    if experiment_has_decision:
        return PortfolioPlanRecommendation(
            step="done",
            reason="The experiment already has a recorded decision.",
            command=None,
        )
    portfolio_records = [
        record for record in index_records if str(record.get("run_type")) == "portfolio_run"
    ]
    metadata_paths = [
        str(record.get("metadata_path"))
        for record in portfolio_records
        if str(record.get("metadata_path", "")).strip()
    ]
    if not metadata_paths:
        return PortfolioPlanRecommendation(
            step="baseline",
            reason="No portfolio run is linked to this experiment yet.",
            command=build_portfolio_baseline_command_from_plan(plan),
        )
    if len(metadata_paths) == 1:
        return PortfolioPlanRecommendation(
            step="inspect",
            reason="One portfolio run exists; inspect it before making comparisons.",
            command=build_show_portfolio_run_command(metadata_paths[0]),
        )
    return PortfolioPlanRecommendation(
        step="compare",
        reason="Multiple portfolio runs exist; compare them before summarizing evidence.",
        command=build_compare_portfolio_runs_command(metadata_paths),
    )


def build_portfolio_baseline_command_from_plan(plan: PortfolioResearchPlan) -> str:
    command = [
        "quant-lab",
        "portfolio-run",
        "--portfolio",
        plan.portfolio_path,
        "--out",
        str(Path(plan.output_dir) / "baseline"),
        "--initial-cash",
        str(plan.initial_cash),
        "--cost-preset",
        plan.cost_preset,
        "--experiments-path",
        plan.experiments_path,
        "--experiment-id",
        plan.experiment_id,
        "--index-path",
        plan.index_path,
    ]
    add_optional_cost_overrides(command, plan.commission_fixed, plan.commission_rate, plan.slippage_bps)
    return shlex.join(command)


def build_show_portfolio_run_command(metadata_path: str) -> str:
    return shlex.join(["quant-lab", "show-portfolio-run", "--metadata", metadata_path])


def build_compare_portfolio_runs_command(metadata_paths: list[str]) -> str:
    command = ["quant-lab", "compare-portfolio-runs"]
    for metadata_path in metadata_paths:
        command.extend(["--metadata", metadata_path])
    return shlex.join(command)


def build_portfolio_summarize_command_from_plan(plan: PortfolioResearchPlan) -> str:
    return shlex.join(
        [
            "quant-lab",
            "summarize-experiment",
            "--experiment-id",
            plan.experiment_id,
            "--experiments-path",
            plan.experiments_path,
            "--index-path",
            plan.index_path,
        ]
    )


def add_optional_cost_overrides(
    command: list[str],
    commission_fixed: float | None,
    commission_rate: float | None,
    slippage_bps: float | None,
) -> None:
    if commission_fixed is not None:
        command.extend(["--commission-fixed", str(commission_fixed)])
    if commission_rate is not None:
        command.extend(["--commission-rate", str(commission_rate)])
    if slippage_bps is not None:
        command.extend(["--slippage-bps", str(slippage_bps)])


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
