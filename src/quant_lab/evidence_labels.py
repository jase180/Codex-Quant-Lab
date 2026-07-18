"""Deterministic evidence labels for linked research runs."""

from __future__ import annotations

from dataclasses import dataclass


VALIDATION_RUN_TYPES = {"test_selected_run", "walk_forward_test_run"}


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
