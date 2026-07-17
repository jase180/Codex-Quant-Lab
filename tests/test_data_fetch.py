from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
import json
import hashlib

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.data_fetch import (
    build_market_data_provenance,
    market_data_filename,
    normalize_ohlcv_frame,
    write_market_data_csv,
    write_market_data_provenance,
)


class DataFetchTests(unittest.TestCase):
    def test_normalize_ohlcv_frame_handles_standard_yfinance_columns(self) -> None:
        raw_data = pd.DataFrame(
            [
                {"Open": 100, "High": 102, "Low": 99, "Close": 101, "Volume": 1000},
                {"Open": 101, "High": 103, "Low": 100, "Close": 102, "Volume": 1100},
            ],
            index=pd.to_datetime(["2026-01-02", "2026-01-05"]),
        )
        raw_data.index.name = "Date"

        normalized = normalize_ohlcv_frame(raw_data)

        self.assertEqual(
            list(normalized.columns),
            ["date", "open", "high", "low", "close", "volume"],
        )
        self.assertEqual(normalized.iloc[0]["date"], "2026-01-02")
        self.assertEqual(normalized.iloc[1]["close"], 102)

    def test_normalize_ohlcv_frame_handles_single_symbol_multiindex_columns(self) -> None:
        raw_data = pd.DataFrame(
            [[100, 102, 99, 101, 1000]],
            index=pd.to_datetime(["2026-01-02"]),
            columns=pd.MultiIndex.from_tuples(
                [
                    ("Open", "SPY"),
                    ("High", "SPY"),
                    ("Low", "SPY"),
                    ("Close", "SPY"),
                    ("Volume", "SPY"),
                ]
            ),
        )
        raw_data.index.name = "Date"

        normalized = normalize_ohlcv_frame(raw_data)

        self.assertEqual(normalized.iloc[0].to_dict()["open"], 100)
        self.assertEqual(normalized.iloc[0].to_dict()["volume"], 1000)

    def test_market_data_filename_sanitizes_symbol(self) -> None:
        self.assertEqual(
            market_data_filename("brk b", "2020-01-01", "2020-12-31"),
            "BRK_B_2020-01-01_2020-12-31.csv",
        )

    def test_write_market_data_csv(self) -> None:
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
            csv_path = Path(
                write_market_data_csv(
                    data=data,
                    symbol="SPY",
                    start="2026-01-01",
                    end="2026-01-31",
                    output_dir=temp_dir,
                )
            )

            self.assertTrue(csv_path.exists())
            self.assertIn("date,open,high,low,close,volume", csv_path.read_text(encoding="utf-8"))

    def test_build_market_data_provenance_records_source_and_fingerprint(self) -> None:
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
            csv_path = Path(write_market_data_csv(data, "spy", "2026-01-01", "2026-01-31", temp_dir))
            provenance = build_market_data_provenance(
                csv_path=csv_path,
                data=data,
                symbol="spy",
                requested_start="2026-01-01",
                requested_end="2026-01-31",
                interval="1d",
                fetched_at_utc="2026-02-01T00:00:00Z",
            )

            self.assertEqual(provenance["provenance_schema_version"], "market_data_provenance.v1")
            self.assertEqual(provenance["provider"], "yfinance")
            self.assertEqual(provenance["symbol"], "SPY")
            self.assertEqual(provenance["requested_start"], "2026-01-01")
            self.assertEqual(provenance["requested_end"], "2026-01-31")
            self.assertEqual(provenance["interval"], "1d")
            self.assertEqual(provenance["row_count"], 1)
            self.assertEqual(provenance["data_start"], "2026-01-02")
            self.assertEqual(provenance["data_end"], "2026-01-02")
            self.assertEqual(provenance["file_sha256"], hashlib.sha256(csv_path.read_bytes()).hexdigest())

    def test_write_market_data_provenance_writes_sibling_json(self) -> None:
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
            csv_path = write_market_data_csv(data, "SPY", "2026-01-01", "2026-01-31", temp_dir)
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

            payload = json.loads(provenance_path.read_text(encoding="utf-8"))
            self.assertEqual(provenance_path.name, "SPY_2026-01-01_2026-01-31.provenance.json")
            self.assertEqual(payload["csv_path"], csv_path)
            self.assertEqual(payload["fetched_at_utc"], "2026-02-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
