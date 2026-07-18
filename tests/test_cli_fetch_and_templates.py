from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from quant_lab.cli import (  # noqa: E402
    main,
)

class CliFetchAndTemplateTests(unittest.TestCase):
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
            with patch("quant_lab.cli_data.fetch_market_data", return_value=fetched_data):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
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
            provenance_path = Path(temp_dir) / "SPY_2026-01-01_2026-01-31.provenance.json"
            self.assertEqual(exit_code, 0)
            self.assertTrue(csv_path.exists())
            self.assertTrue(provenance_path.exists())
            self.assertIn("2026-01-02,100,102,99,101,1000", csv_path.read_text(encoding="utf-8"))
            self.assertIn(f"provenance: {provenance_path}", stdout.getvalue())
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            self.assertEqual(provenance["provider"], "yfinance")
            self.assertEqual(provenance["symbol"], "SPY")
            self.assertEqual(provenance["row_count"], 1)

    def test_list_strategy_templates_command_prints_templates(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = main(["list-strategy-templates"])

        self.assertEqual(exit_code, 0)
        self.assertIn("sma-crossover", stdout.getvalue())
        self.assertIn("rsi-reversion", stdout.getvalue())

    def test_show_data_source_command_prints_csv_and_provenance_summary(self) -> None:
        data = pd.DataFrame(
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
            csv_path = Path(temp_dir) / "SPY_2026-01-01_2026-01-31.csv"
            data.to_csv(csv_path, index=False)
            provenance_path = csv_path.with_suffix(".provenance.json")
            provenance_path.write_text(
                json.dumps(
                    {
                        "provenance_schema_version": "market_data_provenance.v1",
                        "provider": "fixture",
                        "symbol": "SPY",
                        "requested_start": "2026-01-01",
                        "requested_end": "2026-01-31",
                        "data_start": "2026-01-02",
                        "data_end": "2026-01-02",
                        "fetched_at_utc": "2026-02-01T00:00:00Z",
                        "row_count": 1,
                    }
                ),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["show-data-source", "--data", str(csv_path)])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn(f"data: {csv_path}", output)
        self.assertIn("rows: 1", output)
        self.assertIn("provider: fixture", output)
        self.assertIn("warnings: none", output)

    def test_list_data_cache_command_prints_inventory(self) -> None:
        data = pd.DataFrame(
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
            csv_path = Path(temp_dir) / "SPY_2026-01-01_2026-01-31.csv"
            data.to_csv(csv_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["list-data-cache", "--data-dir", temp_dir])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("csv_files: 1", output)
        self.assertIn("SPY", output)
        self.assertIn("missing provenance sidecar", output)

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


if __name__ == "__main__":
    unittest.main()
