"""Guided research workflow plan files for portfolio ideas."""

from __future__ import annotations

import json
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .portfolio_spec import load_portfolio_spec
from .research_plan import normalize_plan_tags
from .research_plan_common import (
    add_optional_cost_overrides,
    normalize_recommended_steps,
    optional_float,
    utc_now_iso,
    validate_required_text_fields,
    write_json_payload,
)

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
    created_at_utc: str = field(default_factory=utc_now_iso)

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
        recommended_steps=normalize_recommended_steps(recommended_steps),
        tags=normalize_plan_tags(tags or []),
        created_at_utc=created_at_utc or utc_now_iso(),
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
    validate_required_text_fields(required_fields, context="portfolio research plan")
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
    write_json_payload(json_path, plan.to_dict())

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
        commission_fixed=optional_float(payload.get("commission_fixed")),
        commission_rate=optional_float(payload.get("commission_rate")),
        slippage_bps=optional_float(payload.get("slippage_bps")),
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
    variants_exist: bool = False,
    summary_exists: bool = False,
    candidate_specs_exist: bool = False,
    batch_manifest_exists: bool = False,
    batch_result_exists: bool = False,
    batch_summary_exists: bool = False,
    data_trust_report_exists: bool = False,
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
    if metadata_paths and not data_trust_report_exists:
        return PortfolioPlanRecommendation(
            step="data_trust",
            reason="A portfolio run exists; write a per-symbol data trust report before interpreting results.",
            command=build_portfolio_data_trust_command(metadata_paths[0]),
        )
    if len(metadata_paths) == 1:
        return PortfolioPlanRecommendation(
            step="inspect",
            reason="One portfolio run exists; inspect it before making comparisons.",
            command=build_show_portfolio_run_command(metadata_paths[0]),
        )
    if not summary_exists:
        return PortfolioPlanRecommendation(
            step="summarize",
            reason="Multiple portfolio runs exist; write a portfolio-specific evidence summary.",
            command=build_portfolio_summarize_command_from_plan(plan),
        )
    if not variants_exist:
        return PortfolioPlanRecommendation(
            step="variants",
            reason="Portfolio evidence exists; generate auditable variants before widening the research branch.",
            command=build_portfolio_variants_command_from_plan(plan),
        )
    if candidate_specs_exist and not batch_manifest_exists:
        return PortfolioPlanRecommendation(
            step="batch_plan",
            reason="Portfolio candidate specs exist; write a dry-run batch manifest before executing them.",
            command=build_portfolio_batch_plan_command_from_plan(plan),
        )
    if batch_manifest_exists and not batch_result_exists:
        return PortfolioPlanRecommendation(
            step="batch_run",
            reason="A portfolio batch manifest exists; run it sequentially so each candidate records normal artifacts.",
            command=build_portfolio_batch_run_command_from_plan(plan),
        )
    if batch_result_exists and not batch_summary_exists:
        return PortfolioPlanRecommendation(
            step="batch_summarize",
            reason="A portfolio batch result exists; write the batch guardrail summary before comparing winners.",
            command=build_portfolio_batch_summarize_command_from_plan(plan),
        )
    return PortfolioPlanRecommendation(
        step="compare",
        reason="Portfolio variants and a summary exist; compare source runs when you need a terminal table.",
        command=build_compare_portfolio_runs_command(metadata_paths),
    )


def build_portfolio_baseline_command_from_plan(plan: PortfolioResearchPlan) -> str:
    command = [
        "quant-lab",
        "portfolio-run",
        "--portfolio",
        plan.portfolio_path,
        "--out",
        _display_path(Path(plan.output_dir) / "baseline"),
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


def build_portfolio_data_trust_command(metadata_path: str) -> str:
    return shlex.join(["quant-lab", "summarize-portfolio-data-trust", "--metadata", metadata_path])


def build_compare_portfolio_runs_command(metadata_paths: list[str]) -> str:
    command = ["quant-lab", "compare-portfolio-runs"]
    for metadata_path in metadata_paths:
        command.extend(["--metadata", metadata_path])
    return shlex.join(command)


def build_portfolio_summarize_command_from_plan(plan: PortfolioResearchPlan) -> str:
    return shlex.join(
        [
            "quant-lab",
            "summarize-portfolio-experiment",
            "--experiment-id",
            plan.experiment_id,
            "--experiments-path",
            plan.experiments_path,
            "--index-path",
            plan.index_path,
            "--out",
            _display_path(Path(plan.output_dir) / "portfolio_summary.md"),
        ]
    )


def build_portfolio_variants_command_from_plan(plan: PortfolioResearchPlan) -> str:
    portfolio = load_portfolio_spec(plan.portfolio_path)
    weights = ",".join(
        f"{symbol.symbol}={symbol.target_weight:.4g}" for symbol in portfolio.symbols
    )
    command = [
        "quant-lab",
        "portfolio-variants",
        "--portfolio",
        plan.portfolio_path,
        "--weights",
        weights,
        "--rebalance",
        "none",
        "--rebalance",
        "monthly",
        "--rebalance",
        "quarterly",
        "--out",
        _display_path(Path(plan.output_dir) / "portfolio_variants"),
    ]
    return shlex.join(command)


def build_portfolio_batch_plan_command_from_plan(plan: PortfolioResearchPlan) -> str:
    command = [
        "quant-lab",
        "portfolio-batch",
        "plan",
        "--portfolios",
        _display_path(_portfolio_batch_candidate_dir(plan)),
        "--out",
        _display_path(_portfolio_batch_dir(plan)),
        "--initial-cash",
        str(plan.initial_cash),
        "--cost-preset",
        plan.cost_preset,
        "--experiments-path",
        plan.experiments_path,
        "--index-path",
        plan.index_path,
    ]
    return shlex.join(command)


def build_portfolio_batch_run_command_from_plan(plan: PortfolioResearchPlan) -> str:
    return shlex.join(
        [
            "quant-lab",
            "portfolio-batch",
            "run",
            "--manifest",
            _display_path(_portfolio_batch_manifest_path(plan)),
            "--experiment-id",
            plan.experiment_id,
        ]
    )


def build_portfolio_batch_summarize_command_from_plan(plan: PortfolioResearchPlan) -> str:
    return shlex.join(
        [
            "quant-lab",
            "portfolio-batch",
            "summarize",
            "--manifest",
            _display_path(_portfolio_batch_manifest_path(plan)),
        ]
    )


def _portfolio_batch_candidate_dir(plan: PortfolioResearchPlan) -> Path:
    output_dir = Path(plan.output_dir)
    variants_dir = output_dir / "portfolio_variants"
    if variants_dir.exists():
        return variants_dir
    return output_dir / "portfolio_candidates"


def _portfolio_batch_dir(plan: PortfolioResearchPlan) -> Path:
    return Path(plan.output_dir) / "portfolio_batch"


def _portfolio_batch_manifest_path(plan: PortfolioResearchPlan) -> Path:
    return _portfolio_batch_dir(plan) / "portfolio_batch_manifest.json"


def _display_path(path: str | Path) -> str:
    """Return a stable command-string path without changing file IO behavior.

    `Path(...)` renders relative paths with backslashes on Windows. These
    helpers build copyable CLI recommendations, not paths we immediately open,
    so forward slashes keep repo-relative commands stable across Windows and
    Unix shells. Absolute paths keep the host platform's spelling because those
    often come from temp directories or user-provided Windows paths.
    """

    path_string = str(path)
    if Path(path).is_absolute():
        return path_string
    return path_string.replace("\\", "/")
