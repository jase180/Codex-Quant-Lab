"""Evidence summaries that combine experiments with linked run index rows."""

from __future__ import annotations

from .evidence_labels import label_strategy_evidence
from .research_registry import ExperimentRecord, format_experiment_detail

VALIDATION_RUN_TYPES = {"test_selected_run", "walk_forward_test_run"}


def format_experiment_evidence_summary(
    experiment: ExperimentRecord,
    index_records: list[dict],
    *,
    recent_limit: int = 5,
) -> str:
    linked_records = _linked_index_records(experiment, index_records)
    linked_records.sort(key=lambda record: str(record.get("created_at_utc", "")), reverse=True)
    missing_linked_paths = _missing_linked_paths(experiment, linked_records)
    evidence_label = label_strategy_evidence(linked_records)

    lines = [
        "Experiment Evidence Summary",
        "===========================",
        "",
        format_experiment_detail(experiment),
        "",
        "Evidence",
        f"  Registry linked metadata paths: {len(experiment.linked_runs)}",
        f"  Linked index rows: {len(linked_records)}",
        f"  Linked paths missing from index: {len(missing_linked_paths)}",
        "",
        "Evidence Label",
        f"  Label: {evidence_label.label}",
        "  Reasons:",
        *_indented_lines(evidence_label.reasons),
    ]

    if not linked_records:
        lines.extend(
            [
                "  Most recent run: -",
                "  Best total return: -",
                "  Best excess return: -",
                "",
                "Supporting Evidence",
                "  None",
                "",
                "Contradicting Evidence",
                "  None",
                "",
                "Recent Runs",
                "  No linked runs found in the research index.",
            ]
        )
        return "\n".join(lines)

    most_recent = linked_records[0]
    best_total = max(linked_records, key=lambda record: _numeric(record.get("total_return")))
    best_excess = max(linked_records, key=lambda record: _numeric(record.get("excess_total_return")))
    weakest_excess = min(linked_records, key=lambda record: _numeric(record.get("excess_total_return"), missing=float("inf")))
    worst_drawdown = min(linked_records, key=lambda record: _numeric(record.get("max_drawdown"), missing=float("inf")))
    lines.extend(
        [
            f"  Most recent run: {_run_label(most_recent)}",
            (
                "  Strongest excess evidence: "
                f"{_run_label(best_excess)} ({_format_percent(best_excess.get('excess_total_return'))})"
            ),
            (
                "  Weakest excess evidence: "
                f"{_run_label(weakest_excess)} ({_format_percent(weakest_excess.get('excess_total_return'))})"
            ),
            (
                "  Best total return: "
                f"{_run_label(best_total)} ({_format_percent(best_total.get('total_return'))})"
            ),
            (
                "  Best excess return: "
                f"{_run_label(best_excess)} ({_format_percent(best_excess.get('excess_total_return'))})"
            ),
            (
                "  Worst drawdown: "
                f"{_run_label(worst_drawdown)} ({_format_percent(worst_drawdown.get('max_drawdown'))})"
            ),
            "",
            "Supporting Evidence",
            *_evidence_lines(_supporting_evidence_records(linked_records)),
            "",
            "Contradicting Evidence",
            *_evidence_lines(_contradicting_evidence_records(linked_records)),
            "",
            "Run Type Breakdown",
            _format_run_type_breakdown(linked_records),
            "",
            "Top Evidence By Excess Return",
            _format_recent_runs_table(
                _sort_by_numeric(linked_records, "excess_total_return", reverse=True)[:recent_limit]
            ),
            "",
            "Weakest Evidence By Excess Return",
            _format_recent_runs_table(
                _sort_by_numeric(linked_records, "excess_total_return", reverse=False)[:recent_limit]
            ),
            "",
            "Recent Runs",
            _format_recent_runs_table(linked_records[:recent_limit]),
        ]
    )
    return "\n".join(lines)


