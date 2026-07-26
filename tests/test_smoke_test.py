import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.smoke_test import format_smoke_test_result, run_smoke_test, smoke_test_result_to_json


def _write_smoke_repo(root: Path) -> None:
    (root / "data" / "strategies").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "data" / "strategies" / "sma_crossover.json").write_text(
        json.dumps(_strategy_payload()),
        encoding="utf-8",
    )
    _write_ohlcv_fixture(root / "data" / "sample_ohlcv.csv")
    (root / "docs" / "getting-running.md").write_text("# Getting Running\n", encoding="utf-8")


def _strategy_payload() -> dict:
    return {
        "schema_version": "v1",
        "strategy_id": "cli_smoke",
        "name": "CLI Smoke",
        "description": "A compact strategy used to test the smoke workflow.",
        "strategy_type": "rule_based",
        "position_mode": "long_only",
        "market": {"symbol": "TEST", "timeframe": "1d"},
        "indicators": [{"id": "sma_2", "kind": "sma", "inputs": {"source": "close", "length": 2}}],
        "entry": {
            "when": "all",
            "conditions": [{"left": {"price": "close"}, "operator": "gt", "right": {"indicator": "sma_2"}}],
        },
        "exit": {
            "when": "all",
            "conditions": [{"left": {"price": "close"}, "operator": "lt", "right": {"indicator": "sma_2"}}],
        },
    }


def _write_ohlcv_fixture(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "date,open,high,low,close,volume",
                "2026-01-01,10,10,10,10,100",
                "2026-01-02,11,11,11,11,100",
                "2026-01-03,12,12,12,12,100",
                "2026-01-04,9,9,9,9,100",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


class SmokeTestWorkflowTest(unittest.TestCase):
    def test_smoke_test_writes_plan_baseline_and_session_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_smoke_repo(root)

            result = run_smoke_test(repo_root=root)

            self.assertEqual("ok", result.status)
            self.assertTrue(Path(result.research_plan).exists())
            self.assertTrue(Path(result.baseline_metadata).exists())
            self.assertTrue(Path(result.baseline_report).exists())
            self.assertTrue(Path(result.session_manifest).exists())
            self.assertEqual(result.session_manifest_markdown, result.read_first)
            self.assertIn("quant-lab summarize-run-trust", result.next_command)

    def test_smoke_test_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_smoke_repo(root)
            run_smoke_test(repo_root=root)

            with self.assertRaises(FileExistsError):
                run_smoke_test(repo_root=root)

    def test_smoke_test_force_replaces_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_smoke_repo(root)
            run_smoke_test(repo_root=root)

            result = run_smoke_test(repo_root=root, force=True)

            self.assertTrue(Path(result.session_manifest).exists())

    def test_smoke_test_json_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_smoke_repo(root)

            payload = json.loads(smoke_test_result_to_json(run_smoke_test(repo_root=root)))

            self.assertEqual("ok", payload["status"])
            self.assertIn("read_first", payload)
            self.assertIn("next_command", payload)

    def test_smoke_test_human_output_points_to_read_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_smoke_repo(root)

            output = format_smoke_test_result(run_smoke_test(repo_root=root))

            self.assertIn("Quant Lab smoke-test: OK", output)
            self.assertIn("read_first:", output)
            self.assertIn("next_command:", output)
