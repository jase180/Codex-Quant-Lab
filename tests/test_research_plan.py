from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.research_plan import (  # noqa: E402
    DEFAULT_RECOMMENDED_STEPS,
    RESEARCH_PLAN_SCHEMA_VERSION,
    create_research_plan,
    load_research_plan,
    normalize_plan_tags,
    render_research_plan_markdown,
    save_research_plan,
)


class ResearchPlanTests(unittest.TestCase):
    def test_create_research_plan_normalizes_fields(self) -> None:
        plan = create_research_plan(
            title="  QQQ SMA check  ",
            hypothesis="  Crossover may reduce drawdown.  ",
            strategy_path="data/strategies/qqq_sma.json",
            data_path="data/cache/qqq.csv",
            symbol=" qqq ",
            experiment_id=" EXP-001 ",
            output_dir="artifacts/research/qqq_sma",
            tags=["QQQ", "sma, trend", "sma"],
            created_at_utc="2026-07-17T00:00:00Z",
        )

        self.assertEqual(plan.schema_version, RESEARCH_PLAN_SCHEMA_VERSION)
        self.assertEqual(plan.title, "QQQ SMA check")
        self.assertEqual(plan.hypothesis, "Crossover may reduce drawdown.")
        self.assertEqual(plan.symbol, "QQQ")
        self.assertEqual(plan.experiment_id, "EXP-001")
        self.assertEqual(plan.tags, ["qqq", "sma", "trend"])
        self.assertEqual(plan.recommended_steps, list(DEFAULT_RECOMMENDED_STEPS))

    def test_save_research_plan_writes_stable_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "research" / "qqq_sma"
            plan = create_research_plan(
                title="QQQ SMA check",
                hypothesis="Crossover may reduce drawdown.",
                strategy_path="data/strategies/qqq_sma.json",
                data_path="data/cache/qqq.csv",
                symbol="QQQ",
                experiment_id="EXP-001",
                output_dir=output_dir,
                tags=["sma"],
                created_at_utc="2026-07-17T00:00:00Z",
            )

            json_path, markdown_path = save_research_plan(plan)

            payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "research_plan.v1")
            self.assertEqual(payload["title"], "QQQ SMA check")
            self.assertEqual(payload["output_dir"], str(output_dir))
            self.assertEqual(payload["recommended_steps"][0], "baseline")
            self.assertTrue(Path(json_path).read_text(encoding="utf-8").endswith("\n"))

            markdown = Path(markdown_path).read_text(encoding="utf-8")
            self.assertIn("# QQQ SMA check", markdown)
            self.assertIn("Crossover may reduce drawdown.", markdown)
            self.assertIn("- Strategy: `data/strategies/qqq_sma.json`", markdown)
            self.assertIn("- baseline", markdown)
            self.assertIn("This plan organizes research.", markdown)

    def test_load_research_plan_round_trips_saved_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = create_research_plan(
                title="QQQ SMA check",
                hypothesis="Crossover may reduce drawdown.",
                strategy_path="data/strategies/qqq_sma.json",
                data_path="data/cache/qqq.csv",
                symbol="QQQ",
                experiment_id="EXP-001",
                output_dir=Path(temp_dir),
                created_at_utc="2026-07-17T00:00:00Z",
            )
            json_path, _ = save_research_plan(plan)

            loaded = load_research_plan(json_path)

            self.assertEqual(loaded, plan)

    def test_create_research_plan_rejects_empty_required_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "title"):
            create_research_plan(
                title=" ",
                hypothesis="Crossover may reduce drawdown.",
                strategy_path="data/strategies/qqq_sma.json",
                data_path="data/cache/qqq.csv",
                symbol="QQQ",
                experiment_id="EXP-001",
                output_dir="artifacts/research/qqq_sma",
            )

    def test_normalize_plan_tags_splits_commas_and_deduplicates(self) -> None:
        self.assertEqual(normalize_plan_tags([" QQQ ", "sma,Trend", "SMA"]), ["qqq", "sma", "trend"])

    def test_render_research_plan_markdown_handles_empty_tags(self) -> None:
        plan = create_research_plan(
            title="QQQ SMA check",
            hypothesis="Crossover may reduce drawdown.",
            strategy_path="data/strategies/qqq_sma.json",
            data_path="data/cache/qqq.csv",
            symbol="QQQ",
            experiment_id="EXP-001",
            output_dir="artifacts/research/qqq_sma",
            created_at_utc="2026-07-17T00:00:00Z",
        )

        markdown = render_research_plan_markdown(plan)

        self.assertIn("## Tags\n\n- none", markdown)


if __name__ == "__main__":
    unittest.main()