def format_experiment_decision_draft(
    experiment: ExperimentRecord,
    index_records: list[dict],
) -> str:
    linked_records = _linked_index_records(experiment, index_records)
    linked_records.sort(key=lambda record: str(record.get("created_at_utc", "")), reverse=True)

    evidence_label = label_strategy_evidence(linked_records)
    draft = _draft_decision_fields(linked_records)
    command = _format_decide_command(experiment.experiment_id, draft)
    return "\n".join(
        [
            "Experiment Decision Draft",
            "=========================",
            "",
            f"Experiment: {experiment.experiment_id}",
            f"Title: {experiment.title}",
            "",
            "Draft",
            f"  Suggested outcome: {draft['outcome']}",
            f"  Rationale: {draft['rationale']}",
            f"  Supporting run: {draft['supporting_run'] or '-'}",
            f"  Contradicting run: {draft['contradicting_run'] or '-'}",
            f"  Next action: {draft['next_action']}",
            "",
            "Evidence Label",
            f"  Label: {evidence_label.label}",
            "  Reasons:",
            *_indented_lines(evidence_label.reasons),
            "",
            "Uncertainty",
            *_indented_lines(_decision_uncertainty_lines(evidence_label.label, linked_records)),
            "",
            "What Would Change My Mind",
            *_indented_lines(_change_my_mind_lines(evidence_label.label, linked_records)),
            "",
            "Review Notes",
            "  This command does not write to the experiment registry.",
            "  Read the evidence summary before copying the decision into the registry.",
            "  Edit the rationale and next action if your judgment differs from the draft.",
            "",
            "Suggested Command",
            command,
        ]
    )


def _decision_uncertainty_lines(label: str, records: list[dict]) -> list[str]:
    validation_records = [record for record in records if record.get("run_type") in VALIDATION_RUN_TYPES]
    low_trade_count = sum(1 for record in records if _numeric(record.get("trade_count"), missing=0) < 5)

    if label == "no_evidence":
        return ["No linked evidence exists, so any decision would be guesswork."]
    if label == "weak":
        lines = ["Evidence is still exploratory or thin."]
        if not validation_records:
            lines.append("There is no out-of-sample validation linked to this experiment.")
        if low_trade_count:
            lines.append("One or more linked runs have too few trades to trust the metric shape.")
        return lines
    if label == "rejected":
        return [
            "The current linked evidence does not support the hypothesis.",
            "A better sweep result alone should not override failed validation evidence.",
        ]
    if label == "mixed":
        return [
            "Some linked evidence supports the hypothesis and some contradicts it.",
            "The failure mode matters more than the best single run.",
        ]
    if label == "promising":
        return [
            "Promising is not proof.",
            "The result can still depend on date range, costs, asset choice, or parameter luck.",
        ]
    return ["Review the linked evidence before deciding."]


def _change_my_mind_lines(label: str, records: list[dict]) -> list[str]:
    validation_records = [record for record in records if record.get("run_type") in VALIDATION_RUN_TYPES]
    low_trade_count = sum(1 for record in records if _numeric(record.get("trade_count"), missing=0) < 5)

    if label == "no_evidence":
        return ["Run a baseline plus a validation check with trusted data and realistic costs."]
    if label == "weak":
        lines = ["Add a train/test or walk-forward validation run that also beats the benchmark."]
        if not validation_records:
            lines.append("Use validation before accepting the idea, even if the sweep winner looks strong.")
        if low_trade_count:
            lines.append("Increase sample size or test a period that naturally creates more trades.")
        return lines
    if label == "rejected":
        return [
            "State a revised hypothesis before running more sweeps.",
            "Do not keep widening this branch just because one exploratory run looked good.",
        ]
    if label == "mixed":
        return [
            "Identify why the underperforming runs failed.",
            "Run a targeted validation window that directly tests that failure explanation.",
        ]
    if label == "promising":
        return [
            "Run robustness checks across dates, costs, and symbols.",
            "Downgrade the idea if it fails under reasonable perturbations.",
        ]
    return ["Write down the evidence that would change the decision before adding more runs."]


