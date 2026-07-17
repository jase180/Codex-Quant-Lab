from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest

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
    _write_walk_forward_ohlcv_fixture,
)

class CliSweepWorkflowTests(unittest.TestCase):
    def test_sweep_command_writes_summary_and_per_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "sweep"
            index_path = temp_path / "research_index.jsonl"
            experiments_path = temp_path / "experiments.jsonl"
            note_path = temp_path / "note.md"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)
            note_path.write_text("Hypothesis: sweep note should link to every run.\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                create_exit_code = main(
                    [
                        "new-experiment",
                        "--experiments-path",
                        str(experiments_path),
                        "--experiment-id",
                        "EXP-002",
                        "--title",
                        "CLI sweep link",
                        "--hypothesis",
                        "A valid sweep should link every generated run metadata file.",
                    ]
                )
                exit_code = main(
                    [
                        "sweep",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--param",
                        "sma_2.inputs.length=2,3",
                        "--param",
                        "sma_3.inputs.length=3,4",
                        "--initial-cash",
                        "1000",
                        "--quantity",
                        "2",
                        "--note-file",
                        str(note_path),
                        "--index-path",
                        str(index_path),
                        "--experiments-path",
                        str(experiments_path),
                        "--experiment-id",
                        "EXP-002",
                    ]
                )

            self.assertEqual(create_exit_code, 0)
            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "summary.csv").exists())
            self.assertTrue((output_dir / "research.md").exists())
            self.assertTrue((output_dir / "research_note.md").exists())

            summary = (output_dir / "summary.csv").read_text(encoding="utf-8")
            self.assertIn("run_id,strategy_id,params", summary)
            self.assertIn("commission_fixed", summary)
            self.assertIn("slippage_bps", summary)
            self.assertIn("benchmark_name", summary)
            self.assertIn("benchmark_total_return", summary)
            self.assertIn("excess_total_return", summary)
            self.assertIn("run_001", summary)
            self.assertIn("run_004", summary)

            first_run = output_dir / "run_001"
            self.assertTrue((first_run / "metrics.json").exists())
            self.assertTrue((first_run / "equity_curve.csv").exists())
            self.assertTrue((first_run / "report.md").exists())
            self.assertTrue((first_run / "trades.csv").exists())
            self.assertTrue((first_run / "strategy.json").exists())
            self.assertTrue((first_run / "equity_curve.png").exists())
            self.assertTrue((first_run / "drawdown.png").exists())
            self.assertTrue((first_run / "data_quality.json").exists())
            self.assertTrue((first_run / "research_warnings.json").exists())
            self.assertTrue((first_run / "run_metadata.json").exists())
            metadata = json.loads((first_run / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["run_type"], "sweep_run")
            self.assertEqual(metadata["run_id"], "run_001")
            self.assertEqual(metadata["experiment_id"], "EXP-002")
            self.assertEqual(metadata["parameters"]["sma_2.inputs.length"], 2)
            self.assertEqual(metadata["data"]["file_sha256"], hashlib.sha256(data_path.read_bytes()).hexdigest())
            self.assertEqual(metadata["data"]["file_size_bytes"], data_path.stat().st_size)
            self.assertTrue(metadata["data"]["modified_at_utc"].endswith("Z"))
            self.assertEqual(metadata["data"]["quality_severity"], "warning")
            self.assertIn("strategy", metadata["artifacts"])
            self.assertEqual(metadata["artifacts"]["research_note"], str(output_dir / "research_note.md"))
            research = (output_dir / "research.md").read_text(encoding="utf-8")
            self.assertIn("Research note", research)
            self.assertIn("## Top Runs", research)
            self.assertIn("## Parameter Stability", research)
            index_rows = _read_jsonl(index_path)
            self.assertEqual(len(index_rows), 4)
            self.assertEqual(index_rows[0]["run_type"], "sweep_run")
            self.assertEqual(index_rows[0]["experiment_id"], "EXP-002")
            self.assertIn(index_rows[0]["run_id"], {"run_001", "run_002", "run_003", "run_004"})
            self.assertEqual(index_rows[0]["symbol"], "TEST")
            experiment_rows = _read_jsonl(experiments_path)
            self.assertEqual(len(experiment_rows[0]["linked_runs"]), 4)
            self.assertIn(str(output_dir / "run_001" / "run_metadata.json"), experiment_rows[0]["linked_runs"])
            self.assertIn(str(output_dir / "run_004" / "run_metadata.json"), experiment_rows[0]["linked_runs"])

    def test_sweep_command_supports_train_test_split(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "split"
            index_path = temp_path / "research_index.jsonl"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "sweep",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--param",
                        "sma_2.inputs.length=2,3",
                        "--param",
                        "sma_3.inputs.length=3,4",
                        "--initial-cash",
                        "1000",
                        "--quantity",
                        "2",
                        "--train-end",
                        "2026-01-02",
                        "--test-start",
                        "2026-01-03",
                        "--select-by",
                        "total_return",
                        "--index-path",
                        str(index_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("Train/test sweep complete", stdout.getvalue())
            self.assertTrue((output_dir / "train_sweep" / "summary.csv").exists())
            self.assertTrue((output_dir / "test_summary" / "summary.csv").exists())
            self.assertTrue((output_dir / "research.md").exists())
            self.assertTrue((output_dir / "train_sweep" / "run_001" / "run_metadata.json").exists())
            self.assertTrue((output_dir / "test_selected" / "run_metadata.json").exists())

            metadata = json.loads((output_dir / "test_selected" / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["run_type"], "test_selected_run")
            self.assertEqual(metadata["parameters"]["_split_phase"], "test")
            self.assertEqual(metadata["parameters"]["_train_end"], "2026-01-02")
            self.assertEqual(metadata["parameters"]["_test_start"], "2026-01-03")

            index_rows = _read_jsonl(index_path)
            self.assertEqual(len(index_rows), 5)
            self.assertEqual(index_rows[-1]["run_type"], "test_selected_run")

    def test_sweep_command_supports_walk_forward_windows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "walk_forward"
            index_path = temp_path / "research_index.jsonl"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_walk_forward_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "sweep",
                        "--strategy",
                        str(strategy_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(output_dir),
                        "--param",
                        "sma_2.inputs.length=2,3",
                        "--param",
                        "sma_3.inputs.length=3,4",
                        "--initial-cash",
                        "1000",
                        "--quantity",
                        "2",
                        "--walk-forward-window",
                        "2026-01-01,2026-01-02,2026-01-03,2026-01-04",
                        "--walk-forward-window",
                        "2026-01-02,2026-01-03,2026-01-05,2026-01-06",
                        "--select-by",
                        "total_return",
                        "--index-path",
                        str(index_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("Walk-forward sweep complete: 2 windows", stdout.getvalue())
            self.assertTrue((output_dir / "walk_forward_summary.csv").exists())
            self.assertTrue((output_dir / "research.md").exists())
            self.assertTrue((output_dir / "window_001" / "train_sweep" / "summary.csv").exists())
            self.assertTrue((output_dir / "window_001" / "test_selected" / "run_metadata.json").exists())
            self.assertTrue((output_dir / "window_002" / "test_selected" / "run_metadata.json").exists())

            summary = (output_dir / "walk_forward_summary.csv").read_text(encoding="utf-8")
            self.assertIn("window_id,train_start,train_end,test_start,test_end", summary)
            self.assertIn("window_001", summary)
            self.assertIn("window_002", summary)
            self.assertNotIn("_workflow", summary)

            metadata = json.loads(
                (output_dir / "window_001" / "test_selected" / "run_metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["run_type"], "walk_forward_test_run")
            self.assertEqual(metadata["parameters"]["_workflow"], "walk_forward")
            self.assertEqual(metadata["parameters"]["_window_id"], "window_001")
            self.assertEqual(metadata["parameters"]["_test_end"], "2026-01-04")

            index_rows = _read_jsonl(index_path)
            self.assertEqual(len(index_rows), 10)
            self.assertEqual(index_rows[-1]["run_type"], "walk_forward_test_run")


if __name__ == "__main__":
    unittest.main()
