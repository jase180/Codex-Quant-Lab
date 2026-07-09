from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.strategy_schema import parse_strategy  # noqa: E402
from quant_lab.strategy_templates import (  # noqa: E402
    available_strategy_templates,
    build_strategy_template,
    write_strategy_template,
)


class StrategyTemplateTests(unittest.TestCase):
    def test_available_templates_are_stable(self) -> None:
        self.assertEqual(
            available_strategy_templates(),
            ("sma-crossover", "ema-trend-follow", "rsi-reversion", "breakout-trend"),
        )

    def test_build_strategy_template_returns_valid_payload(self) -> None:
        payload = build_strategy_template(
            "sma-crossover",
            symbol="qqq",
            strategy_id="qqq_sma",
            name="QQQ SMA",
        )

        spec = parse_strategy(payload)
        self.assertEqual(spec.strategy_id, "qqq_sma")
        self.assertEqual(spec.name, "QQQ SMA")
        self.assertEqual(spec.market.symbol, "QQQ")

    def test_build_breakout_template_returns_valid_payload(self) -> None:
        payload = build_strategy_template("breakout-trend", symbol="spy")

        spec = parse_strategy(payload)
        self.assertEqual(spec.strategy_id, "breakout_trend")
        self.assertEqual(spec.market.symbol, "SPY")
        self.assertEqual(spec.indicators[0].kind, "rolling_high")
        self.assertEqual(spec.indicators[1].kind, "rolling_low")

    def test_write_strategy_template_refuses_overwrite_without_force(self) -> None:
        payload = build_strategy_template("rsi-reversion", symbol="SPY")

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "strategy.json"
            write_strategy_template(payload, path)

            with self.assertRaises(FileExistsError):
                write_strategy_template(payload, path)

            write_strategy_template(payload, path, force=True)
            written = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(written["strategy_id"], "rsi_reversion")


if __name__ == "__main__":
    unittest.main()
