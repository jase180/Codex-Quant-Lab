"""Campaign-safe strategy template metadata.

Campaign providers need a small amount of strategy-template metadata before a
proposal is executable: which parameters a template accepts, and which
conceptual strategy family it belongs to for opportunity-thesis matching.
Keeping that mapping in one module avoids provider context and validator drift
as new templates become campaign-safe.
"""

from __future__ import annotations


SUPPORTED_CAMPAIGN_TEMPLATE_PARAMETERS = {
    "sma-long-cash": {"sma_length"},
    "ema-trend-follow": set(),
    "rsi-reversion": set(),
    "breakout-trend": set(),
    "calendar-month-end": set(),
}
CAMPAIGN_TEMPLATE_STRATEGY_FAMILIES = {
    "sma-long-cash": "trend_following",
    "ema-trend-follow": "trend_following",
    "rsi-reversion": "mean_reversion",
    "breakout-trend": "trend_following",
    "calendar-month-end": "calendar_seasonality",
}


def supported_campaign_template_parameters(template: str) -> set[str]:
    return set(SUPPORTED_CAMPAIGN_TEMPLATE_PARAMETERS.get(template, set()))


def campaign_template_strategy_family(template: str) -> str | None:
    return CAMPAIGN_TEMPLATE_STRATEGY_FAMILIES.get(template)


def campaign_strategy_families_for_templates(templates: list[str]) -> set[str]:
    families: set[str] = set()
    for template in templates:
        family = campaign_template_strategy_family(template)
        if family is not None:
            families.add(family)
    return families
