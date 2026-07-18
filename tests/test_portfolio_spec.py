from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.portfolio_spec import (  # noqa: E402
    PortfolioSpecError,
    load_portfolio_spec,
    parse_portfolio_spec,
)


def valid_portfolio_payload() -> dict:
    return {
        "schema_version": "portfolio_plan.v1",
        "portfolio_id": "qqq_spy_static_60_40",
        "name": "QQQ SPY Static 60/40",
        "description": "Static two-symbol allocation.",
        "symbols": [
            {"symbol": "qqq", "data": "QQQ.csv", "target_weight": 0.60},
            {"symbol": "spy", "data": "SPY.csv", "target_weight": 0.40},
        ],
        "rebalance": {"frequency": "monthly"},
        "benchmark": {"symbol": "spy", "data": "SPY.csv"},
    }


class PortfolioSpecTests(unittest.TestCase):
    def test_parse_valid_portfolio_spec(self) -> None:
        spec = parse_portfolio_spec(valid_portfolio_payload())

        self.assertEqual(spec.schema_version, "portfolio_plan.v1")
        self.assertEqual(spec.portfolio_id, "qqq_spy_static_60_40")
        self.assertEqual(spec.symbols[0].symbol, "QQQ")
        self.assertEqual(spec.symbols[0].target_weight, 0.60)
        self.assertEqual(spec.rebalance.frequency, "monthly")
        self.assertEqual(spec.benchmark.symbol, "SPY")

    def test_load_portfolio_spec_records_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            spec_path = Path(temp_dir) / "portfolio.json"
            spec_path.write_text(json.dumps(valid_portfolio_payload()), encoding="utf-8")

            spec = load_portfolio_spec(spec_path)

        self.assertEqual(spec.source_path, str(spec_path))

    def test_example_portfolio_spec_is_valid(self) -> None:
        spec_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "portfolios"
            / "qqq_spy_static_60_40.json"
        )

        spec = load_portfolio_spec(spec_path)

        self.assertEqual(spec.portfolio_id, "qqq_spy_static_60_40")
        self.assertEqual([symbol.symbol for symbol in spec.symbols], ["QQQ", "SPY"])

    def test_rejects_duplicate_symbols(self) -> None:
        payload = valid_portfolio_payload()
        payload["symbols"][1]["symbol"] = "QQQ"

        with self.assertRaisesRegex(PortfolioSpecError, "Duplicate portfolio symbol 'QQQ'"):
            parse_portfolio_spec(payload)

    def test_rejects_weights_that_do_not_sum_to_one(self) -> None:
        payload = valid_portfolio_payload()
        payload["symbols"][1]["target_weight"] = 0.30

        with self.assertRaisesRegex(PortfolioSpecError, "target weights must sum to 1.0"):
            parse_portfolio_spec(payload)

    def test_rejects_unsupported_rebalance_frequency(self) -> None:
        payload = valid_portfolio_payload()
        payload["rebalance"]["frequency"] = "daily"

        with self.assertRaisesRegex(PortfolioSpecError, "rebalance.frequency must be one of"):
            parse_portfolio_spec(payload)

    def test_rejects_unknown_fields(self) -> None:
        payload = valid_portfolio_payload()
        payload["symbols"][0]["currency"] = "USD"

        with self.assertRaisesRegex(PortfolioSpecError, "symbols\\[0\\] contains unsupported fields"):
            parse_portfolio_spec(payload)


if __name__ == "__main__":
    unittest.main()
