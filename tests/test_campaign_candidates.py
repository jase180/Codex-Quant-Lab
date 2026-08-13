from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from quant_lab.campaign import initialize_campaign, load_campaign_state, parse_campaign_config, save_campaign_state
from quant_lab.campaign_candidates import (
    build_campaign_candidate_menu,
    save_campaign_candidate_menu,
)
from quant_lab.cli import main

def campaign_payload() -> dict:
    return {
        "schema_version": "campaign_config.v1",
        "title": "SPY drawdown-control research",
        "objective": "Find simple SPY drawdown controls that retain most long-term growth.",
        "allowed_symbols": ["SPY"],
        "allowed_templates": ["sma-long-cash", "ema-trend-follow"],
        "benchmark": "buy-and-hold",
        "data_paths": {"SPY": "data/cache/SPY_2015-01-01_2025-12-31.csv"},
        "cost_preset": "retail-liquid",
        "max_cycles": 3,
        "max_total_runs": 33,
        "max_variants_per_experiment": 3,
        "duration_minutes": 30,
        "provider": "deterministic",
    }


def expanded_campaign_payload() -> dict:
    payload = campaign_payload()
    payload["title"] = "SPY bounded opportunity expansion"
    payload["objective"] = "Test bounded non-nearby opportunity candidates."
    payload["allowed_templates"] = ["rsi-reversion", "breakout-trend"]
    payload["max_cycles"] = 2
    payload["max_total_runs"] = 22
    payload["max_variants_per_experiment"] = 1
    return payload


def capped_multi_symbol_campaign_payload() -> dict:
    payload = expanded_campaign_payload()
    payload["allowed_symbols"] = ["SPY", "QQQ", "IWM", "TLT"]
    payload["data_paths"] = {
        "SPY": "data/cache/SPY_2015-01-01_2025-12-31.csv",
        "QQQ": "data/cache/QQQ_2015-01-01_2025-12-31.csv",
        "IWM": "data/cache/IWM_2015-01-01_2025-12-31.csv",
        "TLT": "data/cache/TLT_2015-01-01_2025-12-31.csv",
    }
    payload["allowed_templates"] = ["sma-long-cash", "ema-trend-follow", "rsi-reversion", "breakout-trend"]
    payload["max_candidate_menu_size"] = 6
    return payload


def temp_multi_symbol_campaign_payload(temp_dir: str) -> dict:
    payload = capped_multi_symbol_campaign_payload()
    payload["allowed_symbols"] = ["EEM", "EFA", "GLD", "IWM"]
    payload["data_paths"] = {}
    for symbol in payload["allowed_symbols"]:
        path = Path(temp_dir) / f"{symbol}.csv"
        path.write_text("date,open,high,low,close,volume\n", encoding="utf-8")
        payload["data_paths"][symbol] = str(path)
    return payload


