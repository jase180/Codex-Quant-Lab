import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.data_quality import build_data_quality_report, save_data_quality_report  # noqa: E402


class DataQualityTests(unittest.TestCase):
    def test_clean_data_has_no_warnings(self) -> None:
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100},
                {"date": "2026-01-02", "open": 11, "high": 12, "low": 10, "close": 11, "volume": 120},
            ]
        )

        report = build_data_quality_report(data)

        self.assertEqual(report.row_count, 2)
        self.assertEqual(report.start, "2026-01-01")
        self.assertEqual(report.end, "2026-01-02")
        self.assertEqual(report.warnings, [])

    def test_suspicious_data_counts_warnings(self) -> None:
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100},
                {"date": "2026-01-01", "open": 0, "high": 12, "low": 10, "close": 20, "volume": 0},
                {"date": "2026-01-10", "open": 20, "high": 21, "low": None, "close": 19, "volume": 50},
            ]
        )

        report = build_data_quality_report(data)

        self.assertEqual(report.duplicate_dates, 1)
        self.assertEqual(report.missing_ohlcv_values, 1)
        self.assertEqual(report.zero_volume_rows, 1)
        self.assertEqual(report.non_positive_price_rows, 1)
        self.assertEqual(len(report.large_gap_warnings), 1)
        self.assertEqual(len(report.calendar_gap_warnings), 1)
        self.assertGreaterEqual(len(report.warnings), 6)

    def test_save_data_quality_report_writes_json(self) -> None:
        report = build_data_quality_report(
            pd.DataFrame(
                [
                    {"date": "2026-01-01", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100},
                    {"date": "2026-01-02", "open": 11, "high": 12, "low": 10, "close": 11, "volume": 120},
                ]
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = save_data_quality_report(report, temp_dir)
            payload = json.loads(Path(path).read_text(encoding="utf-8"))

        self.assertEqual(payload["row_count"], 2)
        self.assertEqual(payload["warnings"], [])


if __name__ == "__main__":
    unittest.main()
