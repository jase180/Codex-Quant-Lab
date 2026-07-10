from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest

import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from quant_lab.cli import (  # noqa: E402
    main,
)

from cli_fixtures import (  # noqa: E402
    _read_jsonl,
    _strategy_payload,
    _write_ohlcv_fixture,
)

class CliRunTests(unittest.TestCase):
    def test_run_command_writes_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "artifacts"
            index_path = temp_path / "research_index.jsonl"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "run",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--initial-cash",
                        "1000",
                        "--quantity",
                        "3",
                        "--index-path",
                        str(index_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "metrics.json").exists())
            self.assertTrue((output_dir / "equity_curve.csv").exists())
            self.assertTrue((output_dir / "report.md").exists())
            self.assertTrue((output_dir / "trades.csv").exists())
            self.assertTrue((output_dir / "equity_curve.png").exists())
            self.assertTrue((output_dir / "drawdown.png").exists())
            self.assertTrue((output_dir / "data_quality.json").exists())
            self.assertTrue((output_dir / "research_warnings.json").exists())
            self.assertTrue((output_dir / "run_metadata.json").exists())
            metadata = json.loads((output_dir / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["metadata_schema_version"], "run_metadata.v1")
            self.assertEqual(metadata["run_type"], "run")
            self.assertEqual(metadata["strategy"]["strategy_id"], "cli_smoke")
            self.assertEqual(metadata["data"]["row_count"], 4)
            self.assertEqual(metadata["sizing"]["initial_cash"], 1000.0)
            self.assertEqual(metadata["costs"]["slippage_bps"], 0.0)
            self.assertIn("metrics", metadata["artifacts"])
            self.assertIn("data_quality", metadata["artifacts"])
            self.assertIn("research_warnings", metadata["artifacts"])
            self.assertEqual(metadata["artifacts"]["research_index"], str(index_path))
            index_rows = _read_jsonl(index_path)
            self.assertEqual(len(index_rows), 1)
            self.assertEqual(index_rows[0]["index_schema_version"], "research_index.v1")
            self.assertEqual(index_rows[0]["run_type"], "run")
            self.assertEqual(index_rows[0]["strategy_id"], "cli_smoke")
            self.assertEqual(index_rows[0]["metadata_path"], str(output_dir / "run_metadata.json"))
            report = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("CLI Smoke", report)
            self.assertIn("## Benchmark: Buy And Hold", report)
            self.assertIn("## Data Quality", report)
            self.assertIn("## Research Warnings", report)
            self.assertIn("equity_curve.png", report)
            self.assertIn("buy", (output_dir / "trades.csv").read_text(encoding="utf-8"))

    def test_run_command_supports_percent_equity_sizing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "artifacts"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "run",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--sizing",
                        "percent-equity",
                        "--allocation",
                        "0.5",
                    ]
                )

            trades = (output_dir / "trades.csv").read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "trades.csv").exists())
            self.assertIn("buy", trades)

    def test_run_command_applies_transaction_cost_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "artifacts"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "run",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--initial-cash",
                        "1000",
                        "--quantity",
                        "3",
                        "--commission-fixed",
                        "1",
                        "--commission-rate",
                        "0.01",
                        "--slippage-bps",
                        "100",
                    ]
                )

            trades = pd.read_csv(output_dir / "trades.csv")
            self.assertEqual(exit_code, 0)
            self.assertIn("commission_fixed: 1.0", stdout.getvalue())
            self.assertIn("commission", trades.columns)
            self.assertGreater(trades.loc[0, "commission"], 0)
            self.assertAlmostEqual(trades.loc[0, "price"], 12.12)
            metadata = json.loads((output_dir / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["costs"]["commission_fixed"], 1.0)
            self.assertEqual(metadata["costs"]["commission_rate"], 0.01)
            self.assertEqual(metadata["costs"]["slippage_bps"], 100.0)
            self.assertEqual(metadata["command"][0], "quant-lab")

    def test_run_command_records_cost_preset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "artifacts"
            index_path = temp_path / "research_index.jsonl"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "run",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--initial-cash",
                        "1000",
                        "--quantity",
                        "3",
                        "--cost-preset",
                        "retail-liquid",
                        "--index-path",
                        str(index_path),
                    ]
                )

            metadata = json.loads((output_dir / "run_metadata.json").read_text(encoding="utf-8"))
            index_rows = _read_jsonl(index_path)
            self.assertEqual(exit_code, 0)
            self.assertEqual(metadata["costs"]["preset"], "retail-liquid")
            self.assertEqual(metadata["costs"]["commission_rate"], 0.0005)
            self.assertEqual(metadata["costs"]["slippage_bps"], 5.0)
            self.assertEqual(index_rows[0]["cost_preset"], "retail-liquid")

    def test_run_command_records_cash_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "artifacts"
            index_path = temp_path / "research_index.jsonl"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "run",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--initial-cash",
                        "1000",
                        "--quantity",
                        "3",
                        "--benchmark",
                        "cash",
                        "--index-path",
                        str(index_path),
                    ]
                )

            metadata = json.loads((output_dir / "run_metadata.json").read_text(encoding="utf-8"))
            index_rows = _read_jsonl(index_path)
            report = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertIn("benchmark: cash", stdout.getvalue())
            self.assertEqual(metadata["benchmark"]["name"], "cash")
            self.assertEqual(metadata["benchmark"]["display_name"], "Cash")
            self.assertEqual(index_rows[0]["benchmark_name"], "cash")
            self.assertEqual(index_rows[0]["benchmark_total_return"], 0.0)
            self.assertIn("## Benchmark: Cash", report)

    def test_run_command_saves_research_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "artifacts"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "run",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--initial-cash",
                        "1000",
                        "--quantity",
                        "3",
                        "--note",
                        "Hypothesis: tiny fixture should still save notes.",
                    ]
                )

            metadata = json.loads((output_dir / "run_metadata.json").read_text(encoding="utf-8"))
            note_path = output_dir / "research_note.md"
            self.assertEqual(exit_code, 0)
            self.assertTrue(note_path.exists())
            self.assertEqual(note_path.read_text(encoding="utf-8").strip(), "Hypothesis: tiny fixture should still save notes.")
            self.assertEqual(metadata["artifacts"]["research_note"], str(note_path))


if __name__ == "__main__":
    unittest.main()
