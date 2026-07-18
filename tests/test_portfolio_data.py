from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.portfolio_data import PortfolioDataError, load_multi_asset_dataset  # noqa: E402
from quant_lab.portfolio_spec import parse_portfolio_spec  # noqa: E402


def write_ohlcv(path: Path, rows: list[tuple[str, int]]) -> None:
    lines = ["date,open,high,low,close,volume"]
    for date_value, close in rows:
        lines.append(f"{date_value},{close},{close + 1},{close - 1},{close},100")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def valid_portfolio_spec():
    return parse_portfolio_spec(
        {
            "schema_version": "portfolio_plan.v1",
            "portfolio_id": "qqq_spy_static_60_40",
            "name": "QQQ SPY Static 60/40",
            "description": "Static two-symbol allocation.",
            "symbols": [
                {"symbol": "QQQ", "data": "QQQ.csv", "target_weight": 0.60},
                {"symbol": "SPY", "data": "SPY.csv", "target_weight": 0.40},
            ],
            "rebalance": {"frequency": "monthly"},
            "benchmark": {"symbol": "SPY", "data": "SPY.csv"},
        }
    )


class PortfolioDataTests(unittest.TestCase):
    def test_load_multi_asset_dataset_aligns_to_intersection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            write_ohlcv(
                base_dir / "QQQ.csv",
                [
                    ("2026-01-01", 100),
                    ("2026-01-02", 101),
                    ("2026-01-03", 102),
                ],
            )
            write_ohlcv(
                base_dir / "SPY.csv",
                [
                    ("2026-01-02", 200),
                    ("2026-01-03", 201),
                    ("2026-01-04", 202),
                ],
            )

            dataset = load_multi_asset_dataset(valid_portfolio_spec(), base_dir=base_dir)

        self.assertEqual(dataset.alignment_policy, "intersection")
        self.assertEqual([date.date().isoformat() for date in dataset.calendar], ["2026-01-02", "2026-01-03"])
        self.assertEqual(len(dataset.symbols["QQQ"]), 2)
        self.assertEqual(float(dataset.symbols["SPY"].iloc[0].close), 200.0)
        self.assertEqual(dataset.dropped_rows_by_symbol, {"QQQ": 1, "SPY": 1})
        self.assertEqual(dataset.data_quality["QQQ"].row_count, 3)
        self.assertIn("file_sha256", dataset.fingerprints["SPY"])

    def test_load_multi_asset_dataset_uses_portfolio_source_path_as_base_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dir = Path(temp_dir) / "plans"
            nested_dir.mkdir()
            write_ohlcv(nested_dir / "QQQ.csv", [("2026-01-01", 100), ("2026-01-02", 101)])
            write_ohlcv(nested_dir / "SPY.csv", [("2026-01-01", 200), ("2026-01-02", 201)])
            spec = replace(valid_portfolio_spec(), source_path=str(nested_dir / "portfolio.json"))

            dataset = load_multi_asset_dataset(spec)

        self.assertEqual(len(dataset.calendar), 2)

    def test_load_multi_asset_dataset_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(PortfolioDataError, "Data file for QQQ does not exist"):
            load_multi_asset_dataset(valid_portfolio_spec(), base_dir=Path("."))

    def test_load_multi_asset_dataset_rejects_no_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            write_ohlcv(base_dir / "QQQ.csv", [("2026-01-01", 100)])
            write_ohlcv(base_dir / "SPY.csv", [("2026-01-02", 200)])

            with self.assertRaisesRegex(PortfolioDataError, "do not share any overlapping dates"):
                load_multi_asset_dataset(valid_portfolio_spec(), base_dir=base_dir)


if __name__ == "__main__":
    unittest.main()
