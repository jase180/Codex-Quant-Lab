"""Evidence summaries that combine experiments with linked run index rows."""

from __future__ import annotations

from .research_registry import ExperimentRecord, format_experiment_detail


def format_experiment_evidence_summary(
    experiment: ExperimentRecord,
    index_records: list[dict],
    *,
    recent_limit: int = 5,
) -> str:
    linked_records = _linked_index_records(experiment, index_records)
    linked_records.sort(key=lambda record: str(record.get("created_at_utc", "")), reverse=True)
    missing_linked_paths = _missing_linked_paths(experiment, linked_records)

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
    ]

    if not linked_records:
        lines.extend(
            [
                "  Most recent run: -",
                "  Best total return: -",
                "  Best excess return: -",
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
