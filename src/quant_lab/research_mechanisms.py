"""Research-mechanism catalog loading and formatting.

Mechanisms sit one level above opportunity theses. They describe why a market
imperfection might exist before the lab decides whether a current backtest can
measure a reasonable proxy for it.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


MECHANISM_SCHEMA_VERSION = "research_mechanism.v1"
ALLOWED_SOURCE_TYPES = {"literature", "filing", "exchange_doc", "practitioner", "manual", "mixed"}
ALLOWED_ENGINE_FIT = {"ready", "proxy_only", "needs_data", "blocked"}
REQUIRED_MECHANISM_FIELDS = {
    "schema_version",
    "mechanism_id",
    "title",
    "source_type",
    "market_behavior",
    "forced_actor",
    "why_edge_might_exist",
    "why_large_capital_may_ignore_it",
    "capacity_hypothesis",
    "data_required",
    "observable_predictions",
    "falsification_tests",
    "engine_fit",
    "suggested_opportunity_theses",
    "references",
}


@dataclass(frozen=True)
class ResearchMechanism:
    path: Path
    payload: dict[str, Any]

    @property
    def mechanism_id(self) -> str:
        return str(self.payload["mechanism_id"])

    @property
    def title(self) -> str:
        return str(self.payload["title"])

    @property
    def source_type(self) -> str:
        return str(self.payload["source_type"])

    @property
    def engine_fit(self) -> str:
        return str(self.payload["engine_fit"])


def load_research_mechanisms(catalog_dir: str | Path) -> list[ResearchMechanism]:
    """Load strict research-mechanism records from a catalog directory."""

    root = Path(catalog_dir)
    if not root.exists():
        raise FileNotFoundError(f"Research mechanism catalog directory not found: {root}")

    mechanisms: list[ResearchMechanism] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_research_mechanism(payload, path)
        mechanisms.append(ResearchMechanism(path=path, payload=payload))

    if not mechanisms:
        raise ValueError(f"No research mechanism JSON files found in {root}")
    return mechanisms


def find_research_mechanism(
    mechanisms: list[ResearchMechanism],
    mechanism_id: str,
) -> ResearchMechanism | None:
    for mechanism in mechanisms:
        if mechanism.mechanism_id == mechanism_id:
            return mechanism
    return None


def validate_research_mechanism(payload: dict[str, Any], path: Path | None = None) -> None:
    label = str(path) if path is not None else "research mechanism"
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")

    missing = sorted(REQUIRED_MECHANISM_FIELDS.difference(payload))
    if missing:
        raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")
    unknown = sorted(set(payload) - REQUIRED_MECHANISM_FIELDS)
    if unknown:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")

    if payload["schema_version"] != MECHANISM_SCHEMA_VERSION:
        raise ValueError(f"{label} has unsupported schema_version: {payload['schema_version']}")
    if payload["source_type"] not in ALLOWED_SOURCE_TYPES:
        raise ValueError(f"{label} has unsupported source_type: {payload['source_type']}")
    if payload["engine_fit"] not in ALLOWED_ENGINE_FIT:
        raise ValueError(f"{label} has unsupported engine_fit: {payload['engine_fit']}")

    for field in (
        "mechanism_id",
        "title",
        "market_behavior",
        "forced_actor",
        "why_edge_might_exist",
        "why_large_capital_may_ignore_it",
        "capacity_hypothesis",
    ):
        _require_non_empty_text(payload[field], f"{label} {field}")

    for field in (
        "data_required",
        "observable_predictions",
        "falsification_tests",
        "suggested_opportunity_theses",
        "references",
    ):
        _require_non_empty_text_list(payload[field], f"{label} {field}")


def format_research_mechanism_list(mechanisms: list[ResearchMechanism]) -> str:
    lines = [
        "# Research Mechanisms",
        "",
        "Mechanisms are structured raw material for opportunity theses; they are not executable strategies.",
        "",
    ]
    for mechanism in mechanisms:
        lines.append(
            f"- `{mechanism.mechanism_id}`: {mechanism.title} "
            f"(engine_fit: `{mechanism.engine_fit}`, source_type: `{mechanism.source_type}`)"
        )
    return "\n".join(lines)


def format_research_mechanism_detail(mechanism: ResearchMechanism) -> str:
    payload = mechanism.payload
    return "\n".join(
        [
            f"# Research Mechanism: {mechanism.title}",
            "",
            f"- ID: `{mechanism.mechanism_id}`",
            f"- Source type: `{mechanism.source_type}`",
            f"- Engine fit: `{mechanism.engine_fit}`",
            f"- Path: `{mechanism.path}`",
            "",
            "## Market Behavior",
            "",
            str(payload["market_behavior"]),
            "",
            "## Forced Actor",
            "",
            str(payload["forced_actor"]),
            "",
            "## Why Edge Might Exist",
            "",
            str(payload["why_edge_might_exist"]),
            "",
            "## Why Large Capital May Ignore It",
            "",
            str(payload["why_large_capital_may_ignore_it"]),
            "",
            "## Capacity Hypothesis",
            "",
            str(payload["capacity_hypothesis"]),
            "",
            "## Data Required",
            "",
            *_bullet_lines(payload["data_required"]),
            "",
            "## Observable Predictions",
            "",
            *_bullet_lines(payload["observable_predictions"]),
            "",
            "## Falsification Tests",
            "",
            *_bullet_lines(payload["falsification_tests"]),
            "",
            "## Suggested Opportunity Theses",
            "",
            *_bullet_lines(payload["suggested_opportunity_theses"]),
            "",
            "## References",
            "",
            *_bullet_lines(payload["references"]),
            "",
        ]
    )


def format_research_mechanism_data_needs(
    mechanisms: list[ResearchMechanism],
    *,
    engine_fit: str | None = None,
) -> str:
    """Format a data-readiness view for deciding what raw material to pursue."""

    filtered = [
        mechanism
        for mechanism in mechanisms
        if engine_fit is None or mechanism.engine_fit == engine_fit
    ]
    lines = [
        "# Research Mechanism Data Needs",
        "",
        "Use this view to decide which datasets would unlock better opportunity theses.",
        "",
    ]
    if engine_fit is not None:
        lines.append(f"Filter: engine_fit = `{engine_fit}`")
        lines.append("")
    if not filtered:
        lines.append("- none")
        return "\n".join(lines)

    for mechanism in filtered:
        payload = mechanism.payload
        lines.extend(
            [
                f"## {mechanism.title}",
                "",
                f"- ID: `{mechanism.mechanism_id}`",
                f"- Engine fit: `{mechanism.engine_fit}`",
                f"- Source type: `{mechanism.source_type}`",
                "- Data required:",
                *_indented_bullet_lines(payload["data_required"]),
                "- Suggested opportunity theses:",
                *_indented_bullet_lines(payload["suggested_opportunity_theses"]),
                "- First falsification checks:",
                *_indented_bullet_lines(payload["falsification_tests"][:2]),
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


def _indented_bullet_lines(items: list[Any]) -> list[str]:
    return [f"  - {item}" for item in items] if items else ["  - none"]
