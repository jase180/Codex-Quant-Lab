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

from quant_lab.cli import build_sweep_variants, main, parse_param_sweeps  # noqa: E402


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
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "metrics.json").exists())
            self.assertTrue((output_dir / "equity_curve.csv").exists())
            self.assertTrue((output_dir / "report.md").exists())
            self.assertTrue((output_dir / "trades.csv").exists())
            report = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("CLI Smoke", report)
            self.assertIn("## Benchmark: Buy And Hold", report)
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

    def test_sweep_command_writes_summary_and_per_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "sweep"

            strategy_path.write_text(json.dumps(_strategy_payload()), encoding="utf-8")
            _write_ohlcv_fixture(data_path)

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
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "summary.csv").exists())
            self.assertTrue((output_dir / "research.md").exists())

            summary = (output_dir / "summary.csv").read_text(encoding="utf-8")
            self.assertIn("run_id,strategy_id,params", summary)
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


if __name__ == "__main__":
    unittest.main()