def _draft_decision_fields(records: list[dict]) -> dict[str, str | None]:
    if not records:
        return {
            "outcome": "continue",
            "rationale": "No linked index evidence exists yet.",
            "supporting_run": None,
            "contradicting_run": None,
            "next_action": "Run a baseline and at least one validation check before deciding.",
        }

    best_excess = max(records, key=lambda record: _numeric(record.get("excess_total_return")))
    weakest_excess = min(records, key=lambda record: _numeric(record.get("excess_total_return"), missing=float("inf")))
    validation_records = [record for record in records if record.get("run_type") in VALIDATION_RUN_TYPES]
    best_validation = (
        max(validation_records, key=lambda record: _numeric(record.get("excess_total_return")))
        if validation_records
        else None
    )
    best_excess_value = _numeric(best_excess.get("excess_total_return"))
    weakest_excess_value = _numeric(weakest_excess.get("excess_total_return"), missing=float("inf"))
    best_validation_value = (
        _numeric(best_validation.get("excess_total_return")) if best_validation is not None else None
    )

    if best_excess_value <= 0:
        return {
            "outcome": "reject",
            "rationale": f"No linked run beat the benchmark on excess return; best excess was {_format_percent(best_excess_value)}.",
            "supporting_run": _evidence_reference(best_excess),
            "contradicting_run": _evidence_reference(weakest_excess),
            "next_action": "Stop this branch or reformulate the hypothesis before running more sweeps.",
        }

    if best_validation is None:
        return {
            "outcome": "continue",
            "rationale": "Best linked evidence is positive, but no train/test or walk-forward validation run is linked yet.",
            "supporting_run": _evidence_reference(best_excess),
            "contradicting_run": _evidence_reference(weakest_excess) if weakest_excess_value < 0 else None,
            "next_action": "Run train/test or walk-forward validation before accepting or rejecting.",
        }

    if best_validation_value is not None and best_validation_value <= 0:
        return {
            "outcome": "reject",
            "rationale": f"Validation evidence did not beat the benchmark; best validation excess was {_format_percent(best_validation_value)}.",
            "supporting_run": _evidence_reference(best_excess),
            "contradicting_run": _evidence_reference(best_validation),
            "next_action": "Reject this parameter branch or return to the hypothesis with stricter constraints.",
        }

    if weakest_excess_value < 0:
        return {
            "outcome": "continue",
            "rationale": "Validation evidence is positive, but linked evidence is mixed across runs.",
            "supporting_run": _evidence_reference(best_validation),
            "contradicting_run": _evidence_reference(weakest_excess),
            "next_action": "Investigate why weaker runs failed before promoting the idea.",
        }

    return {
        "outcome": "accept",
        "rationale": "Linked evidence and validation evidence both show positive excess return.",
        "supporting_run": _evidence_reference(best_validation),
        "contradicting_run": None,
        "next_action": "Promote this idea to stricter validation or paper-trading research.",
    }


def _format_decide_command(experiment_id: str, draft: dict[str, str | None]) -> str:
    parts = [
        "quant-lab decide-experiment",
        f"  --experiment-id {experiment_id}",
        f"  --outcome {draft['outcome']}",
        f"  --rationale {_shell_quote(str(draft['rationale']))}",
    ]
    if draft["supporting_run"] is not None:
        parts.append(f"  --supporting-run {_shell_quote(str(draft['supporting_run']))}")
    if draft["contradicting_run"] is not None:
        parts.append(f"  --contradicting-run {_shell_quote(str(draft['contradicting_run']))}")
    parts.append(f"  --next-action {_shell_quote(str(draft['next_action']))}")
    return " \\\n".join(parts)


def _linked_index_records(experiment: ExperimentRecord, index_records: list[dict]) -> list[dict]:
    linked_metadata_paths = set(experiment.linked_runs)
    linked_records: list[dict] = []
    seen_keys: set[str] = set()

    for record in index_records:
        metadata_path = str(record.get("metadata_path") or "")
        is_linked_by_experiment_id = record.get("experiment_id") == experiment.experiment_id
        is_linked_by_metadata_path = metadata_path in linked_metadata_paths
        if not is_linked_by_experiment_id and not is_linked_by_metadata_path:
            continue

        # Some records match by both experiment id and metadata path. Dedupe so
        # the summary counts evidence rows, not the number of ways we found them.
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


def _missing_linked_paths(experiment: ExperimentRecord, linked_records: list[dict]) -> list[str]:
    indexed_paths = {str(record.get("metadata_path")) for record in linked_records if record.get("metadata_path")}
    return [metadata_path for metadata_path in experiment.linked_runs if metadata_path not in indexed_paths]


