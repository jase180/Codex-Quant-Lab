from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.adjusted_price_audit import (  # noqa: E402
    build_adjusted_price_comparison,
    write_adjusted_price_audit,
)
from quant_lab.cli import main  # noqa: E402


class AdjustedPriceAuditTests(unittest.TestCase):
    def test_build_adjusted_price_comparison_matches_auto_adjusted_close_to_adj_close(self) -> None:
        adjusted = _adjusted_frame(close_values=[50.0, 100.25], ratios=[0.5, 1.0])
        raw = _raw_action_frame(adj_close_values=[50.0, 100.25], dividends=[0.0, 0.5])

        comparison = build_adjusted_price_comparison(adjusted=adjusted, raw=raw)

        self.assertEqual(list(comparison["date"]), ["2026-01-02", "2026-01-05"])
        self.assertEqual(float(comparison.iloc[0]["adjustment_ratio"]), 0.5)
        self.assertEqual(float(comparison.iloc[0]["expected_adjusted_open"]), 50.0)
        self.assertEqual(float(comparison.iloc[0]["open_difference"]), 0.0)
        self.assertEqual(float(comparison.iloc[0]["high_difference"]), 0.0)
        self.assertEqual(float(comparison.iloc[0]["low_difference"]), 0.0)
        self.assertEqual(float(comparison.iloc[1]["dividend"]), 0.5)
        self.assertEqual(float(comparison["close_difference"].max()), 0.0)

    def test_write_adjusted_price_audit_records_missing_expected_events(self) -> None:
        adjusted = _adjusted_frame(close_values=[99.5, 100.25])
        raw = _raw_action_frame(adj_close_values=[99.5, 100.25], dividends=[0.0, 0.5])
        comparison = build_adjusted_price_comparison(adjusted=adjusted, raw=raw)

        with tempfile.TemporaryDirectory() as temp_dir:
            audit = write_adjusted_price_audit(
                comparison=comparison,
                symbol="spy",
                start="2026-01-01",
                end="2026-01-31",
                out_dir=temp_dir,
                expected_dividend_dates=["2026-01-05", "2026-01-12"],
                expected_split_dates=["2026-01-12"],
                fetched_at_utc="2026-02-01T00:00:00Z",
            )

            payload = json.loads(Path(audit.json_path).read_text(encoding="utf-8"))
            comparison_exists = Path(audit.comparison_path).exists()

        self.assertEqual(audit.result, "warning")
        self.assertEqual(audit.max_ohlc_difference, 0.0)
        self.assertEqual(payload["symbol"], "SPY")
        self.assertEqual(payload["max_ohlc_difference"], 0.0)
        self.assertEqual(payload["backtest_implications"]["research_system_status"], "valid_with_caveats")
        self.assertEqual(payload["missing_expected_dividends"], ["2026-01-12"])
        self.assertEqual(payload["missing_expected_splits"], ["2026-01-12"])
        self.assertTrue(comparison_exists)
        self.assertIn("missing expected dividend dates", audit.warnings[0])

    def test_write_adjusted_price_audit_records_dividend_amount_mismatches(self) -> None:
        adjusted = _adjusted_frame(close_values=[99.5, 100.25])
        raw = _raw_action_frame(adj_close_values=[99.5, 100.25], dividends=[0.0, 0.5])
        comparison = build_adjusted_price_comparison(adjusted=adjusted, raw=raw)

        with tempfile.TemporaryDirectory() as temp_dir:
            audit = write_adjusted_price_audit(
                comparison=comparison,
                symbol="SPY",
                start="2026-01-01",
                end="2026-01-31",
                out_dir=temp_dir,
                expected_dividend_dates=["2026-01-05"],
                expected_dividend_amounts={"2026-01-05": 0.75},
                tolerance=0.01,
                fetched_at_utc="2026-02-01T00:00:00Z",
            )

            payload = json.loads(Path(audit.json_path).read_text(encoding="utf-8"))
            markdown = Path(audit.markdown_path).read_text(encoding="utf-8")

        self.assertEqual(audit.result, "warning")
        self.assertEqual(
            payload["dividend_amount_mismatches"],
            [{"actual": 0.5, "date": "2026-01-05", "difference": 0.25, "expected": 0.75}],
        )
        self.assertTrue(any("dividend amount mismatches" in warning for warning in audit.warnings))
        self.assertIn("Expected dividend amounts", markdown)
        self.assertIn("## Backtest Implications", markdown)
        self.assertIn("not an automated independent second-source validation", markdown)

    def test_write_adjusted_price_audit_warns_when_adjusted_ohlc_does_not_match_ratio(self) -> None:
        adjusted = _adjusted_frame(close_values=[50.0, 100.25], ratios=[0.6, 1.0])
        raw = _raw_action_frame(adj_close_values=[50.0, 100.25], dividends=[0.0, 0.5])
        comparison = build_adjusted_price_comparison(adjusted=adjusted, raw=raw)

        with tempfile.TemporaryDirectory() as temp_dir:
            audit = write_adjusted_price_audit(
                comparison=comparison,
                symbol="SPY",
                start="2026-01-01",
                end="2026-01-31",
                out_dir=temp_dir,
                fetched_at_utc="2026-02-01T00:00:00Z",
            )

        self.assertEqual(audit.result, "warning")
        self.assertGreater(audit.max_ohlc_difference, 0.01)
        self.assertTrue(any("auto-adjusted OHLC differs" in warning for warning in audit.warnings))

    def test_audit_adjusted_prices_command_writes_report_with_mocked_yfinance(self) -> None:
        calls = []

        def fake_download(symbol, **kwargs):
            calls.append((symbol, kwargs))
            if kwargs["auto_adjust"]:
                return _adjusted_frame(close_values=[99.5, 100.25])
            return _raw_action_frame(adj_close_values=[99.5, 100.25], dividends=[0.0, 0.5])

        fake_yfinance = types.SimpleNamespace(download=fake_download)

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(sys.modules, {"yfinance": fake_yfinance}):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    exit_code = main(
                        [
                            "audit-adjusted-prices",
                            "--symbol",
                            "SPY",
                            "--start",
                            "2026-01-01",
                            "--end",
                            "2026-01-31",
                            "--out",
                            temp_dir,
                            "--expected-dividend-date",
                            "2026-01-05",
                            "--expected-dividend",
                            "2026-01-05=0.5",
                        ]
                    )

            markdown_path = Path(temp_dir) / "adjusted_price_audit.md"
            markdown_exists = markdown_path.exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1]["auto_adjust"], True)
        self.assertEqual(calls[0][1]["actions"], False)
        self.assertEqual(calls[1][1]["auto_adjust"], False)
        self.assertEqual(calls[1][1]["actions"], True)
        self.assertTrue(markdown_exists)
        self.assertIn("result: pass", stdout.getvalue())
        self.assertIn("max_ohlc_difference: 0.0", stdout.getvalue())
        self.assertIn("dividend_amount_mismatches: 0", stdout.getvalue())

    def test_write_adjusted_price_audit_records_conservative_backtest_implications_on_pass(self) -> None:
        adjusted = _adjusted_frame(close_values=[99.5, 100.25])
        raw = _raw_action_frame(adj_close_values=[99.5, 100.25], dividends=[0.0, 0.5])
        comparison = build_adjusted_price_comparison(adjusted=adjusted, raw=raw)

        with tempfile.TemporaryDirectory() as temp_dir:
            audit = write_adjusted_price_audit(
                comparison=comparison,
                symbol="SPY",
                start="2026-01-01",
                end="2026-01-31",
                out_dir=temp_dir,
                expected_dividend_amounts={"2026-01-05": 0.5},
                fetched_at_utc="2026-02-01T00:00:00Z",
            )

            payload = json.loads(Path(audit.json_path).read_text(encoding="utf-8"))
            markdown = Path(audit.markdown_path).read_text(encoding="utf-8")

        implications = payload["backtest_implications"]
        self.assertEqual(audit.result, "pass")
        self.assertEqual(implications["research_system_status"], "valid_with_caveats")
        self.assertIn("adjusted open", implications["execution_implication"])
        self.assertIn("A passing audit does not prove", markdown)


