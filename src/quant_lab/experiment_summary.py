"""Evidence summaries that combine experiments with linked run index rows."""

from __future__ import annotations

from .research_registry import ExperimentRecord, format_experiment_detail


def format_experiment_evidence_summary(
    experiment: ExperimentRecord,
    index_records: list[dict],
    *,
    recent_limit: int = 5,
) -> str:
    linked_records = [
        record for record in index_records if record.get("experiment_id") == experiment.experiment_id
    ]
    linked_records.sort(key=lambda record: str(record.get("created_at_utc", "")), reverse=True)

    lines = [
        "Experiment Evidence Summary",
        "===========================",
        "",
        format_experiment_detail(experiment),
        "",
        "Evidence",
        f"  Linked index rows: {len(linked_records)}",
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
    lines.extend(
        [
            f"  Most recent run: {_run_label(most_recent)}",
            (
                "  Best total return: "
                f"{_run_label(best_total)} ({_format_percent(best_total.get('total_return'))})"
            ),
            (
                "  Best excess return: "
                f"{_run_label(best_excess)} ({_format_percent(best_excess.get('excess_total_return'))})"
            ),
            "",
            "Recent Runs",
            _format_recent_runs_table(linked_records[:recent_limit]),
        ]
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


def _numeric(value: object) -> float:
    if value is None:
        return float("-inf")
    return float(value)


def _format_percent(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2%}"


def _format_decimal(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}"