class CampaignCandidatesTest(unittest.TestCase):
    def test_fresh_campaign_builds_candidate_menu_from_catalogs(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            menu = build_campaign_candidate_menu(config, state)

        self.assertEqual("ready", menu.status)
        self.assertGreaterEqual(len(menu.candidates), 2)
        candidate_ids = {candidate.candidate_id for candidate in menu.candidates}
        self.assertEqual(len(candidate_ids), len(menu.candidates))
        self.assertIn("spy_liquid_etf_trend_defense_price_vs_sma_trend_001", candidate_ids)
        self.assertTrue(any(candidate.strategy_template == "ema-trend-follow" for candidate in menu.candidates))
        self.assertTrue(all(candidate.projected_run_count == 11 for candidate in menu.candidates))

    def test_expanded_campaign_builds_non_nearby_candidate_menu(self) -> None:
        config = parse_campaign_config(expanded_campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            menu = build_campaign_candidate_menu(config, state)

        templates = {candidate.strategy_template for candidate in menu.candidates}
        thesis_ids = {candidate.opportunity_thesis_id for candidate in menu.candidates}
        self.assertEqual("ready", menu.status)
        self.assertIn("rsi-reversion", templates)
        self.assertIn("breakout-trend", templates)
        self.assertIn("retail_pullback_liquidity", thesis_ids)
        self.assertIn("liquid_etf_trend_defense", thesis_ids)
        self.assertIn("etf_flow_persistence", thesis_ids)
        self.assertTrue(any(candidate.template_id == "etf_flow_breakout_continuation" for candidate in menu.candidates))

    def test_capped_campaign_shortlists_diverse_candidate_menu(self) -> None:
        config = parse_campaign_config(capped_multi_symbol_campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            menu = build_campaign_candidate_menu(config, state)

        symbols = {candidate.symbol for candidate in menu.candidates}
        templates = {candidate.template_id for candidate in menu.candidates}
        self.assertEqual("ready", menu.status)
        self.assertEqual(6, len(menu.candidates))
        self.assertGreater(menu.total_candidates_before_shortlist, len(menu.candidates))
        self.assertGreaterEqual(len(symbols), 3)
        self.assertGreaterEqual(len(templates), 3)
        self.assertIn("capped at 6", menu.shortlist_policy)

    def test_seeded_campaign_filters_forbidden_completed_titles(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            state = replace(
                state,
                cycle_number=2,
                completed_experiments=[
                    {"title": "SPY SMA 200 long/cash campaign baseline"},
                    {"title": "SPY EMA 50 RSI trend-follow campaign follow-up"},
                ],
                do_not_repeat=[
                    "Do not keep widening this branch until the contradicting evidence is explained.",
                    "Do not repeat unchanged rejected experiment: SPY SMA 200 long/cash campaign baseline.",
                ],
            )
            menu = build_campaign_candidate_menu(config, state)

        titles = {candidate.title for candidate in menu.candidates}
        rejected_reasons = [item.reason for item in menu.rejected_candidates]
        self.assertEqual("SEARCH_SPACE_EXHAUSTED", menu.status)
        self.assertNotIn("SPY SMA 200 long/cash campaign baseline", titles)
        self.assertNotIn("SPY EMA 50 RSI trend-follow campaign follow-up", titles)
        self.assertTrue(any("forbidden completed title" in reason for reason in rejected_reasons))
        self.assertTrue(any("violates do_not_repeat" in reason for reason in rejected_reasons))

    def test_seeded_campaign_filters_weakened_thesis_template_branch(self) -> None:
        config = parse_campaign_config(expanded_campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            state = replace(
                state,
                do_not_repeat=[
                    "Do not repeat weakened branch: opportunity=retail_pullback_liquidity; template=rsi-reversion."
                ],
            )
            menu = build_campaign_candidate_menu(config, state)

        templates_by_thesis = {
            (candidate.opportunity_thesis_id, candidate.strategy_template)
            for candidate in menu.candidates
        }
        rejected_reasons = [item.reason for item in menu.rejected_candidates]
        self.assertNotIn(("retail_pullback_liquidity", "rsi-reversion"), templates_by_thesis)
        self.assertIn(("liquid_etf_trend_defense", "breakout-trend"), templates_by_thesis)
        self.assertTrue(any("violates do_not_repeat" in reason for reason in rejected_reasons))

    def test_weakened_branch_filter_does_not_block_same_template_under_new_thesis(self) -> None:
        config = parse_campaign_config(expanded_campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            state = replace(
                state,
                do_not_repeat=[
                    "Do not repeat weakened branch: opportunity=liquid_etf_trend_defense; template=breakout-trend."
                ],
            )
            menu = build_campaign_candidate_menu(config, state)

        templates_by_thesis = {
            (candidate.opportunity_thesis_id, candidate.strategy_template)
            for candidate in menu.candidates
        }
        self.assertNotIn(("liquid_etf_trend_defense", "breakout-trend"), templates_by_thesis)
        self.assertIn(("etf_flow_persistence", "breakout-trend"), templates_by_thesis)

    def test_seeded_campaign_ranking_penalizes_repeated_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = parse_campaign_config(temp_multi_symbol_campaign_payload(temp_dir))
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            state = replace(
                state,
                completed_experiments=[
                    {
                        "title": "EEM RSI Pullback Reversion",
                        "symbol": "EEM",
                        "strategy_template": "rsi-reversion",
                        "opportunity_thesis_id": "retail_pullback_liquidity",
                    }
                ],
                do_not_repeat=[
                    "Do not repeat weakened branch: opportunity=retail_pullback_liquidity; template=rsi-reversion."
                ],
            )
            menu = build_campaign_candidate_menu(config, state)

        self.assertEqual("ready", menu.status)
        self.assertNotEqual("EEM", menu.candidates[0].symbol)
        self.assertGreaterEqual(len({candidate.symbol for candidate in menu.candidates[:4]}), 3)

    def test_save_campaign_candidate_menu_writes_json_and_markdown(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = initialize_campaign(config, Path(temp_dir) / "campaign")
            state = load_campaign_state(paths.state_path)
            menu = build_campaign_candidate_menu(config, state)
            json_path, markdown_path = save_campaign_candidate_menu(menu, Path(paths.cycles_dir) / "cycle_001")
            payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
            markdown = Path(markdown_path).read_text(encoding="utf-8")

        self.assertEqual("campaign_candidate_menu.v1", payload["schema_version"])
        self.assertIn("total_candidates_before_shortlist", payload)
        self.assertIn("shortlist_policy", payload)
        self.assertIn("Campaign Candidate Menu", markdown)
        self.assertIn("Candidate Menu", markdown)

    def test_campaign_candidates_command_writes_next_cycle_menu(self) -> None:
        config = parse_campaign_config(campaign_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            campaign_dir = Path(temp_dir) / "campaign"
            paths = initialize_campaign(config, campaign_dir)
            state = replace(load_campaign_state(paths.state_path), cycle_number=2)
            save_campaign_state(state, campaign_dir, config=config)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["campaign", "candidates", "--campaign", str(campaign_dir)])

            menu_path = campaign_dir / "cycles" / "cycle_003" / "candidate_menu.json"
            markdown_path = campaign_dir / "cycles" / "cycle_003" / "candidate_menu.md"
            menu_exists = menu_path.exists()
            markdown_exists = markdown_path.exists()
            output = stdout.getvalue()

        self.assertEqual(0, exit_code)
        self.assertTrue(menu_exists)
        self.assertTrue(markdown_exists)
        self.assertIn("candidate_menu:", output)
        self.assertIn("status:", output)


if __name__ == "__main__":
    unittest.main()
