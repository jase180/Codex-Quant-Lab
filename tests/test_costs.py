import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.costs import resolve_cost_assumptions  # noqa: E402


class CostPresetTests(unittest.TestCase):
    def test_resolves_named_preset(self) -> None:
        costs = resolve_cost_assumptions(
            cost_preset="retail-liquid",
            commission_fixed=None,
            commission_rate=None,
            slippage_bps=None,
        )

        self.assertEqual(costs.preset, "retail-liquid")
        self.assertEqual(costs.commission_fixed, 0.0)
        self.assertEqual(costs.commission_rate, 0.0005)
        self.assertEqual(costs.slippage_bps, 5.0)

    def test_explicit_values_override_preset(self) -> None:
        costs = resolve_cost_assumptions(
            cost_preset="retail-liquid",
            commission_fixed=2.0,
            commission_rate=0.01,
            slippage_bps=100.0,
        )

        self.assertEqual(costs.preset, "retail-liquid")
        self.assertEqual(costs.commission_fixed, 2.0)
        self.assertEqual(costs.commission_rate, 0.01)
        self.assertEqual(costs.slippage_bps, 100.0)

    def test_unknown_preset_fails(self) -> None:
        with self.assertRaises(ValueError):
            resolve_cost_assumptions(
                cost_preset="unknown",
                commission_fixed=None,
                commission_rate=None,
                slippage_bps=None,
            )


if __name__ == "__main__":
    unittest.main()
