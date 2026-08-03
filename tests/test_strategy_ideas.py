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
            }
        ],
        "suggested_validation": ["Run one prespecified validation path."],
        "references": ["Conceptual reference"],
        "engine_can_currently_execute": executable,
        "execution_notes": "Fixture notes.",
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


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

    def test_load_strategy_catalog_requires_conceptual_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir)
            _write_json(catalog_dir / "trend.json", _catalog_entry("trend_following"))

            entries = load_strategy_catalog(catalog_dir)

        self.assertEqual(1, len(entries))
        self.assertEqual("trend_following", entries[0].family_id)
        self.assertTrue(entries[0].engine_can_currently_execute)

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

            suggestion = suggest_strategy_idea(catalog_dir=catalog_dir, conclusions_dir=conclusions_dir)

        self.assertEqual("mean_reversion", suggestion.family.family_id)
        self.assertIn("trend_following", suggestion.excluded_families)
        self.assertIn("momentum_rotation (not executable)", suggestion.excluded_families)
        self.assertTrue(suggestion.draft_experiment_config["requires_human_approval_before_strategy_json"])
        self.assertNotIn("strategy_path", suggestion.draft_experiment_config)

    def test_cli_ideas_suggest_prints_hypothesis_and_draft_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir) / "catalog"
            conclusions_dir = Path(tmpdir) / "research"
            catalog_dir.mkdir()
            conclusions_dir.mkdir()
            _write_json(catalog_dir / "mean.json", _catalog_entry("mean_reversion", variant_id="rsi_pullback"))

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "ideas",
                        "suggest",
                        "--catalog-dir",
                        str(catalog_dir),
                        "--conclusions-dir",
                        str(conclusions_dir),
                    ]
                )

        output = stdout.getvalue()
        self.assertEqual(0, exit_code)
        self.assertIn("Selected family: Mean Reversion", output)
        self.assertIn("## Proposed Hypothesis", output)
        self.assertIn("## Draft Experiment Config", output)
        self.assertIn("No executable strategy JSON was created", output)

    def test_cli_ideas_suggest_prints_clean_message_when_catalog_is_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir) / "catalog"
            conclusions_dir = Path(tmpdir) / "research"
            catalog_dir.mkdir()
            (conclusions_dir / "exp").mkdir(parents=True)
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
                    ]
                )

        self.assertEqual(1, exit_code)
        self.assertIn("No strategy idea suggestion", stdout.getvalue())
        self.assertNotIn("Traceback", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