def _supporting_evidence_records(records: list[dict]) -> list[dict]:
    positive_records = [
        record for record in records if _numeric(record.get("excess_total_return")) > 0
    ]
    validation_records = [
        record for record in positive_records if record.get("run_type") in VALIDATION_RUN_TYPES
    ]
    source = validation_records or positive_records
    return _sort_by_numeric(source, "excess_total_return", reverse=True)[:3]


def _contradicting_evidence_records(records: list[dict]) -> list[dict]:
    negative_records = [
        record for record in records if _numeric(record.get("excess_total_return")) <= 0
    ]
    validation_records = [
        record for record in records if record.get("run_type") in VALIDATION_RUN_TYPES
    ]
    negative_validation = [
        record for record in validation_records if _numeric(record.get("excess_total_return")) <= 0
    ]
    source = negative_validation or negative_records
    return _sort_by_numeric(source, "excess_total_return", reverse=False)[:3]


def _evidence_lines(records: list[dict]) -> list[str]:
    if not records:
        return ["  None"]
    return [
        (
            f"  - {_run_label(record)}: excess {_format_percent(record.get('excess_total_return'))}, "
            f"return {_format_percent(record.get('total_return'))}, "
            f"trades {record.get('trade_count', '-')}, "
            f"metadata {_evidence_reference(record)}"
        )
        for record in records
    ]


def _indented_lines(lines: list[str]) -> list[str]:
    if not lines:
        return ["    - None"]
    return [f"    - {line}" for line in lines]


def _format_run_type_breakdown(records: list[dict]) -> str:
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(str(record.get("run_type") or "-"), []).append(record)

    lines = [
        "type                   rows  best_excess  best_total  weakest_excess  trades",
        "---------------------  ----  -----------  ----------  --------------  ------",
    ]
    for run_type in sorted(grouped):
        run_records = grouped[run_type]
        best_excess = max(run_records, key=lambda record: _numeric(record.get("excess_total_return")))
        best_total = max(run_records, key=lambda record: _numeric(record.get("total_return")))
        weakest_excess = min(
            run_records,
            key=lambda record: _numeric(record.get("excess_total_return"), missing=float("inf")),
        )
        lines.append(
            "  ".join(
                [
                    run_type.ljust(21),
                    str(len(run_records)).rjust(4),
                    _format_percent(best_excess.get("excess_total_return")).rjust(11),
                    _format_percent(best_total.get("total_return")).rjust(10),
                    _format_percent(weakest_excess.get("excess_total_return")).rjust(14),
                    str(sum(int(record.get("trade_count") or 0) for record in run_records)).rjust(6),
                ]
            )
        )
    return "\n".join(lines)


def _format_recent_runs_table(records: list[dict]) -> str:
    lines = [
        "created              type                   run       strategy  return  excess  sharpe  trades  output",
        "-------------------  ---------------------  --------  --------  ------  ------  ------  ------  ------",
    ]
    for record in records:
        lines.append(
            "  ".join(
                [
                    str(record.get("created_at_utc", "-")).replace("T", " ")[:19].ljust(19),
                    str(record.get("run_type", "-")).ljust(21),
                    str(record.get("run_id") or "-").ljust(8),
                    str(record.get("strategy_id") or "-").ljust(8),
                    _format_percent(record.get("total_return")).rjust(6),
                    _format_percent(record.get("excess_total_return")).rjust(6),
                    _format_decimal(record.get("sharpe_ratio")).rjust(6),
                    str(record.get("trade_count", "-")).rjust(6),
                    str(record.get("output_dir", "-")),
                ]
            )
        )
    return "\n".join(lines)


def _run_label(record: dict) -> str:
    run_id = record.get("run_id") or "-"
    return f"{record.get('run_type', '-')}/{run_id}"


def _evidence_reference(record: dict) -> str:
    return str(record.get("metadata_path") or _run_label(record))


def _shell_quote(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def _numeric(value: object, *, missing: float = float("-inf")) -> float:
    if value is None:
        return missing
    try:
        return float(value)
    except (TypeError, ValueError):
        return missing


def _sort_by_numeric(records: list[dict], field: str, *, reverse: bool) -> list[dict]:
    missing = float("-inf") if reverse else float("inf")
    return sorted(records, key=lambda record: _numeric(record.get(field), missing=missing), reverse=reverse)


def _format_percent(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2%}"


def _format_decimal(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}"
