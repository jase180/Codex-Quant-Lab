from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.portfolio_spec import parse_portfolio_spec  # noqa: E402
from quant_lab.portfolio_templates import (  # noqa: E402
    available_portfolio_templates,
    build_portfolio_template,
    write_portfolio_template,
)


class PortfolioTemplateTests(unittest.TestCase):
    def test_available_templates_are_stable(self) -> None:
        self.assertEqual(available_portfolio_templates(), ("qqq-spy-60-40",))

    def test_build_portfolio_template_returns_valid_payload(self) -> None:
        payload = build_portfolio_template("qqq-spy-60-40")

        spec = parse_portfolio_spec(payload)
        self.assertEqual(spec.portfolio_id, "qqq_spy_static_60_40")
        self.assertEqual([symbol.symbol for symbol in spec.symbols], ["QQQ", "SPY"])
        self.assertEqual([symbol.target_weight for symbol in spec.symbols], [0.6, 0.4])
        self.assertEqual(spec.rebalance.frequency, "monthly")
        self.assertEqual(spec.benchmark.symbol, "SPY")

    def test_write_portfolio_template_refuses_overwrite_without_force(self) -> None:
        payload = build_portfolio_template("qqq-spy-60-40")

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "portfolio.json"
            write_portfolio_template(payload, path)

            with self.assertRaises(FileExistsError):
                write_portfolio_template(payload, path)

            write_portfolio_template(payload, path, force=True)
            written = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(written["portfolio_id"], "qqq_spy_static_60_40")


if __name__ == "__main__":
    unittest.main()
