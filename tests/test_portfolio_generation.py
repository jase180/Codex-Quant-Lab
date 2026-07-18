from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.portfolio_generation import (  # noqa: E402
    validate_rebalance_frequency,
    weight_suffix,
    write_portfolio_json,
)


class PortfolioGenerationTests(unittest.TestCase):
    def test_weight_suffix_uses_stable_basis_point_tokens(self) -> None:
        self.assertEqual(
            weight_suffix({"QQQ": 0.6, "SPY": 0.4}, ["QQQ", "SPY"]),
            "qqq_6000bp_spy_4000bp",
        )

    def test_validate_rebalance_frequency_normalizes_and_rejects_unknown_values(self) -> None:
        self.assertEqual(validate_rebalance_frequency(" Quarterly "), "quarterly")

        with self.assertRaisesRegex(ValueError, "Unsupported rebalance"):
            validate_rebalance_frequency("weekly")

    def test_write_portfolio_json_writes_stable_json_with_newline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "payload.json"

            write_portfolio_json(path, {"b": 2, "a": 1})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 1, "b": 2})
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))


if __name__ == "__main__":
    unittest.main()
