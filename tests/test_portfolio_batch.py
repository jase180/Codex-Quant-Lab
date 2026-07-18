from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.portfolio_batch import (
    PORTFOLIO_BATCH_MANIFEST_FILENAME,
    PORTFOLIO_BATCH_MANIFEST_SCHEMA_VERSION,
    PORTFOLIO_BATCH_RESULT_FILENAME,
    PORTFOLIO_BATCH_RESULT_SCHEMA_VERSION,
    PORTFOLIO_BATCH_SUMMARY_FILENAME,
    plan_portfolio_batch,
    portfolio_batch_manifest_path,
    run_portfolio_batch,
    summarize_portfolio_batch,
)
from quant_lab.research_registry import append_experiment_record, create_experiment_record


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

    def test_run_portfolio_batch_executes_manifest_and_writes_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            data_dir = workspace / "data"
            portfolios_dir = workspace / "candidates"
            output_dir = workspace / "batch"
            experiments_path = workspace / "experiments.jsonl"
            index_path = workspace / "research_index.jsonl"
            data_dir.mkdir()
            portfolios_dir.mkdir()
            _write_ohlcv(data_dir / "QQQ.csv", [100, 110, 120])
            _write_ohlcv(data_dir / "SPY.csv", [100, 100, 100])
            _write_portfolio(
                portfolios_dir / "candidate_a.json",
                portfolio_id="candidate_a",
                qqq_data=data_dir / "QQQ.csv",
                spy_data=data_dir / "SPY.csv",
            )
            _write_experiment(experiments_path)
            plan_portfolio_batch(
                portfolios_dir=portfolios_dir,
                output_dir=output_dir,
                initial_cash=10_000,
                experiments_path=experiments_path,
                index_path=index_path,
                created_at_utc="2026-07-18T00:00:00Z",
            )

            result = run_portfolio_batch(
                manifest_path=output_dir / PORTFOLIO_BATCH_MANIFEST_FILENAME,
                experiment_id="EXP-001",
                created_at_utc="2026-07-18T00:01:00Z",
            )

            result_path = output_dir / PORTFOLIO_BATCH_RESULT_FILENAME
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            index_rows = _read_jsonl(index_path)
            self.assertEqual(result.schema_version, PORTFOLIO_BATCH_RESULT_SCHEMA_VERSION)
            self.assertEqual(payload["completed_count"], 1)
            self.assertEqual(payload["failed_count"], 0)
            self.assertEqual(payload["items"][0]["status"], "completed")
            self.assertTrue(Path(payload["items"][0]["metadata_path"]).exists())
            self.assertEqual(index_rows[0]["run_type"], "portfolio_run")
            self.assertEqual(index_rows[0]["experiment_id"], "EXP-001")
            self.assertTrue(result_path.read_text(encoding="utf-8").endswith("\n"))

    def test_run_portfolio_batch_stops_after_failure_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            data_dir = workspace / "data"
            portfolios_dir = workspace / "candidates"
            output_dir = workspace / "batch"
            experiments_path = workspace / "experiments.jsonl"
            data_dir.mkdir()
            portfolios_dir.mkdir()
            _write_ohlcv(data_dir / "QQQ.csv", [100, 110, 120])
            _write_ohlcv(data_dir / "SPY.csv", [100, 100, 100])
            _write_portfolio(
                portfolios_dir / "candidate_a.json",
                portfolio_id="candidate_a",
                qqq_data=data_dir / "MISSING.csv",
                spy_data=data_dir / "SPY.csv",
            )
            _write_portfolio(
                portfolios_dir / "candidate_b.json",
                portfolio_id="candidate_b",
                qqq_data=data_dir / "QQQ.csv",
                spy_data=data_dir / "SPY.csv",
            )
            _write_experiment(experiments_path)
            plan_portfolio_batch(
                portfolios_dir=portfolios_dir,
                output_dir=output_dir,
                experiments_path=experiments_path,
                index_path=workspace / "research_index.jsonl",
            )

            result = run_portfolio_batch(
                manifest_path=output_dir / PORTFOLIO_BATCH_MANIFEST_FILENAME,
                experiment_id="EXP-001",
            )

            self.assertEqual(result.completed_count, 0)
            self.assertEqual(result.failed_count, 1)
            self.assertEqual(result.skipped_count, 1)
            self.assertEqual([item.status for item in result.items], ["failed", "skipped"])
            self.assertIn("PortfolioDataError", result.items[0].error or "")

    def test_run_portfolio_batch_can_continue_after_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            data_dir = workspace / "data"
            portfolios_dir = workspace / "candidates"
            output_dir = workspace / "batch"
            experiments_path = workspace / "experiments.jsonl"
            data_dir.mkdir()
            portfolios_dir.mkdir()
            _write_ohlcv(data_dir / "QQQ.csv", [100, 110, 120])
            _write_ohlcv(data_dir / "SPY.csv", [100, 100, 100])
            _write_portfolio(
                portfolios_dir / "candidate_a.json",
                portfolio_id="candidate_a",
                qqq_data=data_dir / "MISSING.csv",
                spy_data=data_dir / "SPY.csv",
            )
            _write_portfolio(
                portfolios_dir / "candidate_b.json",
                portfolio_id="candidate_b",
                qqq_data=data_dir / "QQQ.csv",
                spy_data=data_dir / "SPY.csv",
            )
            _write_experiment(experiments_path)
            plan_portfolio_batch(
                portfolios_dir=portfolios_dir,
                output_dir=output_dir,
                experiments_path=experiments_path,
                index_path=workspace / "research_index.jsonl",
            )

            result = run_portfolio_batch(
                manifest_path=output_dir / PORTFOLIO_BATCH_MANIFEST_FILENAME,
                experiment_id="EXP-001",
                continue_on_error=True,
            )

            self.assertEqual(result.completed_count, 1)
            self.assertEqual(result.failed_count, 1)
            self.assertEqual(result.skipped_count, 0)
            self.assertEqual([item.status for item in result.items], ["failed", "completed"])

    def test_summarize_portfolio_batch_warns_before_result_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            portfolios_dir = workspace / "candidates"
            output_dir = workspace / "batch"
            portfolios_dir.mkdir()
            _write_portfolio(portfolios_dir / "candidate_a.json", portfolio_id="candidate_a")
            _write_portfolio(portfolios_dir / "candidate_b.json", portfolio_id="candidate_b")
            plan_portfolio_batch(portfolios_dir=portfolios_dir, output_dir=output_dir)

            summary = summarize_portfolio_batch(
                manifest_path=output_dir / PORTFOLIO_BATCH_MANIFEST_FILENAME,
                max_planned_runs=1,
            )

            markdown = (output_dir / PORTFOLIO_BATCH_SUMMARY_FILENAME).read_text(encoding="utf-8")
            self.assertEqual(summary.planned_count, 2)
            self.assertEqual(summary.completed_count, 0)
            self.assertIsNone(summary.result_path)
            self.assertTrue(any("No batch result" in warning for warning in summary.warnings))
            self.assertTrue(any("Large batch" in warning for warning in summary.warnings))
            self.assertIn("# Portfolio Batch Summary", markdown)
            self.assertIn("- Planned: `2`", markdown)
            self.assertIn("## Robustness Notes", markdown)
            self.assertIn("not a full", markdown)
            self.assertIn("- no result file yet", markdown)

    def test_summarize_portfolio_batch_reports_result_counts_and_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            data_dir = workspace / "data"
            portfolios_dir = workspace / "candidates"
            output_dir = workspace / "batch"
            experiments_path = workspace / "experiments.jsonl"
            index_path = workspace / "research_index.jsonl"
            data_dir.mkdir()
            portfolios_dir.mkdir()
            _write_ohlcv(data_dir / "QQQ.csv", [100, 110, 120])
            _write_ohlcv(data_dir / "SPY.csv", [100, 100, 100])
            _write_portfolio(
                portfolios_dir / "candidate_a.json",
                portfolio_id="candidate_a",
                qqq_data=data_dir / "QQQ.csv",
                spy_data=data_dir / "SPY.csv",
            )
            _write_experiment(experiments_path)
            plan_portfolio_batch(
                portfolios_dir=portfolios_dir,
                output_dir=output_dir,
                experiments_path=experiments_path,
                index_path=index_path,
            )
            run_portfolio_batch(
                manifest_path=output_dir / PORTFOLIO_BATCH_MANIFEST_FILENAME,
                experiment_id="EXP-001",
            )

            summary = summarize_portfolio_batch(
                manifest_path=output_dir / PORTFOLIO_BATCH_MANIFEST_FILENAME,
                min_completed_runs=2,
            )

            markdown = Path(summary.summary_path).read_text(encoding="utf-8")
            self.assertEqual(summary.completed_count, 1)
            self.assertEqual(summary.failed_count, 0)
            self.assertTrue(any("Only 1 completed" in warning for warning in summary.warnings))
            self.assertIn("`completed` `candidate_a`", markdown)
            self.assertIn("portfolio_metadata.json", markdown)
            self.assertIn("which cost presets and benchmarks are represented", markdown)


def _write_portfolio(
    path: Path,
    *,
    portfolio_id: str,
    qqq_data: str | Path = "QQQ.csv",
    spy_data: str | Path = "SPY.csv",
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "portfolio_plan.v1",
                "portfolio_id": portfolio_id,
                "name": portfolio_id.replace("_", " ").title(),
                "description": "Static two-symbol candidate.",
                "symbols": [
                    {"symbol": "QQQ", "data": str(qqq_data), "target_weight": 0.60},
                    {"symbol": "SPY", "data": str(spy_data), "target_weight": 0.40},
                ],
                "rebalance": {"frequency": "monthly"},
                "benchmark": {"symbol": "SPY", "data": str(spy_data)},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_ohlcv(path: Path, closes: list[float]) -> None:
    lines = ["date,open,high,low,close,volume"]
    for index, close in enumerate(closes, start=1):
        lines.append(f"2026-01-0{index},{close},{close + 1},{close - 1},{close},1000")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_experiment(path: Path) -> None:
    append_experiment_record(
        create_experiment_record(
            experiment_id="EXP-001",
            title="Portfolio batch test",
            hypothesis="Batch runner should link completed runs.",
            created_at_utc="2026-07-18T00:00:00Z",
        ),
        path,
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
