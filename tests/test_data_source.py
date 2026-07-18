from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.data_fetch import write_market_data_csv, write_market_data_provenance  # noqa: E402
from quant_lab.data_source import (  # noqa: E402
    format_data_cache_inventory,
    format_data_source_inspection,
    inspect_data_source,
    list_data_cache,
)


def _sample_data() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 101,
                "volume": 1000,
            },
            {
                "date": "2026-01-05",
                "open": 101,
                "high": 103,
                "low": 100,
                "close": 102,
                "volume": 1100,
            },
        ]
    )


class DataSourceTests(unittest.TestCase):
    def test_inspect_data_source_reads_csv_and_provenance(self) -> None:
        data = _sample_data()

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(write_market_data_csv(data, "SPY", "2026-01-01", "2026-01-31", temp_dir))
            write_market_data_provenance(
                csv_path=csv_path,
                data=data,
                symbol="SPY",
                requested_start="2026-01-01",
                requested_end="2026-01-31",
                interval="1d",
                fetched_at_utc="2026-02-01T00:00:00Z",
            )

            inspection = inspect_data_source(csv_path)

        self.assertEqual(inspection.row_count, 2)
        self.assertEqual(inspection.data_start, "2026-01-02")
        self.assertEqual(inspection.data_end, "2026-01-05")
        self.assertTrue(inspection.provenance_found)
        self.assertEqual(inspection.provenance["provider"], "yfinance")
        self.assertEqual(inspection.warnings, [])

    def test_inspect_data_source_warns_when_provenance_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(write_market_data_csv(_sample_data(), "SPY", "2026-01-01", "2026-01-31", temp_dir))

            inspection = inspect_data_source(csv_path)

        self.assertFalse(inspection.provenance_found)
        self.assertIn("missing provenance sidecar", inspection.warnings)

    def test_inspect_data_source_rejects_missing_csv(self) -> None:
        with self.assertRaises(FileNotFoundError):
            inspect_data_source("missing.csv")

    def test_inspect_data_source_rejects_malformed_ohlcv_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "bad.csv"
            csv_path.write_text("date,close\n2026-01-02,101\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing required columns"):
                inspect_data_source(csv_path)

    def test_format_data_source_inspection_prints_human_summary(self) -> None:
        data = _sample_data()

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(write_market_data_csv(data, "SPY", "2026-01-01", "2026-01-31", temp_dir))
            provenance_path = Path(
                write_market_data_provenance(
                    csv_path=csv_path,
                    data=data,
                    symbol="SPY",
                    requested_start="2026-01-01",
                    requested_end="2026-01-31",
                    interval="1d",
                    fetched_at_utc="2026-02-01T00:00:00Z",
                )
            )
            rendered = format_data_source_inspection(inspect_data_source(csv_path))
            provenance_payload = json.loads(provenance_path.read_text(encoding="utf-8"))

        self.assertIn("rows: 2", rendered)
        self.assertIn("date_range: 2026-01-02 to 2026-01-05", rendered)
        self.assertIn("provider: yfinance", rendered)
        self.assertIn("warnings: none", rendered)
        self.assertIn(provenance_payload["file_sha256"][:12], rendered)

    def test_list_data_cache_summarizes_csv_files(self) -> None:
        data = _sample_data()

        with tempfile.TemporaryDirectory() as temp_dir:
            qqq_path = Path(write_market_data_csv(data, "QQQ", "2026-01-01", "2026-01-31", temp_dir))
            spy_path = Path(write_market_data_csv(data, "SPY", "2026-01-01", "2026-01-31", temp_dir))
            write_market_data_provenance(
                csv_path=qqq_path,
                data=data,
                symbol="QQQ",
                requested_start="2026-01-01",
                requested_end="2026-01-31",
                interval="1d",
            )

            inventory = list_data_cache(temp_dir)
            rendered = format_data_cache_inventory(inventory)

        self.assertEqual(len(inventory.entries), 2)
        self.assertIn("QQQ", rendered)
        self.assertIn("SPY", rendered)
        self.assertIn("2026-01-02 to 2026-01-05", rendered)
        self.assertIn("provenance", rendered)
        self.assertIn(f"{spy_path.name}: missing provenance sidecar", rendered)

    def test_list_data_cache_flags_duplicate_symbol_date_ranges(self) -> None:
        data = _sample_data()

        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(write_market_data_csv(data, "QQQ", "2026-01-01", "2026-01-31", temp_dir))
            second = Path(temp_dir) / "QQQ_duplicate.csv"
            second.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")

            inventory = list_data_cache(temp_dir)

        self.assertEqual(len(inventory.entries), 2)
        self.assertEqual(len(inventory.warnings), 1)
        self.assertIn("duplicate-looking cache files for QQQ", inventory.warnings[0])

    def test_list_data_cache_rejects_missing_directory(self) -> None:
        with self.assertRaises(FileNotFoundError):
            list_data_cache("missing-cache-dir")


if __name__ == "__main__":
    unittest.main()
