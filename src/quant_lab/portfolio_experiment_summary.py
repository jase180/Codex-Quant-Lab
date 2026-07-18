"""Portfolio-specific evidence summaries for linked experiment runs."""

from __future__ import annotations

from pathlib import Path

from .research_registry import ExperimentRecord, format_experiment_detail


def format_portfolio_experiment_summary(
    experiment: ExperimentRecord,
    index_records: list[dict],
    *,
    top_limit: int = 5,
) -> str:
    portfolio_records = _linked_portfolio_records(experiment, index_records)
    portfolio_records.sort(key=lambda record: str(record.get("created_at_utc", "")), reverse=True)

    lines = [
        "# Portfolio Experiment Summary",
        "",
        "```text",
        format_experiment_detail(experiment),
        "```",
        "",
        "## Evidence Count",
        "",
        f"- Registry linked metadata paths: {len(experiment.linked_runs)}",
        f"- Linked portfolio index rows: {len(portfolio_records)}",
        "",
    ]

    if not portfolio_records:
        lines.extend(
            [
                "## Evidence Notes",
                "",
                "- No linked portfolio runs were found in the research index.",
            ]
        )
        return "\n".join(lines)

    best_total = _best_record(portfolio_records, "total_return")
    best_excess = _best_record(portfolio_records, "excess_total_return")
    best_sharpe = _best_record(portfolio_records, "sharpe_ratio")
    worst_drawdown = _worst_record(portfolio_records, "max_drawdown")
    underperformers = [
        record for record in portfolio_records if _numeric(record.get("excess_total_return")) < 0
    ]
    large_drawdowns = [
        record for record in portfolio_records if _numeric(record.get("max_drawdown")) <= -0.2
    ]

    lines.extend(
        [
            "## Highlights",
            "",
            f"- Best total return: {_record_label(best_total)} ({_format_percent(best_total.get('total_return'))})",
            f"- Best excess return: {_record_label(best_excess)} ({_format_percent(best_excess.get('excess_total_return'))})",
            f"- Best Sharpe ratio: {_record_label(best_sharpe)} ({_format_decimal(best_sharpe.get('sharpe_ratio'))})",
            f"- Worst drawdown: {_record_label(worst_drawdown)} ({_format_percent(worst_drawdown.get('max_drawdown'))})",
            "",
            "## Skeptical Notes",
            "",
            f"- Benchmark underperformers: {len(underperformers)} of {len(portfolio_records)} portfolio runs.",
            f"- Runs with drawdown at or below -20%: {len(large_drawdowns)}.",
            "- Do not promote an allocation from this summary alone. Inspect the source metadata and reports.",
            "",
            "## Top By Excess Return",
            "",
            _format_portfolio_table(_sort_by_numeric(portfolio_records, "excess_total_return", reverse=True)[:top_limit]),
            "",
            "## Top By Total Return",
            "",
            _format_portfolio_table(_sort_by_numeric(portfolio_records, "total_return", reverse=True)[:top_limit]),
            "",
            "## Top By Sharpe Ratio",
            "",
            _format_portfolio_table(_sort_by_numeric(portfolio_records, "sharpe_ratio", reverse=True)[:top_limit]),
            "",
            "## Worst Drawdowns",
            "",
            _format_portfolio_table(_sort_by_numeric(portfolio_records, "max_drawdown", reverse=False)[:top_limit]),
            "",
            "## Source Metadata",
            "",
            _format_metadata_paths(portfolio_records),
        ]
    )
    return "\n".join(lines)


def save_portfolio_experiment_summary(markdown: str, output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown + "\n", encoding="utf-8")
    return str(path)


def _linked_portfolio_records(experiment: ExperimentRecord, index_records: list[dict]) -> list[dict]:
    linked_paths = set(experiment.linked_runs)
    records: list[dict] = []
    seen: set[str] = set()
    for record in index_records:
        if record.get("run_type") != "portfolio_run":
            continue
        metadata_path = str(record.get("metadata_path") or "")
        if record.get("experiment_id") != experiment.experiment_id and metadata_path not in linked_paths:
            continue
        dedupe_key = metadata_path or str(record.get("output_dir") or record.get("created_at_utc") or len(records))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        records.append(record)
    return records


def _format_portfolio_table(records: list[dict]) -> str:
    lines = [
        "| portfolio | symbols | return | excess | benchmark | drawdown | sharpe | cost | output |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for record in records:
        cells = [
            f"`{record.get('strategy_id') or '-'}`",
            str(record.get("symbol") or "-"),
            _format_percent(record.get("total_return")),
            _format_percent(record.get("excess_total_return")),
            _format_percent(record.get("benchmark_total_return")),
            _format_percent(record.get("max_drawdown")),
            _format_decimal(record.get("sharpe_ratio")),
            str(record.get("cost_preset") or "-"),
            f"`{record.get('output_dir') or '-'}`",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _format_metadata_paths(records: list[dict]) -> str:
    lines = []
    for record in records:
        metadata_path = record.get("metadata_path") or "-"
        lines.append(f"- `{metadata_path}`")
    return "\n".join(lines)


def _record_label(record: dict) -> str:
    return str(record.get("strategy_id") or record.get("output_dir") or "-")


def _best_record(records: list[dict], field: str) -> dict:
    return max(records, key=lambda record: _numeric(record.get(field)))


def _worst_record(records: list[dict], field: str) -> dict:
    return min(records, key=lambda record: _numeric(record.get(field), missing=float("inf")))


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


def _format_percent(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2%}"


def _format_decimal(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}"
