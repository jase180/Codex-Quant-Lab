"""Canonical experiment conclusion model and deterministic formatter."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Sequence

from .evidence_labels import VALIDATION_RUN_TYPES, label_strategy_evidence
from .research_registry import ExperimentRecord


EXPERIMENT_CONCLUSION_SCHEMA_VERSION = "experiment_conclusion.v1"
CONCLUSION_GENERATOR_NAME = "quant-lab conclude-experiment"
AGENT_INSTRUCTIONS = [
    "Read experiment_conclusion.json before scanning raw artifacts.",
    "Treat current_conclusion as provisional, not market truth.",
    "Respect do_not_repeat unless the hypothesis changes.",
    "Propose small falsifiable next tests, not broad optimization.",
    "Cite source_artifacts when making claims.",
    "Preserve no-lookahead and next-open-fill assumptions.",
]
ROBUSTNESS_RUN_TYPES = {
    "cost_sensitivity": "cost_sensitivity_run",
    "date_sensitivity": "date_sensitivity_run",
    "benchmark_sensitivity": "benchmark_sensitivity_run",
}
MARKDOWN_SECTION_ORDER = [
    "## Current Conclusion",
    "## Confidence",
    "## What Was Tested",
    "## What Supports This",
    "## What Contradicts This",
    "## Robustness Status",
    "## Do Not Repeat",
    "## Next Useful Tests",
    "## Open Questions",
    "## Source Artifacts",
    "## Agent Instructions",
]


@dataclass(frozen=True)
class ConclusionGenerator:
    name: str
    mode: str
    version: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ConclusionExperimentSnapshot:
    title: str
    hypothesis: str
    status: str
    tags: list[str]
    strategy_path: str | None
    data_path: str | None

    def to_dict(self) -> dict[str, str | list[str] | None]:
        return asdict(self)


@dataclass(frozen=True)
class ConclusionEvidenceItem:
    label: str
    run_id: str | None
    run_type: str
    metric: str
    value: float | None
    artifact_path: str | None
    note: str

    def to_dict(self) -> dict[str, str | float | None]:
        return asdict(self)


@dataclass(frozen=True)
class RobustnessConclusionNote:
    check: str
    status: str
    artifact_path: str | None
    summary: str

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class NextUsefulTest:
    test: str
    reason: str
    success_criteria: str
    suggested_command: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class SourceArtifact:
    kind: str
    path: str
    role: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentConclusion:
    schema_version: str
    experiment_id: str
    generated_at_utc: str
    generator: ConclusionGenerator
    experiment: ConclusionExperimentSnapshot
    confidence_label: str
    current_conclusion: str
    supporting_evidence: list[ConclusionEvidenceItem]
    contradicting_evidence: list[ConclusionEvidenceItem]
    robustness_notes: list[RobustnessConclusionNote]
    do_not_repeat: list[str]
    next_useful_tests: list[NextUsefulTest]
    open_questions: list[str]
    source_artifacts: list[SourceArtifact]
    agent_instructions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "generated_at_utc": self.generated_at_utc,
            "generator": self.generator.to_dict(),
            "experiment": self.experiment.to_dict(),
            "confidence_label": self.confidence_label,
            "current_conclusion": self.current_conclusion,
            "supporting_evidence": [item.to_dict() for item in self.supporting_evidence],
            "contradicting_evidence": [item.to_dict() for item in self.contradicting_evidence],
            "robustness_notes": [item.to_dict() for item in self.robustness_notes],
            "do_not_repeat": list(self.do_not_repeat),
            "next_useful_tests": [item.to_dict() for item in self.next_useful_tests],
            "open_questions": list(self.open_questions),
            "source_artifacts": [item.to_dict() for item in self.source_artifacts],
            "agent_instructions": list(self.agent_instructions),
        }


def build_experiment_conclusion(
    experiment: ExperimentRecord,
    index_records: Sequence[dict],
    *,
    generated_at_utc: str | None = None,
    generator_version: str = "unknown",
) -> ExperimentConclusion:
    """Build a deterministic conclusion draft from linked experiment evidence."""

    linked_records = _linked_index_records(experiment, list(index_records))
    linked_records.sort(key=lambda record: str(record.get("created_at_utc", "")), reverse=True)
    evidence_label = label_strategy_evidence(linked_records)
    robustness_notes = _robustness_notes(linked_records)
    supporting_evidence = _evidence_items(
        _supporting_evidence_records(linked_records),
        default_label="Positive linked evidence",
        default_note="This linked run beat the benchmark on excess return.",
    )
    contradicting_evidence = _evidence_items(
        _contradicting_evidence_records(linked_records),
        default_label="Contradicting linked evidence",
        default_note="This linked run did not beat the benchmark on excess return.",
    )

    return ExperimentConclusion(
        schema_version=EXPERIMENT_CONCLUSION_SCHEMA_VERSION,
        experiment_id=experiment.experiment_id,
        generated_at_utc=generated_at_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        generator=ConclusionGenerator(
            name=CONCLUSION_GENERATOR_NAME,
            mode="deterministic",
            version=generator_version,
        ),
        experiment=ConclusionExperimentSnapshot(
            title=experiment.title,
            hypothesis=experiment.hypothesis,
            status=experiment.status,
            tags=list(experiment.tags),
            strategy_path=experiment.strategy_path,
            data_path=experiment.data_path,
        ),
        confidence_label=evidence_label.label,
        current_conclusion=_current_conclusion(experiment, evidence_label.label, linked_records, robustness_notes),
        supporting_evidence=supporting_evidence,
        contradicting_evidence=contradicting_evidence,
        robustness_notes=robustness_notes,
        do_not_repeat=_do_not_repeat(evidence_label.label, linked_records, robustness_notes),
        next_useful_tests=_next_useful_tests(evidence_label.label, linked_records, robustness_notes),
        open_questions=_open_questions(evidence_label.label, linked_records, robustness_notes),
        source_artifacts=_source_artifacts(experiment, linked_records),
        agent_instructions=list(AGENT_INSTRUCTIONS),
    )


def format_experiment_conclusion_markdown(conclusion: ExperimentConclusion) -> str:
    """Render the human-first conclusion document."""

    lines = [
        f"# Experiment Conclusion: {conclusion.experiment_id}",
        "",
        "## Current Conclusion",
        "",
        conclusion.current_conclusion,
        "",
        "## Confidence",
        "",
        f"- Label: `{conclusion.confidence_label}`",
        f"- Generated UTC: `{conclusion.generated_at_utc}`",
        f"- Generator: `{conclusion.generator.name}` (`{conclusion.generator.mode}`)",
        "",
        "## What Was Tested",
        "",
        f"- Title: {conclusion.experiment.title}",
        f"- Hypothesis: {conclusion.experiment.hypothesis}",
        f"- Status: `{conclusion.experiment.status}`",
        f"- Strategy path: `{conclusion.experiment.strategy_path or '-'}`",
        f"- Data path: `{conclusion.experiment.data_path or '-'}`",
        "",
        "## What Supports This",
        "",
        *_evidence_markdown(conclusion.supporting_evidence),
        "",
        "## What Contradicts This",
        "",
        *_evidence_markdown(conclusion.contradicting_evidence),
        "",
        "## Robustness Status",
        "",
        *_robustness_markdown(conclusion.robustness_notes),
        "",
        "## Do Not Repeat",
        "",
        *_bullet_lines(conclusion.do_not_repeat),
        "",
        "## Next Useful Tests",
        "",
        *_next_test_markdown(conclusion.next_useful_tests),
        "",
        "## Open Questions",
        "",
        *_bullet_lines(conclusion.open_questions),
        "",
        "## Source Artifacts",
        "",
        *_source_artifact_markdown(conclusion.source_artifacts),
        "",
        "## Agent Instructions",
        "",
        *_bullet_lines(conclusion.agent_instructions),
        "",
    ]
    return "\n".join(lines)


def format_agent_context(conclusion: ExperimentConclusion) -> str:
    return "\n".join(
        [
            "# Agent Context",
            "",
            "Read first:",
            "- `experiment_conclusion.json`",
            "- `experiment_conclusion.md`",
            "",
            "Current conclusion:",
            f"- {conclusion.current_conclusion}",
            "",
            "Rules:",
            *_bullet_lines(conclusion.agent_instructions),
            "",
        ]
    )


def _linked_index_records(experiment: ExperimentRecord, index_records: list[dict]) -> list[dict]:
    linked_metadata_paths = set(experiment.linked_runs)
    linked_records: list[dict] = []
    seen_keys: set[str] = set()

    for record in index_records:
        metadata_path = str(record.get("metadata_path") or "")
        if record.get("experiment_id") != experiment.experiment_id and metadata_path not in linked_metadata_paths:
            continue
        dedupe_key = metadata_path or "|".join(
            [
                str(record.get("created_at_utc", "")),
                str(record.get("run_type", "")),
                str(record.get("run_id", "")),
                str(record.get("output_dir", "")),
            ]
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        linked_records.append(record)
    return linked_records


def _supporting_evidence_records(records: list[dict]) -> list[dict]:
    positive_records = [record for record in records if _numeric(record.get("excess_total_return")) > 0]
    validation_records = [
        record for record in positive_records if str(record.get("run_type")) in VALIDATION_RUN_TYPES
    ]
    return _sort_by_numeric(validation_records or positive_records, "excess_total_return", reverse=True)[:3]


def _contradicting_evidence_records(records: list[dict]) -> list[dict]:
    negative_records = [record for record in records if _numeric(record.get("excess_total_return")) <= 0]
    validation_records = [record for record in records if str(record.get("run_type")) in VALIDATION_RUN_TYPES]
    negative_validation = [
        record for record in validation_records if _numeric(record.get("excess_total_return")) <= 0
    ]
    return _sort_by_numeric(negative_validation or negative_records, "excess_total_return", reverse=False)[:3]


def _evidence_items(records: list[dict], *, default_label: str, default_note: str) -> list[ConclusionEvidenceItem]:
    return [
        ConclusionEvidenceItem(
            label=default_label,
            run_id=_optional_str(record.get("run_id")),
            run_type=str(record.get("run_type") or "-"),
            metric="excess_total_return",
            value=_optional_numeric(record.get("excess_total_return")),
            artifact_path=_optional_str(record.get("metadata_path")),
            note=default_note,
        )
        for record in records
    ]


def _robustness_notes(records: list[dict]) -> list[RobustnessConclusionNote]:
    notes = [
        _robustness_note(check, run_type, records)
        for check, run_type in ROBUSTNESS_RUN_TYPES.items()
    ]
    notes.append(
        RobustnessConclusionNote(
            check="parameter_neighborhood",
            status="not_applicable",
            artifact_path=None,
            summary="Parameter-neighborhood artifacts are read from sweep summaries and are not indexed as run rows yet.",
        )
    )
    return notes


def _robustness_note(check: str, run_type: str, records: list[dict]) -> RobustnessConclusionNote:
    matching = [record for record in records if str(record.get("run_type")) == run_type]
    if not matching:
        return RobustnessConclusionNote(
            check=check,
            status="missing",
            artifact_path=None,
            summary=f"No linked {run_type} rows were found.",
        )
    excess_values = [_numeric(record.get("excess_total_return")) for record in matching]
    if all(value > 0 for value in excess_values):
        status = "passed"
        summary = f"All linked {run_type} rows beat the benchmark on excess return."
    elif any(value > 0 for value in excess_values):
        status = "mixed"
        summary = f"Some linked {run_type} rows beat the benchmark and some did not."
    else:
        status = "failed"
        summary = f"No linked {run_type} rows beat the benchmark on excess return."
    return RobustnessConclusionNote(
        check=check,
        status=status,
        artifact_path=_first_artifact_path(matching),
        summary=summary,
    )


def _current_conclusion(
    experiment: ExperimentRecord,
    confidence_label: str,
    records: list[dict],
    robustness_notes: list[RobustnessConclusionNote],
) -> str:
    if not records:
        return f"No linked evidence exists yet for {experiment.experiment_id}. Run a baseline before drawing conclusions."
    if confidence_label == "rejected":
        return "The current linked evidence does not support the hypothesis. Stop repeating this branch unless the hypothesis changes."
    if confidence_label == "weak":
        return "The current evidence is weak or exploratory. Add validation and missing robustness checks before trusting the idea."
    if confidence_label == "mixed":
        return "The current evidence is mixed. Study the contradicting runs and failed robustness checks before promoting the idea."
    if confidence_label == "promising":
        if any(note.status in {"missing", "mixed", "failed"} for note in robustness_notes):
            return "The current evidence is promising but not complete; finish robustness checks before treating it as sturdy."
        return "The current evidence is promising across linked validation and robustness checks, but it is still local research evidence."
    return "Review the linked evidence before deciding what this experiment means."


def _do_not_repeat(
    confidence_label: str,
    records: list[dict],
    robustness_notes: list[RobustnessConclusionNote],
) -> list[str]:
    items = [
        "Do not treat the best backtest row as proof without validation.",
        "Do not ignore benchmark excess return when total return looks attractive.",
    ]
    if confidence_label in {"rejected", "mixed"}:
        items.append("Do not keep widening this branch until the contradicting evidence is explained.")
    if any(note.status in {"mixed", "failed"} for note in robustness_notes):
        items.append("Do not rerun the same robustness check after seeing failures without changing the hypothesis first.")
    if any(_numeric(record.get("trade_count"), missing=0) < 5 for record in records):
        items.append("Do not overread metrics from runs with tiny trade counts.")
    return items


def _next_useful_tests(
    confidence_label: str,
    records: list[dict],
    robustness_notes: list[RobustnessConclusionNote],
) -> list[NextUsefulTest]:
    if not records:
        return [
            NextUsefulTest(
                test="Run the first baseline.",
                reason="No linked evidence exists yet.",
                success_criteria="A saved run with metadata, benchmark comparison, and realistic costs.",
                suggested_command=None,
            )
        ]

    tests: list[NextUsefulTest] = []
    if not any(str(record.get("run_type")) in VALIDATION_RUN_TYPES for record in records):
        tests.append(
            NextUsefulTest(
                test="Run train/test or walk-forward validation.",
                reason="Exploratory evidence should not decide the experiment.",
                success_criteria="Validation run has positive excess return versus the selected benchmark.",
                suggested_command=None,
            )
        )
    missing_checks = [note.check for note in robustness_notes if note.status == "missing"]
    if missing_checks:
        tests.append(
            NextUsefulTest(
                test=f"Run missing robustness checks: {', '.join(missing_checks)}.",
                reason="The conclusion should survive controlled perturbations before confidence increases.",
                success_criteria="Robustness summaries are not failed and explain any mixed result.",
                suggested_command=None,
            )
        )
    if confidence_label in {"rejected", "mixed"}:
        tests.append(
            NextUsefulTest(
                test="Explain the failure mode before adding a broader sweep.",
                reason="More variants can hide the original contradiction instead of resolving it.",
                success_criteria="A written hypothesis explains why the contradicting evidence should not repeat.",
                suggested_command=None,
            )
        )
    if not tests:
        tests.append(
            NextUsefulTest(
                test="Test the same predefined idea on a different comparable asset.",
                reason="Checks whether the result generalizes beyond one instrument.",
                success_criteria="Positive validation excess return with the same cost and benchmark assumptions.",
                suggested_command=None,
            )
        )
    return tests


def _open_questions(
    confidence_label: str,
    records: list[dict],
    robustness_notes: list[RobustnessConclusionNote],
) -> list[str]:
    questions = [
        "Did adjusted price and corporate-action assumptions affect the comparison?",
        "Does the conclusion depend on one date range or market regime?",
    ]
    if any(_numeric(record.get("trade_count"), missing=0) < 5 for record in records):
        questions.append("Are there enough trades for the metrics to mean anything?")
    if any(note.status == "missing" for note in robustness_notes):
        questions.append("Would missing robustness checks change the conclusion?")
    if confidence_label in {"mixed", "rejected"}:
        questions.append("Which linked run best explains why the hypothesis failed or became mixed?")
    return questions


def _source_artifacts(experiment: ExperimentRecord, records: list[dict]) -> list[SourceArtifact]:
    artifacts = [
        SourceArtifact(kind="experiment_registry", path=f"experiment:{experiment.experiment_id}", role="source")
    ]
    for record in records:
        metadata_path = _optional_str(record.get("metadata_path"))
        output_dir = _optional_str(record.get("output_dir"))
        if metadata_path:
            artifacts.append(SourceArtifact(kind="run_metadata", path=metadata_path, role=_artifact_role(record)))
        elif output_dir:
            artifacts.append(SourceArtifact(kind="run_output", path=output_dir, role=_artifact_role(record)))
    return artifacts


def _artifact_role(record: dict) -> str:
    return "supporting" if _numeric(record.get("excess_total_return")) > 0 else "contradicting"


def _evidence_markdown(items: list[ConclusionEvidenceItem]) -> list[str]:
    if not items:
        return ["- None"]
    return [
        (
            f"- {item.label}: `{item.run_type}/{item.run_id or '-'}` "
            f"{item.metric} {_format_percent(item.value)} "
            f"artifact `{item.artifact_path or '-'}`. {item.note}"
        )
        for item in items
    ]


def _robustness_markdown(notes: list[RobustnessConclusionNote]) -> list[str]:
    return [
        f"- `{note.check}`: `{note.status}`. {note.summary} Artifact: `{note.artifact_path or '-'}`"
        for note in notes
    ]


def _next_test_markdown(tests: list[NextUsefulTest]) -> list[str]:
    if not tests:
        return ["- None"]
    lines: list[str] = []
    for test in tests:
        lines.append(f"- {test.test}")
        lines.append(f"  Reason: {test.reason}")
        lines.append(f"  Success criteria: {test.success_criteria}")
        if test.suggested_command is not None:
            lines.append(f"  Suggested command: `{test.suggested_command}`")
    return lines


def _source_artifact_markdown(artifacts: list[SourceArtifact]) -> list[str]:
    if not artifacts:
        return ["- None"]
    return [f"- `{artifact.kind}` `{artifact.path}` ({artifact.role})" for artifact in artifacts]


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None"]


def _first_artifact_path(records: list[dict]) -> str | None:
    for record in records:
        value = _optional_str(record.get("metadata_path")) or _optional_str(record.get("output_dir"))
        if value:
            return value
    return None


def _sort_by_numeric(records: list[dict], field: str, *, reverse: bool) -> list[dict]:
    missing = float("-inf") if reverse else float("inf")
    return sorted(records, key=lambda record: _numeric(record.get(field), missing=missing), reverse=reverse)


def _numeric(value: object, *, missing: float = float("-inf")) -> float:
    if value is None:
        return missing
    try:
        return float(value)
    except (TypeError, ValueError):
        return missing


def _optional_numeric(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    value_string = str(value).strip()
    return value_string or None


def _format_percent(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2%}"
