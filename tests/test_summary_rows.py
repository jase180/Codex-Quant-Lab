from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.summary_rows import SWEEP_SUMMARY_FIELDNAMES, SweepSummaryRow  # noqa: E402


class SummaryRowTests(unittest.TestCase):
    def test_sweep_summary_row_behaves_like_mapping(self) -> None:
        row = SweepSummaryRow(
            run_id="run_001",
            strategy_id="demo",
            params='{"length": 20}',
            final_equity=101_000.0,
            total_return=0.01,
            cagr=None,
            sharpe_ratio=1.2,
            max_drawdown=-0.03,
            trade_count=4,
            sizing="fixed-shares",
            quantity=1.0,
            allocation=1.0,
            cost_preset="none",
            commission_fixed=0.0,
            commission_rate=0.0,
            slippage_bps=0.0,
            benchmark_name="cash",
            benchmark_final_equity=100_000.0,
            benchmark_total_return=0.0,
            benchmark_cagr=None,
            benchmark_sharpe_ratio=None,
            benchmark_max_drawdown=0.0,
            excess_total_return=0.01,
            output_dir="artifacts/run_001",
        )

        self.assertEqual(row["run_id"], "run_001")
        self.assertEqual(row.get("total_return"), 0.01)
        self.assertEqual(list(row.to_dict()), SWEEP_SUMMARY_FIELDNAMES)


if __name__ == "__main__":
    unittest.main()