def _adjusted_frame(*, close_values: list[float], ratios: list[float] | None = None) -> pd.DataFrame:
    adjustment_ratios = ratios or [value / 100.0 for value in close_values]
    frame = pd.DataFrame(
        {
            "Open": [100.0 * ratio for ratio in adjustment_ratios],
            "High": [101.0 * ratio for ratio in adjustment_ratios],
            "Low": [99.0 * ratio for ratio in adjustment_ratios],
            "Close": close_values,
            "Volume": [1000] * len(close_values),
        },
        index=pd.to_datetime(["2026-01-02", "2026-01-05"][: len(close_values)]),
    )
    frame.index.name = "Date"
    return frame


def _raw_action_frame(*, adj_close_values: list[float], dividends: list[float]) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "Open": [100.0] * len(adj_close_values),
            "High": [101.0] * len(adj_close_values),
            "Low": [99.0] * len(adj_close_values),
            "Close": [100.0] * len(adj_close_values),
            "Adj Close": adj_close_values,
            "Volume": [1000] * len(adj_close_values),
            "Dividends": dividends,
            "Stock Splits": [0.0] * len(adj_close_values),
        },
        index=pd.to_datetime(["2026-01-02", "2026-01-05"][: len(adj_close_values)]),
    )
    frame.index.name = "Date"
    return frame


if __name__ == "__main__":
    unittest.main()
