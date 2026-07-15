"""Local experiment registry for research hypotheses and decisions."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


EXPERIMENT_SCHEMA_VERSION = "experiment.v1"
EXPERIMENT_ID_PATTERN = re.compile(r"^EXP-\d{3,}$")
EXPERIMENT_STATUSES = ("planned", "running", "completed", "archived")
EXPERIMENT_DECISION_OUTCOMES = ("accept", "reject", "continue")


@dataclass(frozen=True)
class ExperimentDecision:
    """Structured decision made after reviewing linked experiment evidence."""

    outcome: str
    decided_at_utc: str
    rationale: str
    supporting_run: str | None = None
    contradicting_run: str | None = None
    next_action: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentRecord:
    """One research hypothesis tracked across future runs and decisions."""

    experiment_schema_version: str
    experiment_id: str
    created_at_utc: str
    title: str
    hypothesis: str
    status: str = "planned"
    tags: list[str] = field(default_factory=list)
    strategy_path: str | None = None
    data_path: str | None = None
    linked_runs: list[str] = field(default_factory=list)
    decision: str | None = None
    decision_record: ExperimentDecision | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def create_experiment_record(
    *,
    experiment_id: str,
    title: str,
    hypothesis: str,
    status: str = "planned",
    tags: Iterable[str] | None = None,
    strategy_path: str | None = None,
    data_path: str | None = None,
    notes: str | None = None,
    created_at_utc: str | None = None,
) -> ExperimentRecord:
    normalized_tags = normalize_tags(tags or [])
    record = ExperimentRecord(
        experiment_schema_version=EXPERIMENT_SCHEMA_VERSION,
        experiment_id=experiment_id,
        created_at_utc=created_at_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        title=title.strip(),
        hypothesis=hypothesis.strip(),
        status=status,
        tags=normalized_tags,
        strategy_path=strategy_path,
        data_path=data_path,
        linked_runs=[],
        decision=None,
        decision_record=None,
        notes=notes.strip() if notes is not None else None,
    )
    validate_experiment_record(record)
    return record


def normalize_tags(tags: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for raw_tag in tags:
        for tag in str(raw_tag).split(","):
            cleaned = tag.strip().lower()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
    return normalized


def next_experiment_id(records: Iterable[ExperimentRecord]) -> str:
    highest = 0
    for record in records:
        if not EXPERIMENT_ID_PATTERN.match(record.experiment_id):
            continue
        highest = max(highest, int(record.experiment_id.split("-", 1)[1]))
    return f"EXP-{highest + 1:03d}"


def append_experiment_record(record: ExperimentRecord, registry_path: str | Path) -> str:
    destination = Path(registry_path)
    existing = load_experiments(destination)
    if any(existing_record.experiment_id == record.experiment_id for existing_record in existing):
        raise ValueError(f"experiment already exists: {record.experiment_id}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    return str(destination)


def update_experiment_record(
    record: ExperimentRecord,
    *,
    status: str | None = None,
    decision: str | None = None,
    notes: str | None = None,
    add_tags: Iterable[str] | None = None,
) -> ExperimentRecord:
    merged_tags = record.tags
    if add_tags:
        merged_tags = normalize_tags([*record.tags, *add_tags])

    updated = replace(
        record,
        status=status if status is not None else record.status,
        decision=decision.strip() if decision is not None else record.decision,
        notes=notes.strip() if notes is not None else record.notes,
        tags=merged_tags,
    )
    validate_experiment_record(updated)
    return updated


def create_experiment_decision(
    *,
    outcome: str,
    rationale: str,
    supporting_run: str | None = None,
    contradicting_run: str | None = None,
    next_action: str | None = None,
    decided_at_utc: str | None = None,
) -> ExperimentDecision:
    decision = ExperimentDecision(
        outcome=outcome,
        decided_at_utc=decided_at_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        rationale=rationale.strip(),
        supporting_run=_optional_str(supporting_run),
        contradicting_run=_optional_str(contradicting_run),
        next_action=_optional_str(next_action),
    )
    validate_experiment_decision(decision)
    return decision


def decide_experiment_record(
    record: ExperimentRecord,
    decision_record: ExperimentDecision,
    *,
    add_tags: Iterable[str] | None = None,
) -> ExperimentRecord:
    status = "running" if decision_record.outcome == "continue" else "completed"
    merged_tags = normalize_tags([*record.tags, *(add_tags or [])])
    updated = replace(
        record,
        status=status,
        decision=f"{decision_record.outcome}: {decision_record.rationale}",
        decision_record=decision_record,
        tags=merged_tags,
    )
    validate_experiment_record(updated)
    return updated


def link_runs_to_experiment(record: ExperimentRecord, metadata_paths: Iterable[str]) -> ExperimentRecord:
    linked_runs = list(record.linked_runs)
    for metadata_path in metadata_paths:
        normalized_path = str(metadata_path).strip()
        if not normalized_path:
            raise ValueError("linked run metadata path must not be empty")
        if normalized_path not in linked_runs:
            linked_runs.append(normalized_path)

    updated = replace(record, linked_runs=linked_runs)
    validate_experiment_record(updated)
    return updated


def require_experiment(registry_path: str | Path, experiment_id: str | None) -> ExperimentRecord | None:
    """Return the experiment when a command explicitly links work to one.

    Runs can take a while once the lab has real data and broad parameter
    sweeps. Checking the registry before the run starts gives a fast, clear
    error for a mistyped experiment id instead of failing after artifacts have
    already been written.
    """

    if experiment_id is None:
        return None
    return find_experiment(load_experiments(registry_path), experiment_id)


def link_run_metadata_path(
    *,
    registry_path: str | Path | None,
    experiment_id: str | None,
    metadata_path: str | Path,
) -> str | None:
    """Attach one generated run metadata file to an experiment registry record."""

    if experiment_id is None:
        return None
    if registry_path is None:
        raise ValueError("--experiments-path is required when --experiment-id is provided")

    record = require_experiment(registry_path, experiment_id)
    if record is None:
        return None
    updated = link_runs_to_experiment(record, [str(metadata_path)])
    return replace_experiment_record(updated, registry_path)


def replace_experiment_record(updated_record: ExperimentRecord, registry_path: str | Path) -> str:
    destination = Path(registry_path)
    records = load_experiments(destination)
    replaced = False
    next_records: list[ExperimentRecord] = []
    for record in records:
        if record.experiment_id == updated_record.experiment_id:
            next_records.append(updated_record)
            replaced = True
        else:
            next_records.append(record)
    if not replaced:
        raise ValueError(f"experiment not found: {updated_record.experiment_id}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(json.dumps(record.to_dict(), sort_keys=True) + "\n" for record in next_records),
        encoding="utf-8",
    )
    return str(destination)


def load_experiments(registry_path: str | Path) -> list[ExperimentRecord]:
    path = Path(registry_path)
    if not path.exists():
        return []

    records: list[ExperimentRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in experiment registry {path} on line {line_number}") from exc
        records.append(experiment_from_dict(payload, path=path, line_number=line_number))
    return records


def experiment_from_dict(payload: dict, *, path: Path | None = None, line_number: int | None = None) -> ExperimentRecord:
    required_fields = {
        "experiment_schema_version",
        "experiment_id",
        "created_at_utc",
        "title",
        "hypothesis",
        "status",
        "tags",
        "strategy_path",
        "data_path",
        "linked_runs",
        "decision",
        "notes",
    }
    optional_fields = {"decision_record"}
    allowed_fields = required_fields | optional_fields
    extra_fields = set(payload) - allowed_fields
    missing_fields = required_fields - set(payload)
    location = f" in {path} on line {line_number}" if path is not None and line_number is not None else ""
    if missing_fields:
        raise ValueError(f"Experiment record missing fields{location}: {sorted(missing_fields)}")
    if extra_fields:
        raise ValueError(f"Experiment record has unknown fields{location}: {sorted(extra_fields)}")

    normalized_payload = dict(payload)
    normalized_payload.setdefault("decision_record", None)
    if normalized_payload["decision_record"] is not None:
        normalized_payload["decision_record"] = experiment_decision_from_dict(normalized_payload["decision_record"])

    record = ExperimentRecord(**normalized_payload)
    validate_experiment_record(record)
    return record


def experiment_decision_from_dict(payload: dict) -> ExperimentDecision:
    if not isinstance(payload, dict):
        raise ValueError("Experiment decision must be an object or null")

    required_fields = {
        "outcome",
        "decided_at_utc",
        "rationale",
        "supporting_run",
        "contradicting_run",
        "next_action",
    }
    extra_fields = set(payload) - required_fields
    missing_fields = required_fields - set(payload)
    if missing_fields:
        raise ValueError(f"Experiment decision missing fields: {sorted(missing_fields)}")
    if extra_fields:
        raise ValueError(f"Experiment decision has unknown fields: {sorted(extra_fields)}")

    decision = ExperimentDecision(**payload)
    validate_experiment_decision(decision)
    return decision


def validate_experiment_record(record: ExperimentRecord) -> None:
    if record.experiment_schema_version != EXPERIMENT_SCHEMA_VERSION:
        raise ValueError(f"unsupported experiment schema: {record.experiment_schema_version}")
    if not EXPERIMENT_ID_PATTERN.match(record.experiment_id):
        raise ValueError(f"invalid experiment id: {record.experiment_id}")
    if not record.title.strip():
        raise ValueError("experiment title must not be empty")
    if not record.hypothesis.strip():
        raise ValueError("experiment hypothesis must not be empty")
    if record.status not in EXPERIMENT_STATUSES:
        raise ValueError(f"invalid experiment status: {record.status}")
    if not isinstance(record.tags, list) or any(not isinstance(tag, str) for tag in record.tags):
        raise ValueError("experiment tags must be a list of strings")
    if not isinstance(record.linked_runs, list) or any(not isinstance(run, str) for run in record.linked_runs):
        raise ValueError("experiment linked_runs must be a list of strings")
    if record.decision is not None and not isinstance(record.decision, str):
        raise ValueError("experiment decision must be a string or null")
    if record.decision_record is not None:
        validate_experiment_decision(record.decision_record)
    if record.notes is not None and not isinstance(record.notes, str):
        raise ValueError("experiment notes must be a string or null")


def validate_experiment_decision(decision: ExperimentDecision) -> None:
    if not isinstance(decision, ExperimentDecision):
        raise ValueError("experiment decision_record must be an ExperimentDecision or null")
    if decision.outcome not in EXPERIMENT_DECISION_OUTCOMES:
        raise ValueError(f"invalid experiment decision outcome: {decision.outcome}")
    if not decision.decided_at_utc.strip():
        raise ValueError("experiment decision decided_at_utc must not be empty")
    if not decision.rationale.strip():
        raise ValueError("experiment decision rationale must not be empty")
    for field_name in ("supporting_run", "contradicting_run", "next_action"):
        value = getattr(decision, field_name)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"experiment decision {field_name} must be a string or null")


def find_experiment(records: Iterable[ExperimentRecord], experiment_id: str) -> ExperimentRecord:
    for record in records:
        if record.experiment_id == experiment_id:
            return record
    raise ValueError(f"experiment not found: {experiment_id}")


def filter_experiments(
    records: Iterable[ExperimentRecord],
    *,
    status: str | None = None,
    tag: str | None = None,
) -> list[ExperimentRecord]:
    filtered = list(records)
    if status is not None:
        filtered = [record for record in filtered if record.status == status]
    if tag is not None:
        requested_tag = tag.strip().lower()
        filtered = [record for record in filtered if requested_tag in record.tags]
    return filtered


EXPERIMENT_TABLE_COLUMNS = [
    ("id", "experiment_id"),
    ("status", "status"),
    ("created", "created_at_utc"),
    ("title", "title"),
    ("tags", "tags"),
]


def format_experiment_table(records: list[ExperimentRecord]) -> str:
    table_rows = [
        [_format_experiment_value(record, field) for _, field in EXPERIMENT_TABLE_COLUMNS]
        for record in records
    ]
    header = [label for label, _ in EXPERIMENT_TABLE_COLUMNS]
    widths = [
        max(len(header[index]), *[len(row[index]) for row in table_rows]) if table_rows else len(header[index])
        for index in range(len(header))
    ]
    lines = [
        "  ".join(header[index].ljust(widths[index]) for index in range(len(header))),
        "  ".join("-" * widths[index] for index in range(len(header))),
    ]
    for row in table_rows:
        lines.append("  ".join(row[index].ljust(widths[index]) for index in range(len(row))))
    return "\n".join(lines)


def format_experiment_csv(records: list[ExperimentRecord]) -> str:
    output = io.StringIO()
    fieldnames = [label for label, _ in EXPERIMENT_TABLE_COLUMNS]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                label: _format_experiment_value(record, field)
                for label, field in EXPERIMENT_TABLE_COLUMNS
            }
        )
    return output.getvalue().rstrip("\n")


def format_experiment_detail(record: ExperimentRecord) -> str:
    linked_runs = record.linked_runs or ["-"]
    lines = [
        "Experiment",
        "==========",
        "",
        f"ID: {record.experiment_id}",
        f"Status: {record.status}",
        f"Created UTC: {record.created_at_utc}",
        f"Title: {record.title}",
        f"Tags: {', '.join(record.tags) if record.tags else '-'}",
        "",
        "Hypothesis",
        record.hypothesis,
        "",
        "Inputs",
        f"  Strategy: {record.strategy_path or '-'}",
        f"  Data: {record.data_path or '-'}",
        "",
        "Linked Runs",
        *[f"  {run}" for run in linked_runs],
        "",
        "Decision",
        *_format_decision_lines(record),
        "",
        "Notes",
        record.notes or "-",
    ]
    return "\n".join(lines)


def _format_decision_lines(record: ExperimentRecord) -> list[str]:
    if record.decision_record is None:
        return [record.decision or "-"]

    decision = record.decision_record
    return [
        f"  Outcome: {decision.outcome}",
        f"  Decided UTC: {decision.decided_at_utc}",
        f"  Rationale: {decision.rationale}",
        f"  Supporting Run: {decision.supporting_run or '-'}",
        f"  Contradicting Run: {decision.contradicting_run or '-'}",
        f"  Next Action: {decision.next_action or '-'}",
    ]


def _format_experiment_value(record: ExperimentRecord, field: str) -> str:
    value = getattr(record, field)
    if field == "created_at_utc":
        return str(value).replace("T", " ")[:19]
    if field == "tags":
        return ",".join(record.tags) if record.tags else "-"
    if value is None:
        return "-"
    return str(value)


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
