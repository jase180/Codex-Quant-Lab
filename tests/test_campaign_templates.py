from __future__ import annotations

import unittest

from quant_lab.campaign_templates import (
    campaign_strategy_families_for_templates,
    campaign_template_strategy_family,
    supported_campaign_template_parameters,
)


class CampaignTemplatesTest(unittest.TestCase):
    def test_campaign_template_metadata_is_shared_by_context_and_validation(self) -> None:
        self.assertEqual("trend_following", campaign_template_strategy_family("sma-long-cash"))
        self.assertEqual("trend_following", campaign_template_strategy_family("ema-trend-follow"))
        self.assertEqual("mean_reversion", campaign_template_strategy_family("rsi-reversion"))
        self.assertEqual("trend_following", campaign_template_strategy_family("breakout-trend"))
        self.assertEqual("calendar_seasonality", campaign_template_strategy_family("calendar-month-end"))
        self.assertIsNone(campaign_template_strategy_family("not-campaign-safe"))
        self.assertEqual({"sma_length"}, supported_campaign_template_parameters("sma-long-cash"))
        self.assertEqual(set(), supported_campaign_template_parameters("rsi-reversion"))
        self.assertEqual(set(), supported_campaign_template_parameters("breakout-trend"))
        self.assertEqual(set(), supported_campaign_template_parameters("calendar-month-end"))
        self.assertEqual(set(), supported_campaign_template_parameters("not-campaign-safe"))
        self.assertEqual(
            {"trend_following", "mean_reversion", "calendar_seasonality"},
            campaign_strategy_families_for_templates(
                ["sma-long-cash", "ema-trend-follow", "rsi-reversion", "calendar-month-end"]
            ),
        )


if __name__ == "__main__":
    unittest.main()
