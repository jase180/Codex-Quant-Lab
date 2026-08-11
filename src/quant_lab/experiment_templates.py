"""Experiment-template and parameter-neighborhood catalog loading.

These catalogs sit between opportunity theses and executable strategy JSON.
They describe bounded experiment families and small prespecified parameter
sets, so a future campaign candidate generator can create valid choices without
asking a model to invent strategy details from scratch.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .campaign_templates import supported_campaign_template_parameters


EXPERIMENT_TEMPLATE_SCHEMA_VERSION = "experiment_template.v1"
PARAMETER_NEIGHBORHOOD_SCHEMA_VERSION = "parameter_neighborhood.v1"
ALLOWED_INFORMATION_GAIN = {"low", "medium", "high"}
ALLOWED_MINING_RISK = {"low", "medium", "high"}
ALLOWED_ENGINE_SUPPORT = {"ready", "blocked"}
REQUIRED_TEMPLATE_FIELDS = {
    "schema_version",
    "template_id",
    "title",
    "strategy_family",
    "rationale",
    "tests_claim",
    "supported_universe",
    "required_project_capabilities",
    "executable_mapping",
    "default_validation_plan",
    "default_success_criteria",
    "parameter_neighborhood_id",
    "expected_information_gain",
    "parameter_mining_risk",
    "known_limitations",
    "engine_support_status",
}
REQUIRED_MAPPING_FIELDS = {"campaign_strategy_template", "parameter_map"}
REQUIRED_NEIGHBORHOOD_FIELDS = {
    "schema_version",
    "neighborhood_id",
    "title",
    "rationale",
    "parameters",
    "max_variants",
    "selection_rule",
}


@dataclass(frozen=True)
class ExperimentTemplate:
    path: Path
    payload: dict[str, Any]

    @property
    def template_id(self) -> str:
        return str(self.payload["template_id"])

    @property
    def strategy_family(self) -> str:
        return str(self.payload["strategy_family"])

    @property
    def campaign_strategy_template(self) -> str:
        mapping = _mapping(self.payload["executable_mapping"], "executable_mapping")
        return str(mapping["campaign_strategy_template"])

    @property
    def parameter_neighborhood_id(self) -> str:
        return str(self.payload["parameter_neighborhood_id"])

    @property
    def engine_support_status(self) -> str:
        return str(self.payload["engine_support_status"])


@dataclass(frozen=True)
class ParameterNeighborhood:
    path: Path
    payload: dict[str, Any]

    @property
    def neighborhood_id(self) -> str:
        return str(self.payload["neighborhood_id"])

    @property
    def parameters(self) -> dict[str, list[Any]]:
        return {str(key): list(value) for key, value in self.payload["parameters"].items()}

    @property
    def max_variants(self) -> int:
        return int(self.payload["max_variants"])


def load_experiment_template_catalog(catalog_dir: str | Path) -> list[ExperimentTemplate]:
    """Load strict experiment-template catalog entries from JSON files."""

    root = Path(catalog_dir)
    if not root.exists():
        raise FileNotFoundError(f"Experiment template catalog directory not found: {root}")

    templates: list[ExperimentTemplate] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_experiment_template(payload, path)
        templates.append(ExperimentTemplate(path=path, payload=payload))

    if not templates:
        raise ValueError(f"No experiment template JSON files found in {root}")
    return templates


def load_parameter_neighborhood_catalog(catalog_dir: str | Path) -> list[ParameterNeighborhood]:
    """Load strict parameter-neighborhood catalog entries from JSON files."""

    root = Path(catalog_dir)
    if not root.exists():
        raise FileNotFoundError(f"Parameter neighborhood catalog directory not found: {root}")

    neighborhoods: list[ParameterNeighborhood] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_parameter_neighborhood(payload, path)
        neighborhoods.append(ParameterNeighborhood(path=path, payload=payload))

    if not neighborhoods:
        raise ValueError(f"No parameter neighborhood JSON files found in {root}")
    return neighborhoods


def validate_experiment_template(payload: dict[str, Any], path: Path | None = None) -> None:
    label = str(path) if path is not None else "experiment template"
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    _require_exact_fields(payload, REQUIRED_TEMPLATE_FIELDS, label)
    if payload["schema_version"] != EXPERIMENT_TEMPLATE_SCHEMA_VERSION:
        raise ValueError(f"{label} has unsupported schema_version: {payload['schema_version']}")

    for field in (
        "template_id",
        "title",
        "strategy_family",
        "rationale",
        "tests_claim",
        "parameter_neighborhood_id",
    ):
        _require_non_empty_text(payload[field], f"{label} {field}")
    for field in ("supported_universe", "required_project_capabilities", "known_limitations"):
        _require_non_empty_text_list(payload[field], f"{label} {field}")
    _require_bool_map(payload["default_validation_plan"], f"{label} default_validation_plan")
    _require_number_map(payload["default_success_criteria"], f"{label} default_success_criteria")

    if payload["expected_information_gain"] not in ALLOWED_INFORMATION_GAIN:
        raise ValueError(f"{label} has unsupported expected_information_gain: {payload['expected_information_gain']}")
    if payload["parameter_mining_risk"] not in ALLOWED_MINING_RISK:
        raise ValueError(f"{label} has unsupported parameter_mining_risk: {payload['parameter_mining_risk']}")
    if payload["engine_support_status"] not in ALLOWED_ENGINE_SUPPORT:
        raise ValueError(f"{label} has unsupported engine_support_status: {payload['engine_support_status']}")

    mapping = _mapping(payload["executable_mapping"], f"{label} executable_mapping")
    _require_exact_fields(mapping, REQUIRED_MAPPING_FIELDS, f"{label} executable_mapping")
    campaign_template = _require_non_empty_text(
        mapping["campaign_strategy_template"],
        f"{label} executable_mapping.campaign_strategy_template",
    )
    parameter_map = _mapping(mapping["parameter_map"], f"{label} executable_mapping.parameter_map")
    supported_parameters = supported_campaign_template_parameters(campaign_template)
    unsupported = sorted(set(parameter_map.values()) - supported_parameters)
    if unsupported:
        raise ValueError(
            f"{label} executable_mapping.parameter_map references unsupported campaign parameters: {unsupported}"
        )


def validate_parameter_neighborhood(payload: dict[str, Any], path: Path | None = None) -> None:
    label = str(path) if path is not None else "parameter neighborhood"
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    _require_exact_fields(payload, REQUIRED_NEIGHBORHOOD_FIELDS, label)
    if payload["schema_version"] != PARAMETER_NEIGHBORHOOD_SCHEMA_VERSION:
        raise ValueError(f"{label} has unsupported schema_version: {payload['schema_version']}")

    for field in ("neighborhood_id", "title", "rationale", "selection_rule"):
        _require_non_empty_text(payload[field], f"{label} {field}")
    parameters = _mapping(payload["parameters"], f"{label} parameters")
    if not parameters:
        raise ValueError(f"{label} parameters must not be empty")
    for key, values in parameters.items():
        _require_non_empty_text(str(key), f"{label} parameter name")
        if not isinstance(values, list) or not values:
            raise ValueError(f"{label} parameter {key} must be a non-empty list")
    if not isinstance(payload["max_variants"], int) or isinstance(payload["max_variants"], bool):
        raise ValueError(f"{label} max_variants must be an integer")
    if payload["max_variants"] <= 0:
        raise ValueError(f"{label} max_variants must be positive")


def find_parameter_neighborhood(
    neighborhoods: list[ParameterNeighborhood],
    neighborhood_id: str,
) -> ParameterNeighborhood | None:
    for neighborhood in neighborhoods:
        if neighborhood.neighborhood_id == neighborhood_id:
            return neighborhood
    return None


def _require_exact_fields(payload: dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")
    unknown = sorted(set(payload) - required)
    if unknown:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")


def _require_non_empty_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _require_non_empty_text_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list")
    cleaned = [_require_non_empty_text(item, label) for item in value]
    return cleaned


def _require_bool_map(value: object, label: str) -> dict[str, bool]:
    mapping = _mapping(value, label)
    if not mapping:
        raise ValueError(f"{label} must not be empty")
    for key, item in mapping.items():
        _require_non_empty_text(str(key), f"{label} key")
        if not isinstance(item, bool):
            raise ValueError(f"{label}.{key} must be a boolean")
    return {str(key): bool(item) for key, item in mapping.items()}


def _require_number_map(value: object, label: str) -> dict[str, float]:
    mapping = _mapping(value, label)
    if not mapping:
        raise ValueError(f"{label} must not be empty")
    for key, item in mapping.items():
        _require_non_empty_text(str(key), f"{label} key")
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise ValueError(f"{label}.{key} must be a number")
    return {str(key): float(item) for key, item in mapping.items()}


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return dict(value)
