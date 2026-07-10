from __future__ import annotations

import contextlib
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
    _strategy_payload,
    _write_index_fixture,
    _write_ohlcv_fixture,
)

class CliRunIndexTests(unittest.TestCase):
    def test_list_runs_command_filters_and_sorts_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "research_index.jsonl"
            _write_index_fixture(index_path)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "list-runs",
                        "--index-path",
                        str(index_path),
                        "--symbol",
                        "QQQ",
                        "--sort",
                        "total_return",
                        "--limit",
                        "1",
                    ]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("strategy", output)
            self.assertIn("fast_strategy", output)
            self.assertIn("10.00%", output)
            self.assertNotIn("slow_strategy", output)

    def test_list_runs_command_filters_strategy_and_run_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "research_index.jsonl"
            _write_index_fixture(index_path)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "list-runs",
                        "--index-path",
                        str(index_path),
                        "--strategy-id",
                        "slow_strategy",
                        "--run-type",
                        "run",
                    ]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("slow_strategy", output)
            self.assertNotIn("fast_strategy", output)

    def test_list_runs_command_can_print_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "research_index.jsonl"
            _write_index_fixture(index_path)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "list-runs",
                        "--index-path",
                        str(index_path),
                        "--symbol",
                        "QQQ",
                        "--csv",
                    ]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("created,symbol,strategy,type,run,return", output)
            self.assertIn("QQQ,fast_strategy", output)
            self.assertNotIn("SPY,slow_strategy", output)

    def test_list_runs_command_handles_empty_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "missing.jsonl"

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["list-runs", "--index-path", str(index_path)])

            self.assertEqual(exit_code, 0)
            self.assertIn("No runs found", stdout.getvalue())

    def test_show_run_command_prints_metadata_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "artifacts"
            index_path = temp_path / "research_index.jsonl"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            with contextlib.redirect_stdout(io.StringIO()):
                main(
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
                        "--commission-rate",
                        "0.01",
                        "--index-path",
                        str(index_path),
                    ]
                )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["show-run", "--metadata", str(output_dir / "run_metadata.json")])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Run Summary", output)
            self.assertIn("cli_smoke", output)
            self.assertIn("TEST", output)
            self.assertIn("Total return", output)
            self.assertIn("Benchmark return", output)
            self.assertIn("Research Warnings", output)
            self.assertIn("Commission rate: 0.0100", output)
            self.assertIn("metrics:", output)
            self.assertIn("trades:", output)

    def test_show_run_command_rejects_missing_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.json"

            with self.assertRaises(FileNotFoundError):
                main(["show-run", "--metadata", str(missing_path)])

    def test_compare_runs_command_prints_comparison_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            first_output_dir = temp_path / "first"
            second_output_dir = temp_path / "second"
            index_path = temp_path / "research_index.jsonl"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

            for output_dir, quantity in [(first_output_dir, "2"), (second_output_dir, "3")]:
                with contextlib.redirect_stdout(io.StringIO()):
                    main(
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
                            quantity,
                            "--index-path",
                            str(index_path),
                        ]
                    )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "compare-runs",
                        "--metadata",
                        str(first_output_dir / "run_metadata.json"),
                        "--metadata",
                        str(second_output_dir / "run_metadata.json"),
                    ]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("strategy", output)
            self.assertIn("cli_smoke", output)
            self.assertIn("return", output)
            self.assertIn("bench", output)
            self.assertIn(str(first_output_dir), output)
            self.assertIn(str(second_output_dir), output)

    def test_compare_runs_command_requires_two_metadata_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / "run_metadata.json"

            with self.assertRaises(ValueError):
                main(["compare-runs", "--metadata", str(metadata_path)])


if __name__ == "__main__":
    unittest.main()
