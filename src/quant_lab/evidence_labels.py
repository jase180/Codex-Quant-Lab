"""Deterministic evidence labels for linked research runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VALIDATION_RUN_TYPES = {"test_selected_run", "walk_forward_test_run"}
PORTFOLIO_DATA_TRUST_REPORT_FILENAME = "portfolio_data_trust_report.md"
MIN_PORTFOLIO_VARIANTS = 2
MAX_PORTFOLIO_VARIANTS = 20
MARGINAL_EXCESS_RETURN = 0.01
LARGE_DRAWDOWN = -0.2


@dataclass(frozen=True)
class EvidenceLabel:
    label: str
    reasons: list[str]


def label_strategy_evidence(
    records: list[dict],
    *,
    min_trades: int = 5,
) -> EvidenceLabel:
    """Classify linked strategy evidence without pretending it is proof.

    These labels are intentionally conservative. A positive sweep winner is not
    `promising` by itself because a sweep is still exploratory evidence until a
    later test period or walk-forward window agrees.
    """

    if not records:
        return EvidenceLabel("no_evidence", ["No linked run evidence exists yet."])

    best_excess = _best_record(records, "excess_total_return")
    weakest_excess = _weakest_record(records, "excess_total_return")
    validation_records = [
        record for record in records if str(record.get("run_type")) in VALIDATION_RUN_TYPES
    ]
    best_excess_value = _numeric(best_excess.get("excess_total_return"))
    weakest_excess_value = _numeric(weakest_excess.get("excess_total_return"), missing=float("inf"))
    low_trade_count = _low_trade_count(records, min_trades=min_trades)

    reasons: list[str] = []
    if best_excess_value <= 0:
        return EvidenceLabel(
            "rejected",
            [
                "No linked run beat the benchmark on excess return.",
                f"Best excess return was {_format_percent(best_excess_value)}.",
            ],
        )

    if low_trade_count:
        reasons.append(
            f"{low_trade_count} linked run(s) have fewer than {min_trades} trades."
        )

    if not validation_records:
        reasons.append("No train/test or walk-forward validation run is linked yet.")
        reasons.append(
            f"Best linked excess return is {_format_percent(best_excess_value)}, but it is still exploratory."
        )
        return EvidenceLabel("weak", reasons)

    best_validation = _best_record(validation_records, "excess_total_return")
    best_validation_value = _numeric(best_validation.get("excess_total_return"))
    if best_validation_value <= 0:
        return EvidenceLabel(
            "rejected",
            [
                "Validation evidence did not beat the benchmark.",
                f"Best validation excess return was {_format_percent(best_validation_value)}.",
            ],
        )

    if weakest_excess_value < 0:
        reasons.append("At least one linked run underperformed the benchmark.")
        reasons.append(
            f"Weakest linked excess return was {_format_percent(weakest_excess_value)}."
        )
        reasons.append(
            f"Best validation excess return was {_format_percent(best_validation_value)}."
        )
        return EvidenceLabel("mixed", reasons)

    if low_trade_count:
        reasons.append("Validation is positive, but thin trade counts make the evidence fragile.")
        reasons.append(
            f"Best validation excess return was {_format_percent(best_validation_value)}."
        )
        return EvidenceLabel("weak", reasons)

    return EvidenceLabel(
        "promising",
        [
            "Validation evidence beat the benchmark.",
            "No linked run underperformed the benchmark on excess return.",
            f"Best validation excess return was {_format_percent(best_validation_value)}.",
        ],
    )


def label_portfolio_evidence(records: list[dict]) -> EvidenceLabel:
    """Classify linked portfolio evidence with deliberately conservative rules.

    Portfolio evidence has a slightly different shape than a single-symbol
    strategy run: we care about allocation breadth, drawdown, and whether a
    per-symbol data trust report exists before treating the comparison as
    promising.
    """

    if not records:
        return EvidenceLabel("no_evidence", ["No linked portfolio run evidence exists yet."])

    best_excess = _best_record(records, "excess_total_return")
    best_excess_value = _numeric(best_excess.get("excess_total_return"))
    underperformer_count = sum(1 for record in records if _numeric(record.get("excess_total_return")) < 0)
    large_drawdown_count = sum(
        1 for record in records if _numeric(record.get("max_drawdown")) <= LARGE_DRAWDOWN
    )
    trust_report_exists = portfolio_data_trust_report_exists(records)

    if best_excess_value <= 0:
        return EvidenceLabel(
            "rejected",
            [
                "No linked portfolio run beat the benchmark on excess return.",
                f"Best excess return was {_format_percent(best_excess_value)}.",
            ],
        )

    reasons: list[str] = []
    if len(records) < MIN_PORTFOLIO_VARIANTS:
        reasons.append(
            f"Only {len(records)} linked portfolio run(s) exist; compare at least {MIN_PORTFOLIO_VARIANTS} variants."
        )
    if len(records) > MAX_PORTFOLIO_VARIANTS:
        reasons.append(
            f"{len(records)} linked portfolio runs exist; summarize a narrower candidate set before choosing."
        )
    if not trust_report_exists:
        reasons.append("No portfolio data trust report was found beside linked metadata.")
    if best_excess_value < MARGINAL_EXCESS_RETURN:
        reasons.append(
            f"Best excess return is only {_format_percent(best_excess_value)}, which is marginal."
        )

    if underperformer_count or large_drawdown_count:
        if underperformer_count:
            reasons.append(f"{underperformer_count} linked portfolio run(s) underperformed the benchmark.")
        if large_drawdown_count:
            reasons.append(
                f"{large_drawdown_count} linked portfolio run(s) had drawdown at or below {_format_percent(LARGE_DRAWDOWN)}."
            )
        return EvidenceLabel("mixed", reasons)

    if reasons:
        return EvidenceLabel("weak", reasons)

    return EvidenceLabel(
        "promising",
        [
            "Multiple linked portfolio runs beat the benchmark.",
            "No linked portfolio run underperformed the benchmark.",
            "A portfolio data trust report exists for linked evidence.",
        ],
    )


def portfolio_data_trust_report_exists(records: list[dict]) -> bool:
    for record in records:
        metadata_path = record.get("metadata_path")
        if not metadata_path:
            continue
        if (Path(str(metadata_path)).parent / PORTFOLIO_DATA_TRUST_REPORT_FILENAME).exists():
            return True
    return False


def _best_record(records: list[dict], field: str) -> dict:
    return max(records, key=lambda record: _numeric(record.get(field)))


def _weakest_record(records: list[dict], field: str) -> dict:
    return min(records, key=lambda record: _numeric(record.get(field), missing=float("inf")))


def _low_trade_count(records: list[dict], *, min_trades: int) -> int:
    return sum(1 for record in records if _numeric(record.get("trade_count"), missing=0) < min_trades)


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
