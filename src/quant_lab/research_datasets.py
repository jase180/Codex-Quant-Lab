"""Dataset-plan catalog for mechanism-driven research.

Dataset plans turn a broad mechanism data need into a concrete acquisition or
curation target. They still do not provide market data; they define what would
make a future dataset honest enough to use.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


DATASET_PLAN_SCHEMA_VERSION = "research_dataset_plan.v1"
ALLOWED_DATASET_STATUSES = {"planned", "available", "blocked"}
REQUIRED_DATASET_PLAN_FIELDS = {
    "schema_version",
    "dataset_id",
    "mechanism_id",
    "title",
    "status",
    "purpose",
    "data_grain",
    "required_fields",
    "candidate_sources",
    "construction_rules",
    "quality_checks",
    "minimum_viable_tests",
    "known_limitations",
    "next_action",
}


@dataclass(frozen=True)
class ResearchDatasetPlan:
    path: Path
    payload: dict[str, Any]

    @property
    def dataset_id(self) -> str:
        return str(self.payload["dataset_id"])

    @property
    def mechanism_id(self) -> str:
        return str(self.payload["mechanism_id"])

    @property
    def title(self) -> str:
        return str(self.payload["title"])

    @property
    def status(self) -> str:
        return str(self.payload["status"])


def load_research_dataset_plans(catalog_dir: str | Path) -> list[ResearchDatasetPlan]:
    root = Path(catalog_dir)
    if not root.exists():
        raise FileNotFoundError(f"Research dataset plan directory not found: {root}")

    plans: list[ResearchDatasetPlan] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_research_dataset_plan(payload, path)
        plans.append(ResearchDatasetPlan(path=path, payload=payload))

    if not plans:
        raise ValueError(f"No research dataset plan JSON files found in {root}")
    return plans


def dataset_plans_for_mechanism(
    plans: list[ResearchDatasetPlan],
    mechanism_id: str,
) -> list[ResearchDatasetPlan]:
    return [plan for plan in plans if plan.mechanism_id == mechanism_id]


def validate_research_dataset_plan(payload: dict[str, Any], path: Path | None = None) -> None:
    label = str(path) if path is not None else "research dataset plan"
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    missing = sorted(REQUIRED_DATASET_PLAN_FIELDS.difference(payload))
    if missing:
        raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")
    unknown = sorted(set(payload) - REQUIRED_DATASET_PLAN_FIELDS)
    if unknown:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")

    if payload["schema_version"] != DATASET_PLAN_SCHEMA_VERSION:
        raise ValueError(f"{label} has unsupported schema_version: {payload['schema_version']}")
    if payload["status"] not in ALLOWED_DATASET_STATUSES:
        raise ValueError(f"{label} has unsupported status: {payload['status']}")

    for field in ("dataset_id", "mechanism_id", "title", "purpose", "data_grain", "next_action"):
        _require_non_empty_text(payload[field], f"{label} {field}")
    for field in (
        "required_fields",
        "candidate_sources",
        "construction_rules",
        "quality_checks",
        "minimum_viable_tests",
        "known_limitations",
    ):
        _require_non_empty_text_list(payload[field], f"{label} {field}")


def format_dataset_plan_list(plans: list[ResearchDatasetPlan]) -> str:
    lines = [
        "# Research Dataset Plans",
        "",
        "Dataset plans define raw-material requirements before a mechanism can be tested honestly.",
        "",
    ]
    for plan in plans:
        lines.append(
            f"- `{plan.dataset_id}`: {plan.title} "
            f"(mechanism: `{plan.mechanism_id}`, status: `{plan.status}`)"
        )
    return "\n".join(lines)


def format_dataset_plans_for_mechanism(mechanism_id: str, plans: list[ResearchDatasetPlan]) -> str:
    lines = [
        f"# Dataset Plans For Mechanism: {mechanism_id}",
        "",
    ]
    if not plans:
        lines.append("- none")
        return "\n".join(lines)

    for plan in plans:
        payload = plan.payload
        lines.extend(
            [
                f"## {plan.title}",
                "",
                f"- Dataset ID: `{plan.dataset_id}`",
                f"- Status: `{plan.status}`",
                f"- Data grain: `{payload['data_grain']}`",
                f"- Path: `{plan.path}`",
                "",
                "Purpose:",
                "",
                str(payload["purpose"]),
                "",
                "Required fields:",
                *_bullet_lines(payload["required_fields"]),
                "",
                "Candidate sources:",
                *_bullet_lines(payload["candidate_sources"]),
                "",
                "Construction rules:",
                *_bullet_lines(payload["construction_rules"]),
                "",
                "Quality checks:",
                *_bullet_lines(payload["quality_checks"]),
                "",
                "Minimum viable tests:",
                *_bullet_lines(payload["minimum_viable_tests"]),
                "",
                "Known limitations:",
                *_bullet_lines(payload["known_limitations"]),
                "",
                f"Next action: {payload['next_action']}",
                "",
            ]
        )
    return "\n".join(lines)


def _require_non_empty_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _require_non_empty_text_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list")
    return [_require_non_empty_text(item, label) for item in value]


def _bullet_lines(items: list[Any]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- none"]
