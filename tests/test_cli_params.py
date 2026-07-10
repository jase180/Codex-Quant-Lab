from __future__ import annotations

import unittest

import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from quant_lab.cli import (  # noqa: E402
    build_sweep_variants,
    parse_param_sweeps,
    parse_walk_forward_windows,
    split_train_test_data,
)

from cli_fixtures import (  # noqa: E402
    _strategy_payload,
)

class CliParamTests(unittest.TestCase):
    def test_parse_param_sweeps_coerces_numbers(self) -> None:
        params = parse_param_sweeps(
            [
                "sma_2.inputs.length=2,4",
                "sma_3.inputs.source=close",
            ]
        )

        self.assertEqual(params[0], ("sma_2.inputs.length", [2, 4]))
        self.assertEqual(params[1], ("sma_3.inputs.source", ["close"]))

    def test_build_sweep_variants_applies_cartesian_product(self) -> None:
        base_payload = _strategy_payload()
        variants = build_sweep_variants(
            base_payload,
            [
                ("sma_2.inputs.length", [2, 4]),
                ("sma_3.inputs.length", [3, 5]),
            ],
        )

        self.assertEqual(len(variants), 4)
        self.assertEqual(base_payload["indicators"][0]["inputs"]["length"], 2)
        self.assertEqual(variants[0]["payload"]["indicators"][0]["inputs"]["length"], 2)
        self.assertEqual(variants[1]["payload"]["indicators"][1]["inputs"]["length"], 5)
        self.assertEqual(variants[3]["params"]["sma_2.inputs.length"], 4)

    def test_train_test_split_rejects_overlapping_dates(self) -> None:
        data = pd.DataFrame(
            [
                {"date": "2026-01-01", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 100},
                {"date": "2026-01-02", "open": 11, "high": 11, "low": 11, "close": 11, "volume": 100},
            ]
        )

        with self.assertRaisesRegex(ValueError, "earlier than --test-start"):
            split_train_test_data(data, "2026-01-02", "2026-01-02")

    def test_parse_walk_forward_windows_rejects_overlapping_test_windows(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-overlapping"):
            parse_walk_forward_windows(
                [
                    "2026-01-01,2026-01-02,2026-01-03,2026-01-05",
                    "2026-01-02,2026-01-03,2026-01-05,2026-01-06",
                ]
            )


if __name__ == "__main__":
    unittest.main()
