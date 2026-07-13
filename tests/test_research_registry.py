from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.research_registry import (  # noqa: E402
    append_experiment_record,
    create_experiment_record,
    experiment_from_dict,
    filter_experiments,
    load_experiments,
    next_experiment_id,
    normalize_tags,
    replace_experiment_record,
    update_experiment_record,
)


class ResearchRegistryTests(unittest.TestCase):
    def test_create_append_and_load_experiment_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "experiments.jsonl"
            record = create_experiment_record(
                experiment_id="EXP-001",
                title="QQQ SMA sweep",
                hypothesis="Shorter moving averages may improve risk-adjusted returns.",
                tags=["QQQ", "sma,trend"],
                strategy_path="data/strategies/sma.json",
                data_path="data/cache/qqq.csv",
                notes="Start with broad parameters.",
                created_at_utc="2026-01-01T00:00:00Z",
            )

            append_experiment_record(record, registry_path)
            loaded = load_experiments(registry_path)

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].experiment_id, "EXP-001")
            self.assertEqual(loaded[0].tags, ["qqq", "sma", "trend"])
            self.assertEqual(loaded[0].linked_runs, [])
            self.assertEqual(next_experiment_id(loaded), "EXP-002")

    def test_rejects_unknown_fields_in_experiment_json(self) -> None:
        payload = create_experiment_record(
            experiment_id="EXP-001",
            title="Valid",
            hypothesis="A valid hypothesis.",
            created_at_utc="2026-01-01T00:00:00Z",
        ).to_dict()
        payload["unexpected"] = True

        with self.assertRaisesRegex(ValueError, "unknown fields"):
            experiment_from_dict(payload)

    def test_duplicate_experiment_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "experiments.jsonl"
            record = create_experiment_record(
                experiment_id="EXP-001",
                title="Valid",
                hypothesis="A valid hypothesis.",
                created_at_utc="2026-01-01T00:00:00Z",
            )
            append_experiment_record(record, registry_path)

            with self.assertRaisesRegex(ValueError, "already exists"):
                append_experiment_record(record, registry_path)

    def test_filter_experiments_by_status_and_tag(self) -> None:
        planned = create_experiment_record(
            experiment_id="EXP-001",
            title="Planned",
            hypothesis="A valid hypothesis.",
            tags=["trend"],
            created_at_utc="2026-01-01T00:00:00Z",
        )
        running = create_experiment_record(
            experiment_id="EXP-002",
            title="Running",
            hypothesis="Another valid hypothesis.",
            status="running",
            tags=["mean-reversion"],
            created_at_utc="2026-01-02T00:00:00Z",
        )

        self.assertEqual(filter_experiments([planned, running], status="running"), [running])
        self.assertEqual(filter_experiments([planned, running], tag="TREND"), [planned])
        self.assertEqual(normalize_tags(["QQQ, SMA", "qqq"]), ["qqq", "sma"])

    def test_update_and_replace_experiment_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "experiments.jsonl"
            original = create_experiment_record(
                experiment_id="EXP-001",
                title="Valid",
                hypothesis="A valid hypothesis.",
                tags=["trend"],
                created_at_utc="2026-01-01T00:00:00Z",
            )
            append_experiment_record(original, registry_path)

            updated = update_experiment_record(
                original,
                status="completed",
                decision="Do a tighter follow-up sweep.",
                notes="Result was promising but sparse.",
                add_tags=["follow-up", "trend"],
            )
            replace_experiment_record(updated, registry_path)
            loaded = load_experiments(registry_path)

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].status, "completed")
            self.assertEqual(loaded[0].decision, "Do a tighter follow-up sweep.")
            self.assertEqual(loaded[0].notes, "Result was promising but sparse.")
            self.assertEqual(loaded[0].tags, ["trend", "follow-up"])

    def test_load_reports_invalid_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "experiments.jsonl"
            registry_path.write_text(json.dumps({"not": "valid"}) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing fields"):
                load_experiments(registry_path)


if __name__ == "__main__":
    unittest.main()
