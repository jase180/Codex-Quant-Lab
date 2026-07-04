from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.cli import main  # noqa: E402


class CliTests(unittest.TestCase):
    def test_run_command_writes_expected_artifacts(self) -> None:
        strategy_payload = {
            "schema_version": "v1",
            "strategy_id": "cli_smoke",
            "name": "CLI Smoke",
            "description": "A compact strategy used to test the CLI runner.",
            "strategy_type": "rule_based",
            "position_mode": "long_only",
            "market": {"symbol": "TEST", "timeframe": "1d"},
            "indicators": [
                {"id": "sma_2", "kind": "sma", "inputs": {"source": "close", "length": 2}},
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

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            strategy_path = temp_path / "strategy.json"
            data_path = temp_path / "ohlcv.csv"
            output_dir = temp_path / "artifacts"

            strategy_path.write_text(json.dumps(strategy_payload), encoding="utf-8")
            data_path.write_text(
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
            self.assertIn("CLI Smoke", (output_dir / "report.md").read_text(encoding="utf-8"))
            self.assertIn("buy", (output_dir / "trades.csv").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
