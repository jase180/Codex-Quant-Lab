from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.costs import CostAssumptions  # noqa: E402
from quant_lab.run_config import RunExecutionConfig  # noqa: E402


class RunConfigTests(unittest.TestCase):
    def test_run_execution_config_from_args_copies_cli_values(self) -> None:
        costs = CostAssumptions(
            preset="none",
            commission_fixed=0.0,
            commission_rate=0.0,
            slippage_bps=0.0,
        )
        args = argparse.Namespace(
            data="data.csv",
            index_path="research_index.jsonl",
            initial_cash=1000,
            quantity=3,
            sizing="fixed-shares",
            allocation=1,
            benchmark="cash",
            cost_assumptions=costs,
            command_tokens=["quant-lab", "run"],
            experiment_id="EXP-001",
            experiments_path="experiments.jsonl",
        )

        config = RunExecutionConfig.from_args(args)

        self.assertEqual(config.data_path, "data.csv")
        self.assertEqual(config.index_path, "research_index.jsonl")
        self.assertEqual(config.initial_cash, 1000.0)
        self.assertEqual(config.quantity, 3.0)
        self.assertEqual(config.cost_assumptions, costs)
        self.assertEqual(config.command_tokens, ("quant-lab", "run"))
        self.assertEqual(config.experiment_id, "EXP-001")
        self.assertEqual(config.experiments_path, "experiments.jsonl")


if __name__ == "__main__":
    unittest.main()
