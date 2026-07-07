import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from metrics_reporting import RunMetrics  # noqa: E402
from quant_lab.research_warnings import build_research_warnings  # noqa: E402


def _metrics(observations: int = 300, total_return: float = 0.2, max_drawdown: float = -0.1) -> RunMetrics:
    return RunMetrics(
        sharpe_ratio=1.0,
        max_drawdown=max_drawdown,
        cagr=0.1,
        total_return=total_return,
        starting_equity=1000,
        ending_equity=1200,
        observations=observations,
    )


class ResearchWarningTests(unittest.TestCase):
    def test_warns_for_no_trades_and_short_sample(self) -> None:
        warnings = build_research_warnings(_metrics(observations=20), pd.DataFrame(columns=["side"]))

        self.assertTrue(warnings.no_trades)
        self.assertTrue(warnings.short_sample)
        self.assertIn("Strategy did not trade.", warnings.warnings)

    def test_warns_for_few_trades_and_no_exit(self) -> None:
        trades = pd.DataFrame([{"side": "buy"}, {"side": "buy"}])

        warnings = build_research_warnings(_metrics(), trades)

        self.assertTrue(warnings.too_few_trades)
        self.assertTrue(warnings.no_completed_exits)

    def test_warns_for_high_drawdown_relative_to_return(self) -> None:
        trades = pd.DataFrame([{"side": "buy"}, {"side": "sell"}, {"side": "buy"}, {"side": "sell"}, {"side": "buy"}])

        warnings = build_research_warnings(_metrics(total_return=0.05, max_drawdown=-0.25), trades)

        self.assertTrue(warnings.high_drawdown_relative_to_return)


if __name__ == "__main__":
    unittest.main()
