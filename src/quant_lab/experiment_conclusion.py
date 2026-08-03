"""Canonical experiment conclusion model and deterministic formatter."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Sequence

from .evidence_labels import VALIDATION_RUN_TYPES, label_strategy_evidence
from .research_plan import InvestmentObjective
from .research_registry import ExperimentRecord


EXPERIMENT_CONCLUSION_SCHEMA_VERSION = "experiment_conclusion.v1"
CONCLUSION_GENERATOR_NAME = "quant-lab conclude-experiment"
EXPERIMENT_CONCLUSION_JSON_FILENAME = "experiment_conclusion.json"
EXPERIMENT_CONCLUSION_MARKDOWN_FILENAME = "experiment_conclusion.md"
AGENT_CONTEXT_FILENAME = "agent_context.md"
AGENT_INSTRUCTIONS = [
    "Read experiment_conclusion.json before scanning raw artifacts.",
    "Treat current_conclusion as provisional, not market truth.",
    "Respect do_not_repeat unless the hypothesis changes.",
    "Propose small falsifiable next tests, not broad optimization.",
    "Cite source_artifacts when making claims.",
    "Preserve no-lookahead and next-open-fill assumptions.",
    "Do not treat a rejected strategy hypothesis as a failed research system.",
]
ROBUSTNESS_RUN_TYPES = {
    "cost_sensitivity": "cost_sensitivity_run",
    "date_sensitivity": "date_sensitivity_run",
    "benchmark_sensitivity": "benchmark_sensitivity_run",
}
MARKDOWN_SECTION_ORDER = [
    "## Current Conclusion",
    "## Research-System Status",
    "## Strategy-Hypothesis Status",
    "## Confidence",
    "## What Was Tested",
    "## What Supports This",
    "## What Contradicts This",
    "## Robustness Status",
    "## Do Not Repeat",
    "## Next Useful Tests",
    "## Open Questions",
    "## Source Artifacts",
    "## Next Research Prompt",
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
class StatusCheck:
    name: str
    status: str
    evidence: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchSystemStatus:
    status: str
    summary: str
    checks: list[StatusCheck]
    caveats: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "checks": [check.to_dict() for check in self.checks],
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True)
class StrategyCriterionResult:
    name: str
    passed: bool | None
    expected: str
    observed: str

    def to_dict(self) -> dict[str, bool | str | None]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyHypothesisStatus:
    status: str
    summary: str
    criteria_results: list[StrategyCriterionResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "criteria_results": [result.to_dict() for result in self.criteria_results],
        }


@dataclass(frozen=True)
class NextResearchPrompt:
    known_result: str
    what_appears_promising: list[str]
    what_failed: list[str]
    constraints: list[str]
    next_experiment_should: list[str]

    def to_dict(self) -> dict[str, str | list[str]]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentConclusion:
    schema_version: str
    experiment_id: str
    generated_at_utc: str
    generator: ConclusionGenerator
    experiment: ConclusionExperimentSnapshot
    research_system_status: ResearchSystemStatus
    strategy_hypothesis_status: StrategyHypothesisStatus
    confidence_label: str
    current_conclusion: str
    supporting_evidence: list[ConclusionEvidenceItem]
    contradicting_evidence: list[ConclusionEvidenceItem]
    robustness_notes: list[RobustnessConclusionNote]
    do_not_repeat: list[str]
    next_useful_tests: list[NextUsefulTest]
    open_questions: list[str]
    source_artifacts: list[SourceArtifact]
    next_research_prompt: NextResearchPrompt
    agent_instructions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "generated_at_utc": self.generated_at_utc,
            "generator": self.generator.to_dict(),
            "experiment": self.experiment.to_dict(),
            "research_system_status": self.research_system_status.to_dict(),
            "strategy_hypothesis_status": self.strategy_hypothesis_status.to_dict(),
            "confidence_label": self.confidence_label,
            "current_conclusion": self.current_conclusion,
            "supporting_evidence": [item.to_dict() for item in self.supporting_evidence],
            "contradicting_evidence": [item.to_dict() for item in self.contradicting_evidence],
            "robustness_notes": [item.to_dict() for item in self.robustness_notes],
            "do_not_repeat": list(self.do_not_repeat),
            "next_useful_tests": [item.to_dict() for item in self.next_useful_tests],
            "open_questions": list(self.open_questions),
            "source_artifacts": [item.to_dict() for item in self.source_artifacts],
            "next_research_prompt": self.next_research_prompt.to_dict(),
            "agent_instructions": list(self.agent_instructions),
        }


def build_experiment_conclusion(
    experiment: ExperimentRecord,
    index_records: Sequence[dict],
    *,
    generated_at_utc: str | None = None,
    generator_version: str = "unknown",
    investment_objective: InvestmentObjective | None = None,
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
    current_conclusion = _current_conclusion(experiment, evidence_label.label, linked_records, robustness_notes)
    research_system_status = _research_system_status(linked_records, robustness_notes)
    strategy_hypothesis_status = _strategy_hypothesis_status(
        linked_records,
        investment_objective=investment_objective,
        legacy_evidence_label=evidence_label.label,
    )
    do_not_repeat = _do_not_repeat(evidence_label.label, linked_records, robustness_notes)
    next_useful_tests = _next_useful_tests(evidence_label.label, linked_records, robustness_notes)
    open_questions = _open_questions(evidence_label.label, linked_records, robustness_notes)
    source_artifacts = _source_artifacts(experiment, linked_records)

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
        research_system_status=research_system_status,
        strategy_hypothesis_status=strategy_hypothesis_status,
        confidence_label=evidence_label.label,
        current_conclusion=current_conclusion,
        supporting_evidence=supporting_evidence,
        contradicting_evidence=contradicting_evidence,
        robustness_notes=robustness_notes,
        do_not_repeat=do_not_repeat,
        next_useful_tests=next_useful_tests,
        open_questions=open_questions,
        source_artifacts=source_artifacts,
        next_research_prompt=_next_research_prompt(
            current_conclusion=current_conclusion,
            research_system_status=research_system_status,
            strategy_hypothesis_status=strategy_hypothesis_status,
            supporting_evidence=supporting_evidence,
            contradicting_evidence=contradicting_evidence,
            robustness_notes=robustness_notes,
            do_not_repeat=do_not_repeat,
            next_useful_tests=next_useful_tests,
            open_questions=open_questions,
        ),
        agent_instructions=list(AGENT_INSTRUCTIONS),
    )


def format_experiment_conclusion_markdown(conclusion: ExperimentConclusion) -> str:
    """Render the human-first conclusion document."""

    lines = [
        f"# Experiment Conclusion: {conclusion.experiment_id}",
        "",
        "Report role: main source of truth.",
        "",
        "## Current Conclusion",
        "",
        conclusion.current_conclusion,
        "",
        "## Research-System Status",
        "",
        f"- Status: `{conclusion.research_system_status.status}`",
        f"- Summary: {conclusion.research_system_status.summary}",
        "- Checks:",
        *_status_check_markdown(conclusion.research_system_status.checks),
        "- Caveats:",
        *_indented_bullet_lines(conclusion.research_system_status.caveats),
        "",
        "## Strategy-Hypothesis Status",
        "",
        f"- Status: `{conclusion.strategy_hypothesis_status.status}`",
        f"- Summary: {conclusion.strategy_hypothesis_status.summary}",
        "- Criteria:",
        *_criterion_result_markdown(conclusion.strategy_hypothesis_status.criteria_results),
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
        "## Next Research Prompt",
        "",
        *_next_research_prompt_markdown(conclusion.next_research_prompt),
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
            f"- Research-system status: `{conclusion.research_system_status.status}`",
            f"- Strategy-hypothesis status: `{conclusion.strategy_hypothesis_status.status}`",
            "",
            "Next research prompt:",
            *_next_research_prompt_markdown(conclusion.next_research_prompt),
            "",
            "Rules:",
            *_bullet_lines(conclusion.agent_instructions),
            "",
        ]
    )


def save_experiment_conclusion_artifacts(
    conclusion: ExperimentConclusion,
    output_dir: str | Path,
    *,
    force: bool = False,
) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    artifact_paths = {
        "json": destination / EXPERIMENT_CONCLUSION_JSON_FILENAME,
        "markdown": destination / EXPERIMENT_CONCLUSION_MARKDOWN_FILENAME,
        "agent_context": destination / AGENT_CONTEXT_FILENAME,
    }

    existing_paths = [path for path in artifact_paths.values() if path.exists()]
    if existing_paths and not force:
        raise FileExistsError(
            f"conclusion artifact already exists: {existing_paths[0]}; pass --force to overwrite"
        )

    # The JSON artifact is the future-agent API, so keep it stable and easy to diff.
    artifact_paths["json"].write_text(
        json.dumps(conclusion.to_dict(), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    artifact_paths["markdown"].write_text(
        format_experiment_conclusion_markdown(conclusion),
        encoding="utf-8",
    )
    artifact_paths["agent_context"].write_text(
        format_agent_context(conclusion),
        encoding="utf-8",
    )
    return {kind: str(path) for kind, path in artifact_paths.items()}


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


def _research_system_status(
    records: list[dict],
    robustness_notes: list[RobustnessConclusionNote],
) -> ResearchSystemStatus:
    checks = [
        _status_check(
            "linked_evidence_exists",
            bool(records),
            "At least one linked research-index row was found." if records else "No linked research-index rows were found.",
        ),
        _status_check(
            "data_and_benchmark_aligned",
            any(record.get("data_start") and record.get("data_end") and record.get("benchmark_name") for record in records),
            "Linked rows include data range and benchmark fields.",
        ),
        _status_check(
            "no_lookahead_assumption_preserved",
            bool(records),
            "v1 strategy/backtester path uses bar t signals with bar t+1 open fills; see engine tests.",
        ),
        _status_check(
            "next_open_execution_used",
            bool(records),
            "Run artifacts were produced through the shared next-open execution path.",
        ),
        _status_check(
            "costs_and_sizing_recorded",
            any(record.get("cost_preset") is not None and record.get("sizing") is not None for record in records),
            "Linked rows include cost preset and sizing fields.",
        ),
        _status_check(
            "strategy_and_input_saved",
            any(record.get("metadata_path") for record in records),
            "Linked rows point to run_metadata.json artifacts.",
        ),
        _status_check(
            "validation_completed",
            any(str(record.get("run_type")) in VALIDATION_RUN_TYPES for record in records),
            "At least one train/test or walk-forward validation row is linked.",
        ),
        _status_check(
            "robustness_completed",
            all(note.status != "missing" for note in robustness_notes if note.check != "parameter_neighborhood"),
            "Cost, date, and benchmark sensitivity checks are present.",
        ),
    ]
    failed = [check for check in checks if check.status == "fail"]
    caveats = [check.evidence for check in failed]
    if not records:
        status = "invalid"
        summary = "No linked evidence exists, so the experiment has not measured the strategy yet."
    elif failed:
        status = "valid_with_caveats"
        summary = "The experiment produced evidence, but some workflow checks are missing or incomplete."
    else:
        status = "valid"
        summary = "The experiment measured the strategy honestly and reproducibly with the planned validation checks."
    return ResearchSystemStatus(status=status, summary=summary, checks=checks, caveats=caveats)


def _status_check(name: str, passed: bool, evidence: str) -> StatusCheck:
    return StatusCheck(name=name, status="pass" if passed else "fail", evidence=evidence)


def _strategy_hypothesis_status(
    records: list[dict],
    *,
    investment_objective: InvestmentObjective | None,
    legacy_evidence_label: str,
) -> StrategyHypothesisStatus:
    if not records:
        return StrategyHypothesisStatus(
            status="inconclusive",
            summary="No linked strategy evidence exists yet.",
            criteria_results=[],
        )
    if investment_objective is None or not investment_objective.success_criteria:
        return StrategyHypothesisStatus(
            status="inconclusive",
            summary=(
                "No prespecified measurable success criteria were found. "
                f"Legacy evidence label is `{legacy_evidence_label}`, but strategy status should not be finalized from ad hoc criteria."
            ),
            criteria_results=[],
        )

    record = _representative_strategy_record(records)
    criteria_results = [_evaluate_success_criterion(record, criterion) for criterion in investment_objective.success_criteria]
    known_results = [result for result in criteria_results if result.passed is not None]
    if not known_results:
        status = "inconclusive"
        summary = "The prespecified criteria could not be evaluated from current linked run fields."
    elif all(result.passed for result in known_results) and len(known_results) == len(criteria_results):
        status = "supported"
        summary = "The strategy met all prespecified measurable criteria."
    elif any(result.passed for result in known_results):
        status = "partially_supported"
        summary = "The strategy met some prespecified criteria but failed or could not evaluate others."
    else:
        status = "rejected"
        summary = "The strategy failed the prespecified measurable criteria."
    return StrategyHypothesisStatus(status=status, summary=summary, criteria_results=criteria_results)


def _representative_strategy_record(records: list[dict]) -> dict:
    validation_records = [record for record in records if str(record.get("run_type")) in VALIDATION_RUN_TYPES]
    if validation_records:
        return sorted(validation_records, key=lambda record: str(record.get("created_at_utc", "")), reverse=True)[0]
    baseline_records = [record for record in records if str(record.get("run_type")) == "run"]
    return (baseline_records or records)[0]


def _evaluate_success_criterion(record: dict, criterion) -> StrategyCriterionResult:
    observed_value = _criterion_observed_value(record, criterion.metric, criterion.comparison)
    expected = f"{criterion.metric} {criterion.comparison} {criterion.operator} {criterion.threshold}"
    if observed_value is None:
        return StrategyCriterionResult(
            name=criterion.name,
            passed=None,
            expected=expected,
            observed="Could not evaluate from linked run fields.",
        )
    passed = _compare_observed(observed_value, criterion.operator, criterion.threshold)
    return StrategyCriterionResult(
        name=criterion.name,
        passed=passed,
        expected=expected,
        observed=f"{observed_value:.4f}",
    )


def _criterion_observed_value(record: dict, metric: str, comparison: str) -> float | None:
    if comparison == "strategy_vs_benchmark_ratio":
        strategy_value = _record_metric(record, metric)
        benchmark_value = _record_metric(record, f"benchmark_{metric}")
        if strategy_value is None or benchmark_value in {None, 0}:
            return None
        return strategy_value / float(benchmark_value)
    if comparison == "relative_reduction_vs_benchmark":
        strategy_value = _record_metric(record, metric)
        benchmark_value = _record_metric(record, f"benchmark_{metric}")
        if strategy_value is None or benchmark_value in {None, 0}:
            return None
        return (abs(float(benchmark_value)) - abs(strategy_value)) / abs(float(benchmark_value))
    if comparison == "absolute":
        return _record_metric(record, metric)
    return None


def _record_metric(record: dict, field: str) -> float | None:
    value = _optional_numeric(record.get(field))
    if value is not None:
        return value
    if field == "benchmark_cagr":
        return _benchmark_cagr_from_record(record)
    return None


def _benchmark_cagr_from_record(record: dict) -> float | None:
    benchmark_total_return = _optional_numeric(record.get("benchmark_total_return"))
    row_count = _metadata_row_count(record)
    if benchmark_total_return is None or row_count is None or row_count < 2:
        return None
    elapsed_days = row_count - 1
    return (1 + benchmark_total_return) ** (252 / elapsed_days) - 1


def _metadata_row_count(record: dict) -> int | None:
    metadata_path = _optional_str(record.get("metadata_path"))
    if metadata_path is None:
        return None
    path = Path(metadata_path)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    row_count = payload.get("data", {}).get("row_count")
    try:
        return int(row_count)
    except (TypeError, ValueError):
        return None


def _compare_observed(value: float, operator: str, threshold) -> bool | None:
    if operator == ">=":
        return value >= float(threshold)
    if operator == ">":
        return value > float(threshold)
    if operator == "<=":
        return value <= float(threshold)
    if operator == "<":
        return value < float(threshold)
    return None


def _current_conclusion(
    experiment: ExperimentRecord,
    confidence_label: str,
    records: list[dict],
    robustness_notes: list[RobustnessConclusionNote],
) -> str:
    if not records:
        return f"No linked evidence exists yet for {experiment.experiment_id}. Run a baseline before drawing conclusions."
    if confidence_label == "rejected":
        return (
            "The research system produced a usable measurement, but the tested strategy did not satisfy the current "
            "strategy evidence hurdle. Treat this as a valid negative result unless a correctness caveat says otherwise."
        )
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
    if confidence_label == "rejected":
        tests.append(
            NextUsefulTest(
                test="Stop this branch or reformulate the hypothesis before running more tests.",
                reason="No linked run beat the benchmark on excess return, so more validation would mostly confirm a weak branch.",
                success_criteria="A revised hypothesis explains why the next test should behave differently from the rejected evidence.",
                suggested_command=None,
            )
        )
        tests.append(
            NextUsefulTest(
                test="Explain the failure mode before adding a broader sweep.",
                reason="More variants can hide the original contradiction instead of resolving it.",
                success_criteria="A written hypothesis explains why the contradicting evidence should not repeat.",
                suggested_command=None,
            )
        )
        return tests

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
    if confidence_label == "mixed":
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


def _next_research_prompt(
    *,
    current_conclusion: str,
    research_system_status: ResearchSystemStatus,
    strategy_hypothesis_status: StrategyHypothesisStatus,
    supporting_evidence: list[ConclusionEvidenceItem],
    contradicting_evidence: list[ConclusionEvidenceItem],
    robustness_notes: list[RobustnessConclusionNote],
    do_not_repeat: list[str],
    next_useful_tests: list[NextUsefulTest],
    open_questions: list[str],
) -> NextResearchPrompt:
    # This is intentionally deterministic. A model can read it later, but the
    # project itself decides the evidence-shaped boundaries of the next cycle.
    return NextResearchPrompt(
        known_result=(
            f"{current_conclusion} Research-system status: {research_system_status.status}. "
            f"Strategy-hypothesis status: {strategy_hypothesis_status.status}."
        ),
        what_appears_promising=_prompt_evidence_lines(supporting_evidence)
        or ["No linked evidence currently supports the hypothesis."],
        what_failed=_prompt_failure_lines(contradicting_evidence, robustness_notes),
        constraints=do_not_repeat + [
            "Change only one meaningful research idea per next experiment.",
            "Define success criteria before running the next command.",
            "Keep realistic costs, benchmark comparison, and next-open execution assumptions.",
        ],
        next_experiment_should=[
            f"{test.test} Reason: {test.reason} Success criteria: {test.success_criteria}"
            for test in next_useful_tests
        ]
        + [f"Resolve open question: {question}" for question in open_questions[:2]],
    )


def _prompt_evidence_lines(items: list[ConclusionEvidenceItem]) -> list[str]:
    return [
        f"`{item.run_type}/{item.run_id or '-'}` {item.metric} {_format_percent(item.value)}; source `{item.artifact_path or '-'}`."
        for item in items
    ]


def _prompt_failure_lines(
    contradicting_evidence: list[ConclusionEvidenceItem],
    robustness_notes: list[RobustnessConclusionNote],
) -> list[str]:
    lines = [
        f"`{item.run_type}/{item.run_id or '-'}` {item.metric} {_format_percent(item.value)}; source `{item.artifact_path or '-'}`."
        for item in contradicting_evidence
    ]
    lines.extend(
        f"`{note.check}` was `{note.status}`: {note.summary}"
        for note in robustness_notes
        if note.status in {"missing", "mixed", "failed"}
    )
    return lines or ["No specific failure is recorded yet; gather baseline evidence first."]


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


def _status_check_markdown(checks: list[StatusCheck]) -> list[str]:
    if not checks:
        return ["  - none"]
    return [f"  - `{check.name}`: `{check.status}`. {check.evidence}" for check in checks]


def _criterion_result_markdown(results: list[StrategyCriterionResult]) -> list[str]:
    if not results:
        return ["  - none"]
    lines: list[str] = []
    for result in results:
        status = "unknown" if result.passed is None else ("pass" if result.passed else "fail")
        lines.append(f"  - `{result.name}`: `{status}`. Expected: {result.expected}. Observed: {result.observed}")
    return lines


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


def _next_research_prompt_markdown(prompt: NextResearchPrompt) -> list[str]:
    return [
        "Use this when planning the next experiment cycle.",
        "",
        f"- Known result: {prompt.known_result}",
        "- What appears promising:",
        *_indented_bullet_lines(prompt.what_appears_promising),
        "- What failed or remains weak:",
        *_indented_bullet_lines(prompt.what_failed),
        "- Constraints:",
        *_indented_bullet_lines(prompt.constraints),
        "- Next experiment should:",
        *_indented_bullet_lines(prompt.next_experiment_should),
    ]


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None"]


def _indented_bullet_lines(items: list[str]) -> list[str]:
    return [f"  - {item}" for item in items] if items else ["  - None"]


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
