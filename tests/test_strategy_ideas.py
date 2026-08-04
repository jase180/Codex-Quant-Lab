from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.cli import main
from quant_lab.strategy_ideas import load_strategy_catalog, suggest_strategy_idea


def _catalog_entry(
    family_id: str,
    *,
    executable: bool = True,
    variant_id: str | None = None,
    matching_terms: list[str] | None = None,
) -> dict:
    variant_id = variant_id or f"{family_id}_variant"
    return {
        "schema_version": "strategy_catalog_entry.v1",
        "family_id": family_id,
        "name": family_id.replace("_", " ").title(),
        "rationale": "Test one conceptual strategy family.",
        "expected_benefit": "Improve a prespecified investment objective.",
        "failure_modes": ["Can fail after costs."],
        "required_project_capabilities": ["daily OHLCV data"],
        "canonical_variants": [
            {
                "variant_id": variant_id,
                "name": variant_id.replace("_", " ").title(),
                "description": "Conceptual variant only.",
                "matching_terms": matching_terms or [variant_id.replace("_", " ")],
                "hypothesis_template": f"{family_id} may improve the prespecified objective.",
                "primary_metric": "sharpe",
                "benchmark": "buy-and-hold",
                "minimum_acceptable_performance": "Improve Sharpe versus buy-and-hold after costs.",
                "success_criteria": [
                    {
                        "name": "risk_adjusted_return",
                        "metric": "sharpe",
                        "comparison": "strategy_vs_benchmark_delta",
                        "operator": ">",
                        "threshold": 0.0,
                    }
                ],
                "engine_can_currently_execute": executable,
                "research_priority": "core",
                "capability_status": "executable_now" if executable else "unsupported_now",
                "next_action": "run_after_human_approval" if executable else "defer_until_capability_exists",
            }
        ],
        "suggested_validation": ["Run one prespecified validation path."],
        "references": ["Conceptual reference"],
        "engine_can_currently_execute": executable,
        "execution_notes": "Fixture notes.",
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _experiment_record(
    *,
    experiment_id: str,
    title: str,
    hypothesis: str,
    strategy_path: str,
    rationale: str,
    next_action: str,
) -> dict:
    return {
        "experiment_schema_version": "experiment.v1",
        "experiment_id": experiment_id,
        "created_at_utc": "2026-08-04T00:00:00Z",
        "title": title,
        "hypothesis": hypothesis,
        "status": "completed",
        "tags": ["portfolio", "allocation"],
        "strategy_path": strategy_path,
        "data_path": "data/cache/SPY.csv",
        "linked_runs": [],
        "decision": f"reject: {rationale}",
        "decision_record": {
            "outcome": "reject",
            "decided_at_utc": "2026-08-04T00:01:00Z",
            "rationale": rationale,
            "supporting_run": None,
            "contradicting_run": None,
            "next_action": next_action,
        },
        "notes": "Prespecified portfolio allocation test.",
    }


class StrategyIdeasTest(unittest.TestCase):
    def test_tracked_strategy_catalog_has_broad_idea_library(self) -> None:
        catalog_dir = Path(__file__).resolve().parents[1] / "data" / "strategy_catalog"

        entries = load_strategy_catalog(catalog_dir)
        variant_count = sum(len(entry.canonical_variants) for entry in entries)
        executable_variant_count = sum(
            1
            for entry in entries
            for variant in entry.canonical_variants
            if variant.get("engine_can_currently_execute")
        )

        self.assertGreaterEqual(len(entries), 10)
        self.assertGreaterEqual(variant_count, 30)
        self.assertGreaterEqual(executable_variant_count, 5)
        for entry in entries:
            for variant in entry.canonical_variants:
                self.assertIn(variant["research_priority"], {"core", "secondary", "later"})
                self.assertIn(
                    variant["capability_status"],
                    {
                        "executable_now",
                        "small_schema_extension_required",
                        "data_extension_required",
                        "portfolio_extension_required",
                        "unsupported_now",
                    },
                )
                self.assertTrue(variant["next_action"])

    def test_load_strategy_catalog_requires_conceptual_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir)
            _write_json(catalog_dir / "trend.json", _catalog_entry("trend_following"))

            entries = load_strategy_catalog(catalog_dir)

        self.assertEqual(1, len(entries))
        self.assertEqual("trend_following", entries[0].family_id)
        self.assertTrue(entries[0].engine_can_currently_execute)

    def test_load_strategy_catalog_rejects_inconsistent_variant_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir)
            payload = _catalog_entry("mean_reversion", executable=False)
            payload["canonical_variants"][0]["capability_status"] = "executable_now"
            _write_json(catalog_dir / "mean.json", payload)

            with self.assertRaisesRegex(ValueError, "marked executable_now but is not executable"):
                load_strategy_catalog(catalog_dir)

    def test_suggest_excludes_do_not_repeat_idea_and_keeps_conceptual_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            catalog_dir = root / "catalog"
            conclusions_dir = root / "research"
            catalog_dir.mkdir()
            (conclusions_dir / "exp").mkdir(parents=True)

            _write_json(
                catalog_dir / "trend.json",
                _catalog_entry(
                    "trend_following",
                    variant_id="sma_long_cash",
                    matching_terms=["sma long cash", "200-day sma"],
                ),
            )
            _write_json(catalog_dir / "mean.json", _catalog_entry("mean_reversion", variant_id="rsi_pullback"))
            _write_json(catalog_dir / "rotation.json", _catalog_entry("momentum_rotation", executable=False))
            _write_json(
                conclusions_dir / "exp" / "experiment_conclusion.json",
                {
                    "schema_version": "experiment_conclusion.v1",
                    "do_not_repeat": ["Do not rerun the same 200-day SMA long/cash idea unchanged."],
                    "next_research_prompt": {"constraints": []},
                },
            )

            suggestion = suggest_strategy_idea(
                catalog_dir=catalog_dir,
                conclusions_dir=conclusions_dir,
                experiments_path=root / "missing_experiments.jsonl",
                handoffs_dir=root / "missing_handoffs",
            )

        self.assertEqual("mean_reversion", suggestion.family.family_id)
        self.assertIn("trend_following", suggestion.excluded_families)
        self.assertIn("momentum_rotation (not executable)", suggestion.excluded_families)
        self.assertTrue(suggestion.draft_experiment_config["requires_human_approval_before_strategy_json"])
        self.assertEqual("core", suggestion.draft_experiment_config["research_priority"])
        self.assertEqual("executable_now", suggestion.draft_experiment_config["capability_status"])
        self.assertNotIn("strategy_path", suggestion.draft_experiment_config)

    def test_cli_ideas_suggest_prints_hypothesis_and_draft_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir) / "catalog"
            conclusions_dir = Path(tmpdir) / "research"
            experiments_path = Path(tmpdir) / "experiments.jsonl"
            handoffs_dir = Path(tmpdir) / "handoffs"
            catalog_dir.mkdir()
            conclusions_dir.mkdir()
            handoffs_dir.mkdir()
            _write_json(catalog_dir / "mean.json", _catalog_entry("mean_reversion", variant_id="rsi_pullback"))
            experiments_path.write_text("", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "ideas",
                        "suggest",
                        "--catalog-dir",
                        str(catalog_dir),
                        "--conclusions-dir",
                        str(conclusions_dir),
                        "--experiments-path",
                        str(experiments_path),
                        "--handoffs-dir",
                        str(handoffs_dir),
                    ]
                )

        output = stdout.getvalue()
        self.assertEqual(0, exit_code)
        self.assertIn("Selected family: Mean Reversion", output)
        self.assertIn("Prior research records read: 0", output)
        self.assertIn("## Proposed Hypothesis", output)
        self.assertIn("## Draft Experiment Config", output)
        self.assertIn("No executable strategy JSON was created", output)

    def test_suggest_excludes_portfolio_family_from_registry_decision_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            catalog_dir = root / "catalog"
            conclusions_dir = root / "research"
            handoffs_dir = root / "handoffs"
            experiments_path = root / "experiments.jsonl"
            catalog_dir.mkdir()
            conclusions_dir.mkdir()
            handoffs_dir.mkdir()
            _write_json(
                catalog_dir / "portfolio.json",
                _catalog_entry(
                    "portfolio_allocation",
                    variant_id="equal_weight_two_asset",
                    matching_terms=["portfolio allocation", "static allocation", "60 40"],
                ),
            )
            _write_json(catalog_dir / "stat.json", _catalog_entry("statistical_reversion", variant_id="rolling_low_reversion"))
            experiments_path.write_text(
                json.dumps(
                    _experiment_record(
                        experiment_id="EXP-010",
                        title="SPY TLT static 60/40 allocation test",
                        hypothesis="A static 60% SPY and 40% TLT allocation may reduce max drawdown.",
                        strategy_path="data/portfolios/spy_tlt_static_60_40.json",
                        rationale="Strategy-hypothesis status is rejected for the exact static allocation.",
                        next_action="Do not tune SPY/TLT weights immediately.",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            suggestion = suggest_strategy_idea(
                catalog_dir=catalog_dir,
                conclusions_dir=conclusions_dir,
                experiments_path=experiments_path,
                handoffs_dir=handoffs_dir,
            )

        self.assertEqual("statistical_reversion", suggestion.family.family_id)
        self.assertIn("portfolio_allocation", suggestion.excluded_families)

    def test_cli_ideas_suggest_prints_clean_message_when_catalog_is_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir) / "catalog"
            conclusions_dir = Path(tmpdir) / "research"
            experiments_path = Path(tmpdir) / "experiments.jsonl"
            handoffs_dir = Path(tmpdir) / "handoffs"
            catalog_dir.mkdir()
            handoffs_dir.mkdir()
            (conclusions_dir / "exp").mkdir(parents=True)
            experiments_path.write_text("", encoding="utf-8")
            _write_json(catalog_dir / "mean.json", _catalog_entry("mean_reversion", variant_id="rsi_pullback"))
            _write_json(
                conclusions_dir / "exp" / "experiment_conclusion.json",
                {
                    "schema_version": "experiment_conclusion.v1",
                    "experiment": {"hypothesis": "mean reversion rsi pullback failed"},
                    "do_not_repeat": ["Do not rerun the same strategy unchanged."],
                    "next_research_prompt": {"constraints": []},
                },
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "ideas",
                        "suggest",
                        "--catalog-dir",
                        str(catalog_dir),
                        "--conclusions-dir",
                        str(conclusions_dir),
                        "--experiments-path",
                        str(experiments_path),
                        "--handoffs-dir",
                        str(handoffs_dir),
                    ]
                )

        self.assertEqual(1, exit_code)
        self.assertIn("No strategy idea suggestion", stdout.getvalue())
        self.assertNotIn("Traceback", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
