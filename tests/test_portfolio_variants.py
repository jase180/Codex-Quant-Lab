from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.portfolio_spec import parse_portfolio_spec  # noqa: E402
from quant_lab.portfolio_variants import (  # noqa: E402
    normalize_rebalance_frequencies,
    parse_weight_set,
    write_portfolio_variants,
)


class PortfolioVariantTests(unittest.TestCase):
    def test_parse_weight_set_normalizes_and_validates_symbols(self) -> None:
        weights = parse_weight_set("qqq=0.7, spy=0.3", ["QQQ", "SPY"])

        self.assertEqual(weights, {"QQQ": 0.7, "SPY": 0.3})

    def test_parse_weight_set_rejects_missing_or_bad_weights(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing"):
            parse_weight_set("QQQ=1.0", ["QQQ", "SPY"])

        with self.assertRaisesRegex(ValueError, "sum to 1.0"):
            parse_weight_set("QQQ=0.7,SPY=0.4", ["QQQ", "SPY"])

        with self.assertRaisesRegex(ValueError, "unknown symbol"):
            parse_weight_set("QQQ=0.6,TLT=0.4", ["QQQ", "SPY"])

    def test_normalize_rebalance_frequencies_deduplicates_and_validates(self) -> None:
        self.assertEqual(
            normalize_rebalance_frequencies(["monthly", " quarterly ", "monthly"]),
            ["monthly", "quarterly"],
        )

        with self.assertRaisesRegex(ValueError, "Unsupported rebalance"):
            normalize_rebalance_frequencies(["weekly"])

    def test_write_portfolio_variants_creates_valid_specs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            base_path = workspace / "base.json"
            output_dir = workspace / "variants"
            _write_base_portfolio(base_path)

            results = write_portfolio_variants(
                portfolio_path=base_path,
                raw_weight_sets=["QQQ=0.5,SPY=0.5", "QQQ=0.7,SPY=0.3"],
                output_dir=output_dir,
            )

            self.assertEqual(len(results), 2)
            first_payload = json.loads(Path(results[0].path).read_text(encoding="utf-8"))
            first_spec = parse_portfolio_spec(first_payload)
            self.assertEqual(
                first_spec.portfolio_id,
                "qqq_spy_static_60_40_qqq_5000bp_spy_5000bp_rebalance_monthly",
            )
            self.assertEqual([symbol.target_weight for symbol in first_spec.symbols], [0.5, 0.5])
            self.assertEqual(first_spec.rebalance.frequency, "monthly")
            self.assertEqual(first_spec.benchmark.symbol, "SPY")
            self.assertTrue(Path(results[0].path).read_text(encoding="utf-8").endswith("\n"))

    def test_write_portfolio_variants_creates_weight_and_rebalance_cross_product(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            base_path = workspace / "base.json"
            output_dir = workspace / "variants"
            _write_base_portfolio(base_path)

            results = write_portfolio_variants(
                portfolio_path=base_path,
                raw_weight_sets=["QQQ=0.5,SPY=0.5", "QQQ=0.7,SPY=0.3"],
                rebalance_frequencies=["none", "quarterly"],
                output_dir=output_dir,
            )

            self.assertEqual(len(results), 4)
            portfolio_ids = [result.portfolio_id for result in results]
            self.assertIn("qqq_spy_static_60_40_qqq_5000bp_spy_5000bp_rebalance_none", portfolio_ids)
            self.assertIn("qqq_spy_static_60_40_qqq_7000bp_spy_3000bp_rebalance_quarterly", portfolio_ids)
            quarterly_payload = json.loads(
                (output_dir / "qqq_spy_static_60_40_qqq_7000bp_spy_3000bp_rebalance_quarterly.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(quarterly_payload["rebalance"]["frequency"], "quarterly")

    def test_write_portfolio_variants_refuses_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            base_path = workspace / "base.json"
            output_dir = workspace / "variants"
            _write_base_portfolio(base_path)

            write_portfolio_variants(
                portfolio_path=base_path,
                raw_weight_sets=["QQQ=0.5,SPY=0.5"],
                output_dir=output_dir,
            )

            with self.assertRaises(FileExistsError):
                write_portfolio_variants(
                    portfolio_path=base_path,
                    raw_weight_sets=["QQQ=0.5,SPY=0.5"],
                    output_dir=output_dir,
                )

            results = write_portfolio_variants(
                portfolio_path=base_path,
                raw_weight_sets=["QQQ=0.5,SPY=0.5"],
                output_dir=output_dir,
                force=True,
            )
            self.assertEqual(len(results), 1)


def _write_base_portfolio(path: Path) -> None:
    path.write_text(
        json.dumps(
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
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
