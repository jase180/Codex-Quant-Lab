from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.strategy_schema import StrategySchemaError, load_strategy, parse_strategy


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "data" / "strategies"


class StrategySchemaTests(unittest.TestCase):
    def test_parse_valid_rsi_strategy(self) -> None:
        strategy = load_strategy(FIXTURES_DIR / "rsi_reversion.json")

        self.assertEqual(strategy.schema_version, "v1")
        self.assertEqual(strategy.strategy_id, "rsi_reversion")
        self.assertEqual(strategy.market.timeframe, "1d")
        self.assertEqual(strategy.indicators[0].kind, "rsi")
        self.assertEqual(strategy.entry.conditions[0].operator, "lt")

    def test_parse_valid_sma_crossover_strategy(self) -> None:
        strategy = load_strategy(FIXTURES_DIR / "sma_crossover.json")

        self.assertEqual(strategy.strategy_type, "rule_based")
        self.assertEqual(len(strategy.indicators), 2)
        self.assertEqual(strategy.entry.conditions[0].operator, "crosses_above")

    def test_parse_valid_ema_trend_strategy(self) -> None:
        strategy = load_strategy(FIXTURES_DIR / "ema_trend_follow.json")

        self.assertEqual(strategy.position_mode, "long_only")
        self.assertEqual(strategy.exit.when, "any")

    def test_missing_required_field_raises_clear_error(self) -> None:
        payload = {
            "schema_version": "v1",
            "strategy_id": "missing_name",
            "description": "Missing a required name field.",
            "strategy_type": "rule_based",
            "position_mode": "long_only",
            "market": {"symbol": "SPY", "timeframe": "1d"},
            "indicators": [{"id": "fast_sma", "kind": "sma", "inputs": {"source": "close", "length": 10}}],
            "entry": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "gt",
                        "right": {"indicator": "fast_sma"},
                    }
                ],
            },
            "exit": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "lt",
                        "right": {"indicator": "fast_sma"},
                    }
                ],
            },
        }

        with self.assertRaisesRegex(StrategySchemaError, "strategy.name must be a non-empty string"):
            parse_strategy(payload)

    def test_unknown_indicator_reference_is_rejected(self) -> None:
        payload = {
            "schema_version": "v1",
            "strategy_id": "bad_indicator_ref",
            "name": "Bad indicator ref",
            "description": "References an unknown indicator.",
            "strategy_type": "rule_based",
            "position_mode": "long_only",
            "market": {"symbol": "SPY", "timeframe": "1d"},
            "indicators": [{"id": "fast_sma", "kind": "sma", "inputs": {"source": "close", "length": 10}}],
            "entry": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"indicator": "missing_indicator"},
                        "operator": "gt",
                        "right": {"value": 0},
                    }
                ],
            },
            "exit": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "lt",
                        "right": {"indicator": "fast_sma"},
                    }
                ],
            },
        }

        with self.assertRaisesRegex(StrategySchemaError, "must reference a declared indicator id"):
            parse_strategy(payload)

    def test_invalid_timeframe_is_rejected(self) -> None:
        payload = {
            "schema_version": "v1",
            "strategy_id": "bad_timeframe",
            "name": "Bad timeframe",
            "description": "Uses an invalid timeframe.",
            "strategy_type": "rule_based",
            "position_mode": "long_only",
            "market": {"symbol": "SPY", "timeframe": "4h"},
            "indicators": [{"id": "fast_sma", "kind": "sma", "inputs": {"source": "close", "length": 10}}],
            "entry": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "gt",
                        "right": {"indicator": "fast_sma"},
                    }
                ],
            },
            "exit": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "lt",
                        "right": {"indicator": "fast_sma"},
                    }
                ],
            },
        }

        with self.assertRaisesRegex(StrategySchemaError, "market.timeframe must be one of \\['1d'\\]"):
            parse_strategy(payload)

    def test_duplicate_indicator_ids_are_rejected(self) -> None:
        payload = {
            "schema_version": "v1",
            "strategy_id": "dup_ids",
            "name": "Duplicate indicators",
            "description": "Uses the same indicator id twice.",
            "strategy_type": "rule_based",
            "position_mode": "long_only",
            "market": {"symbol": "SPY", "timeframe": "1d"},
            "indicators": [
                {"id": "sma_20", "kind": "sma", "inputs": {"source": "close", "length": 20}},
                {"id": "sma_20", "kind": "ema", "inputs": {"source": "close", "length": 20}},
            ],
            "entry": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "gt",
                        "right": {"indicator": "sma_20"},
                    }
                ],
            },
            "exit": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "lt",
                        "right": {"indicator": "sma_20"},
                    }
                ],
            },
        }

        with self.assertRaisesRegex(StrategySchemaError, "Duplicate indicator id 'sma_20'"):
            parse_strategy(payload)

    def test_invalid_operator_is_rejected(self) -> None:
        payload = {
            "schema_version": "v1",
            "strategy_id": "bad_operator",
            "name": "Bad operator",
            "description": "Uses an unsupported operator.",
            "strategy_type": "rule_based",
            "position_mode": "long_only",
            "market": {"symbol": "SPY", "timeframe": "1d"},
            "indicators": [{"id": "sma_20", "kind": "sma", "inputs": {"source": "close", "length": 20}}],
            "entry": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "between",
                        "right": {"indicator": "sma_20"},
                    }
                ],
            },
            "exit": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "lt",
                        "right": {"indicator": "sma_20"},
                    }
                ],
            },
        }

        with self.assertRaisesRegex(StrategySchemaError, "must be one of"):
            parse_strategy(payload)

    def test_invalid_price_field_is_rejected(self) -> None:
        payload = {
            "schema_version": "v1",
            "strategy_id": "bad_price_ref",
            "name": "Bad price ref",
            "description": "Uses open instead of close in a signal.",
            "strategy_type": "rule_based",
            "position_mode": "long_only",
            "market": {"symbol": "SPY", "timeframe": "1d"},
            "indicators": [{"id": "sma_20", "kind": "sma", "inputs": {"source": "close", "length": 20}}],
            "entry": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "open"},
                        "operator": "gt",
                        "right": {"indicator": "sma_20"},
                    }
                ],
            },
            "exit": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "lt",
                        "right": {"indicator": "sma_20"},
                    }
                ],
            },
        }

        with self.assertRaisesRegex(StrategySchemaError, "must be 'close' in v1"):
            parse_strategy(payload)

    def test_non_close_indicator_source_is_rejected(self) -> None:
        payload = {
            "schema_version": "v1",
            "strategy_id": "bad_indicator_source",
            "name": "Bad indicator source",
            "description": "Uses high instead of close for an indicator input.",
            "strategy_type": "rule_based",
            "position_mode": "long_only",
            "market": {"symbol": "SPY", "timeframe": "1d"},
            "indicators": [{"id": "sma_20", "kind": "sma", "inputs": {"source": "high", "length": 20}}],
            "entry": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "gt",
                        "right": {"indicator": "sma_20"},
                    }
                ],
            },
            "exit": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "lt",
                        "right": {"indicator": "sma_20"},
                    }
                ],
            },
        }

        with self.assertRaisesRegex(StrategySchemaError, "inputs.source must be 'close' in v1"):
            parse_strategy(payload)

    def test_malformed_value_ref_is_rejected(self) -> None:
        payload = {
            "schema_version": "v1",
            "strategy_id": "bad_value_ref",
            "name": "Bad value ref",
            "description": "Includes multiple value ref keys.",
            "strategy_type": "rule_based",
            "position_mode": "long_only",
            "market": {"symbol": "SPY", "timeframe": "1d"},
            "indicators": [{"id": "sma_20", "kind": "sma", "inputs": {"source": "close", "length": 20}}],
            "entry": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"indicator": "sma_20", "value": 20},
                        "operator": "gt",
                        "right": {"value": 0},
                    }
                ],
            },
            "exit": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"price": "close"},
                        "operator": "lt",
                        "right": {"indicator": "sma_20"},
                    }
                ],
            },
        }

        with self.assertRaisesRegex(StrategySchemaError, "must contain exactly one of"):
            parse_strategy(payload)

    def test_non_numeric_constant_is_rejected(self) -> None:
        payload = {
            "schema_version": "v1",
            "strategy_id": "bad_constant",
            "name": "Bad constant",
            "description": "Uses a non-numeric constant.",
            "strategy_type": "rule_based",
            "position_mode": "long_only",
            "market": {"symbol": "SPY", "timeframe": "1d"},
            "indicators": [{"id": "rsi_14", "kind": "rsi", "inputs": {"source": "close", "length": 14}}],
            "entry": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"indicator": "rsi_14"},
                        "operator": "lt",
                        "right": {"value": "30"},
                    }
                ],
            },
            "exit": {
                "when": "all",
                "conditions": [
                    {
                        "left": {"indicator": "rsi_14"},
                        "operator": "gte",
                        "right": {"value": 55},
                    }
                ],
            },
        }

        with self.assertRaisesRegex(StrategySchemaError, "value must be numeric"):
            parse_strategy(payload)

    def test_loader_rejects_non_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "strategy.yaml"
            yaml_path.write_text("schema_version: v1\n", encoding="utf-8")

            with self.assertRaisesRegex(StrategySchemaError, "accepts JSON files"):
                load_strategy(yaml_path)

    def test_loader_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            strategy_path = Path(tmp_dir) / "broken.json"
            strategy_path.write_text("{not-json}", encoding="utf-8")

            with self.assertRaisesRegex(StrategySchemaError, "Invalid JSON"):
                load_strategy(strategy_path)

    def test_strategy_round_trip_is_plain_json(self) -> None:
        raw = json.loads((FIXTURES_DIR / "sma_crossover.json").read_text(encoding="utf-8"))
        strategy = parse_strategy(raw)

        self.assertEqual(strategy.name, "Simple SMA Crossover")


if __name__ == "__main__":
    unittest.main()
