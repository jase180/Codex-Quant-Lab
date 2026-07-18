from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.portfolio_candidates import (  # noqa: E402
    generate_weight_grid,
    parse_candidate_symbols,
    write_portfolio_candidates,
)
from quant_lab.portfolio_spec import parse_portfolio_spec  # noqa: E402


class PortfolioCandidateTests(unittest.TestCase):
    def test_parse_candidate_symbols_requires_at_least_two_symbols(self) -> None:
        self.assertEqual(parse_candidate_symbols("qqq, spy, qqq"), ["QQQ", "SPY"])

        with self.assertRaisesRegex(ValueError, "at least two"):
            parse_candidate_symbols("QQQ")

    def test_generate_weight_grid_uses_positive_weights_that_sum_to_one(self) -> None:
        grid = generate_weight_grid(["QQQ", "SPY", "TLT"], 0.25)

        self.assertEqual(
            grid,
            [
                {"QQQ": 0.25, "SPY": 0.25, "TLT": 0.5},
                {"QQQ": 0.25, "SPY": 0.5, "TLT": 0.25},
                {"QQQ": 0.5, "SPY": 0.25, "TLT": 0.25},
            ],
        )

    def test_generate_weight_grid_rejects_bad_step(self) -> None:
        with self.assertRaisesRegex(ValueError, "divide 1.0"):
            generate_weight_grid(["QQQ", "SPY"], 0.3)

    def test_write_portfolio_candidates_creates_valid_capped_specs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            data_dir = workspace / "data"
            output_dir = workspace / "candidates"
            data_dir.mkdir()
            _write_csv(data_dir / "QQQ.csv")
            _write_csv(data_dir / "SPY.csv")
            _write_csv(data_dir / "TLT.csv")

            result = write_portfolio_candidates(
                symbols="QQQ,SPY,TLT",
                step=0.25,
                data_dir=data_dir,
                output_dir=output_dir,
                max_candidates=2,
                rebalance_frequency="quarterly",
                benchmark_symbol="SPY",
            )

            self.assertEqual(len(result.written), 2)
            self.assertGreater(result.skipped_count, 0)
            payload = json.loads(Path(result.written[0].path).read_text(encoding="utf-8"))
            spec = parse_portfolio_spec(payload)
            self.assertEqual(spec.rebalance.frequency, "quarterly")
            self.assertEqual(spec.benchmark.symbol, "SPY")
            self.assertEqual(len(spec.symbols), 3)
            self.assertTrue(Path(result.written[0].path).read_text(encoding="utf-8").endswith("\n"))

    def test_write_portfolio_candidates_rejects_ambiguous_data_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            data_dir = workspace / "data"
            data_dir.mkdir()
            _write_csv(data_dir / "QQQ_2020.csv")
            _write_csv(data_dir / "QQQ_2021.csv")
            _write_csv(data_dir / "SPY.csv")

            with self.assertRaisesRegex(ValueError, "Multiple CSV"):
                write_portfolio_candidates(
                    symbols="QQQ,SPY",
                    step=0.5,
                    data_dir=data_dir,
                    output_dir=workspace / "candidates",
                )

    def test_write_portfolio_candidates_rejects_step_with_no_positive_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            data_dir = workspace / "data"
            data_dir.mkdir()
            _write_csv(data_dir / "QQQ.csv")
            _write_csv(data_dir / "SPY.csv")
            _write_csv(data_dir / "TLT.csv")

            with self.assertRaisesRegex(ValueError, "too coarse"):
                write_portfolio_candidates(
                    symbols="QQQ,SPY,TLT",
                    step=0.5,
                    data_dir=data_dir,
                    output_dir=workspace / "candidates",
                )


def _write_csv(path: Path) -> None:
    path.write_text("date,open,high,low,close,volume\n2026-01-01,1,1,1,1,100\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
