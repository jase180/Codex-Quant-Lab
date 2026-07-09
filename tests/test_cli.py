from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.cli import (  # noqa: E402
    build_sweep_variants,
    main,
    parse_param_sweeps,
    parse_walk_forward_windows,
    split_train_test_data,
)


def _strategy_payload() -> dict:
    return {
        "schema_version": "v1",
        "strategy_id": "cli_smoke",
        "name": "CLI Smoke",
        "description": "A compact strategy used to test the CLI runner.",
        "strategy_type": "rule_based",
        "position_mode": "long_only",
        "market": {"symbol": "TEST", "timeframe": "1d"},
        "indicators": [
            {"id": "sma_2", "kind": "sma", "inputs": {"source": "close", "length": 2}},
            {"id": "sma_3", "kind": "sma", "inputs": {"source": "close", "length": 3}},
        ],
        "entry": {
            "when": "all",
            "conditions": [
                {
                    "left": {"price": "close"},
                    "operator": "gt",
                    "right": {"indicator": "sma_2"},
                }
            ],
        },
        "exit": {
            "when": "all",
            "conditions": [
                {
                    "left": {"price": "close"},
                    "operator": "lt",
                    "right": {"indicator": "sma_2"},
                }
            ],
        },
    }


def _write_ohlcv_fixture(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "date,open,high,low,close,volume",
                "2026-01-01,10,10,10,10,100",
                "2026-01-02,11,11,11,11,100",
                "2026-01-03,12,12,12,12,100",
                "2026-01-04,9,9,9,9,100",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_walk_forward_ohlcv_fixture(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "date,open,high,low,close,volume",
                "2026-01-01,10,10,10,10,100",
                "2026-01-02,11,11,11,11,100",
                "2026-01-03,12,12,12,12,100",
                "2026-01-04,13,13,13,13,100",
                "2026-01-05,12,12,12,12,100",
                "2026-01-06,14,14,14,14,100",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_index_fixture(path: Path) -> None:
    records = [
        {
            "index_schema_version": "research_index.v1",
            "created_at_utc": "2026-01-01T00:00:00Z",
            "run_type": "run",
            "run_id": None,
            "strategy_id": "slow_strategy",
            "strategy_name": "Slow Strategy",
            "symbol": "SPY",
            "timeframe": "1d",
            "data_start": "2026-01-01",
            "data_end": "2026-01-31",
            "final_equity": 1010,
            "total_return": 0.01,
            "cagr": 0.12,
            "sharpe_ratio": 0.5,
            "max_drawdown": -0.05,
            "trade_count": 2,
            "benchmark_total_return": 0.02,
            "benchmark_max_drawdown": -0.03,
            "excess_total_return": -0.01,
            "sizing": "fixed-shares",
            "initial_cash": 1000,
            "quantity": 1,
            "allocation": 1,
            "commission_fixed": 0,
            "commission_rate": 0,
            "slippage_bps": 0,
            "output_dir": "artifacts/spy_run",
            "metadata_path": "artifacts/spy_run/run_metadata.json",
            "git_commit": "abc",
        },
        {
            "index_schema_version": "research_index.v1",
            "created_at_utc": "2026-01-02T00:00:00Z",
            "run_type": "run",
            "run_id": None,
            "strategy_id": "fast_strategy",
            "strategy_name": "Fast Strategy",
            "symbol": "QQQ",
            "timeframe": "1d",
            "data_start": "2026-01-01",
            "data_end": "2026-01-31",
            "final_equity": 1100,
            "total_return": 0.10,
            "cagr": 1.2,
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.10,
            "trade_count": 4,
            "benchmark_total_return": 0.06,
            "benchmark_max_drawdown": -0.08,
            "excess_total_return": 0.04,
            "sizing": "percent-equity",
            "initial_cash": 1000,
            "quantity": 1,
            "allocation": 1,
            "commission_fixed": 0,
            "commission_rate": 0,
            "slippage_bps": 0,
            "output_dir": "artifacts/qqq_run",
            "metadata_path": "artifacts/qqq_run/run_metadata.json",
            "git_commit": "def",
        },
    ]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


class CliTests(unittest.TestCase):
    def test_parse_param_sweeps_coerces_numbers(self) -> None:
        params = parse_param_sweeps(
            [
                "sma_2.inputs.length=2,4",
                "sma_3.inputs.source=close",
            ]
        )

        self.assertEqual(params[0], ("sma_2.inputs.length", [2, 4]))
        self.assertEqual(params[1], ("sma_3.inputs.source", ["close"]))

    def test_build_sweep_variants_applies_cartesian_product(self) -> None:
        base_payload = _strategy_payload()
        variants = build_sweep_variants(
            base_payload,
            [
                ("sma_2.inputs.length", [2, 4]),
                ("sma_3.inputs.length", [3, 5]),
            ],
        )

        self.assertEqual(len(variants), 4)
        self.assertEqual(base_payload["indicators"][0]["inputs"]["length"], 2)
        self.assertEqual(variants[0]["payload"]["indicators"][0]["inputs"]["length"], 2)
        self.assertEqual(variants[1]["payload"]["indicators"][1]["inputs"]["length"], 5)
        self.assertEqual(variants[3]["params"]["sma_2.inputs.length"], 4)

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

    def test_fetch_command_writes_normalized_csv(self) -> None:
        fetched_data = pd.DataFrame(
            [
                {
                    "date": "2026-01-02",
                    "open": 100,
                    "high": 102,
                    "low": 99,
                    "close": 101,
                    "volume": 1000,
                }
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("quant_lab.cli.fetch_market_data", return_value=fetched_data):
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = main(
                        [
                            "fetch",
                            "--symbol",
                            "SPY",
                            "--start",
                            "2026-01-01",
                            "--end",
                            "2026-01-31",
                            "--out",
                            temp_dir,
                        ]
                    )

            csv_path = Path(temp_dir) / "SPY_2026-01-01_2026-01-31.csv"
            self.assertEqual(exit_code, 0)
            self.assertTrue(csv_path.exists())
            self.assertIn("2026-01-02,100,102,99,101,1000", csv_path.read_text(encoding="utf-8"))

    def test_list_strategy_templates_command_prints_templates(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["list-strategy-templates"])

        self.assertEqual(exit_code, 0)
        self.assertIn("sma-crossover", stdout.getvalue())
        self.assertIn("rsi-reversion", stdout.getvalue())

    def test_new_strategy_command_writes_valid_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "qqq_sma.json"

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "new-strategy",
                        "--template",
                        "sma-crossover",
                        "--symbol",
                        "qqq",
                        "--strategy-id",
                        "qqq_sma",
                        "--name",
                        "QQQ SMA",
                        "--out",
                        str(output_path),
                    ]
                )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertIn("Strategy template written", stdout.getvalue())
            self.assertEqual(payload["strategy_id"], "qqq_sma")
            self.assertEqual(payload["name"], "QQQ SMA")
            self.assertEqual(payload["market"]["symbol"], "QQQ")

            with self.assertRaises(FileExistsError):
                main(
                    [
                        "new-strategy",
                        "--template",
                        "sma-crossover",
                        "--symbol",
                        "QQQ",
                        "--out",
                        str(output_path),
                    ]
                )

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

    def test_sweep_command_writes_summary_and_per_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "sweep"
            index_path = temp_path / "research_index.jsonl"
            note_path = temp_path / "note.md"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)
            note_path.write_text("Hypothesis: sweep note should link to every run.\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
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
                    ]
                )

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
            self.assertEqual(metadata["parameters"]["sma_2.inputs.length"], 2)
            self.assertIn("strategy", metadata["artifacts"])
            self.assertEqual(metadata["artifacts"]["research_note"], str(output_dir / "research_note.md"))
            research = (output_dir / "research.md").read_text(encoding="utf-8")
            self.assertIn("Research note", research)
            self.assertIn("## Top Runs", research)
            self.assertIn("## Parameter Stability", research)
            index_rows = _read_jsonl(index_path)
            self.assertEqual(len(index_rows), 4)
            self.assertEqual(index_rows[0]["run_type"], "sweep_run")
            self.assertIn(index_rows[0]["run_id"], {"run_001", "run_002", "run_003", "run_004"})
            self.assertEqual(index_rows[0]["symbol"], "TEST")

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

    def test_train_test_split_rejects_overlapping_dates(self) -> None:
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 100},
                {"date": "2026-01-02", "open": 11, "high": 11, "low": 11, "close": 11, "volume": 100},
            ]
        )

        with self.assertRaisesRegex(ValueError, "earlier than --test-start"):
            split_train_test_data(data, "2026-01-02", "2026-01-02")

    def test_parse_walk_forward_windows_rejects_overlapping_test_windows(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-overlapping"):
            parse_walk_forward_windows(
                [
                    "2026-01-01,2026-01-02,2026-01-03,2026-01-05",
                    "2026-01-02,2026-01-03,2026-01-05,2026-01-06",
                ]
            )


if __name__ == "__main__":
    unittest.main()
