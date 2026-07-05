from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from metrics_reporting import (  # noqa: E402
    drawdown_curve,
    save_drawdown_chart,
    save_equity_curve_chart,
)


class ChartTests(unittest.TestCase):
    def test_drawdown_curve(self) -> None:
        curve = [
            {"date": "2026-01-01", "equity": 100.0},
            {"date": "2026-01-02", "equity": 120.0},
            {"date": "2026-01-03", "equity": 90.0},
        ]

        drawdowns = drawdown_curve(curve)

        self.assertEqual(drawdowns[0], {"date": "2026-01-01", "drawdown": 0.0})
        self.assertEqual(drawdowns[1], {"date": "2026-01-02", "drawdown": 0.0})
        self.assertAlmostEqual(drawdowns[2]["drawdown"], -0.25)

    def test_save_chart_files(self) -> None:
        strategy_curve = [
            {"date": "2026-01-01", "equity": 100.0},
            {"date": "2026-01-02", "equity": 110.0},
            {"date": "2026-01-03", "equity": 105.0},
        ]
        benchmark_curve = [
            {"date": "2026-01-01", "equity": 100.0},
            {"date": "2026-01-02", "equity": 105.0},
            {"date": "2026-01-03", "equity": 115.0},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            equity_path = Path(temp_dir) / "equity_curve.png"
            drawdown_path = Path(temp_dir) / "drawdown.png"

            save_equity_curve_chart(strategy_curve, benchmark_curve, equity_path)
            save_drawdown_chart(strategy_curve, benchmark_curve, drawdown_path)

            self.assertGreater(equity_path.stat().st_size, 0)
            self.assertGreater(drawdown_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
