from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.portfolio_batch import (
    PORTFOLIO_BATCH_MANIFEST_FILENAME,
    PORTFOLIO_BATCH_MANIFEST_SCHEMA_VERSION,
    plan_portfolio_batch,
    portfolio_batch_manifest_path,
)


class PortfolioBatchTests(unittest.TestCase):
    def test_plan_portfolio_batch_writes_valid_manifest_without_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            portfolios_dir = workspace / "candidates"
            output_dir = workspace / "batch"
            portfolios_dir.mkdir()
            _write_portfolio(portfolios_dir / "candidate_a.json", portfolio_id="candidate_a")
            _write_portfolio(portfolios_dir / "candidate_b.json", portfolio_id="candidate_b")

            manifest = plan_portfolio_batch(
                portfolios_dir=portfolios_dir,
                output_dir=output_dir,
                initial_cash=50_000,
                cost_preset="retail-liquid",
                experiments_path=workspace / "experiments.jsonl",
                index_path=workspace / "research_index.jsonl",
                created_at_utc="2026-07-18T00:00:00Z",
            )

            manifest_path = output_dir / PORTFOLIO_BATCH_MANIFEST_FILENAME
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest.schema_version, PORTFOLIO_BATCH_MANIFEST_SCHEMA_VERSION)
            self.assertEqual(payload["schema_version"], PORTFOLIO_BATCH_MANIFEST_SCHEMA_VERSION)
            self.assertEqual(payload["item_count"], 2)
            self.assertEqual([item["portfolio_id"] for item in payload["items"]], ["candidate_a", "candidate_b"])
            self.assertEqual(payload["items"][0]["status"], "planned")
            self.assertIn("portfolio-run", payload["items"][0]["command"])
            self.assertIn("--cost-preset", payload["items"][0]["command"])
            self.assertIn("retail-liquid", payload["items"][0]["command"])
            self.assertFalse((output_dir / "runs" / "candidate_a" / "portfolio_metadata.json").exists())
            self.assertTrue(manifest_path.read_text(encoding="utf-8").endswith("\n"))

    def test_portfolio_batch_manifest_path_uses_standard_filename(self) -> None:
        self.assertEqual(
            portfolio_batch_manifest_path("artifacts/batch"),
            Path("artifacts/batch") / PORTFOLIO_BATCH_MANIFEST_FILENAME,
        )

    def test_plan_portfolio_batch_rejects_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            portfolios_dir = Path(temp_dir) / "empty"
            portfolios_dir.mkdir()

            with self.assertRaisesRegex(ValueError, "No portfolio JSON"):
                plan_portfolio_batch(portfolios_dir=portfolios_dir, output_dir=Path(temp_dir) / "batch")

    def test_plan_portfolio_batch_validates_specs_before_writing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            portfolios_dir = workspace / "candidates"
            output_dir = workspace / "batch"
            portfolios_dir.mkdir()
            (portfolios_dir / "bad.json").write_text('{"schema_version": "portfolio_plan.v1"}\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "portfolio_id"):
                plan_portfolio_batch(portfolios_dir=portfolios_dir, output_dir=output_dir)

            self.assertFalse((output_dir / PORTFOLIO_BATCH_MANIFEST_FILENAME).exists())

    def test_plan_portfolio_batch_refuses_to_overwrite_manifest_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            portfolios_dir = workspace / "candidates"
            output_dir = workspace / "batch"
            portfolios_dir.mkdir()
            _write_portfolio(portfolios_dir / "candidate_a.json", portfolio_id="candidate_a")
            plan_portfolio_batch(portfolios_dir=portfolios_dir, output_dir=output_dir)

            with self.assertRaisesRegex(FileExistsError, "already exists"):
                plan_portfolio_batch(portfolios_dir=portfolios_dir, output_dir=output_dir)

            replacement = plan_portfolio_batch(portfolios_dir=portfolios_dir, output_dir=output_dir, force=True)
            self.assertEqual(replacement.item_count, 1)


def _write_portfolio(path: Path, *, portfolio_id: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "portfolio_plan.v1",
                "portfolio_id": portfolio_id,
                "name": portfolio_id.replace("_", " ").title(),
                "description": "Static two-symbol candidate.",
                "symbols": [
                    {"symbol": "QQQ", "data": "QQQ.csv", "target_weight": 0.60},
                    {"symbol": "SPY", "data": "SPY.csv", "target_weight": 0.40},
                ],
                "rebalance": {"frequency": "monthly"},
                "benchmark": {"symbol": "SPY", "data": "SPY.csv"},
            }
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
