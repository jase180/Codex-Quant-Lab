"""Reusable transaction cost presets for CLI research runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostAssumptions:
    preset: str
    commission_fixed: float
    commission_rate: float
    slippage_bps: float


COST_PRESETS: dict[str, CostAssumptions] = {
    "none": CostAssumptions(
        preset="none",
        commission_fixed=0.0,
        commission_rate=0.0,
        slippage_bps=0.0,
    ),
    "retail-liquid": CostAssumptions(
        preset="retail-liquid",
        commission_fixed=0.0,
        commission_rate=0.0005,
        slippage_bps=5.0,
    ),
    "retail-conservative": CostAssumptions(
        preset="retail-conservative",
        commission_fixed=0.0,
        commission_rate=0.001,
        slippage_bps=10.0,
    ),
    "high-friction": CostAssumptions(
        preset="high-friction",
        commission_fixed=1.0,
        commission_rate=0.002,
        slippage_bps=25.0,
    ),
}


def resolve_cost_assumptions(
    *,
    cost_preset: str,
    commission_fixed: float | None,
    commission_rate: float | None,
    slippage_bps: float | None,
) -> CostAssumptions:
    try:
        preset = COST_PRESETS[cost_preset]
    except KeyError as exc:
        raise ValueError(f"unknown cost preset: {cost_preset}") from exc

    return CostAssumptions(
        preset=cost_preset,
        commission_fixed=preset.commission_fixed if commission_fixed is None else float(commission_fixed),
        commission_rate=preset.commission_rate if commission_rate is None else float(commission_rate),
        slippage_bps=preset.slippage_bps if slippage_bps is None else float(slippage_bps),
    )
