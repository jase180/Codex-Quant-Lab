import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.cli import main


def _write_minimal_repo(root: Path) -> None:
    (root / "data" / "strategies").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    (root / "data" / "sample_ohlcv.csv").write_text("date,open,high,low,close,volume\n", encoding="utf-8")
    (root / "data" / "strategies" / "sma_crossover.json").write_text("{}\n", encoding="utf-8")
    (root / "docs" / "getting-running.md").write_text("# Getting Running\n", encoding="utf-8")


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
        "description": "A compact strategy used to test the CLI runner.",
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


class CliHealthTest(unittest.TestCase):
    def test_doctor_prints_human_report_and_returns_zero_for_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_repo(root)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["doctor", "--repo-root", str(root)])

            output = stdout.getvalue()
            self.assertEqual(0, exit_code)
            self.assertIn("Quant Lab doctor: WARN", output)
            self.assertIn("data/cache", output)

    def test_doctor_returns_nonzero_for_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["doctor", "--repo-root", tmpdir])

            output = stdout.getvalue()
            self.assertEqual(1, exit_code)
            self.assertIn("Quant Lab doctor: FAIL", output)
            self.assertIn("pyproject.toml", output)

    def test_doctor_json_output_is_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_repo(root)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["doctor", "--repo-root", str(root), "--json"])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual("warn", payload["status"])
            self.assertEqual("quant-lab research-plan init --help", payload["next_command"])

    def test_smoke_test_prints_read_first_and_next_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_smoke_repo(root)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["smoke-test", "--repo-root", str(root)])

            output = stdout.getvalue()
            self.assertEqual(0, exit_code)
            self.assertIn("Quant Lab smoke-test: OK", output)
            self.assertIn("read_first:", output)
            self.assertIn("next_command:", output)

    def test_smoke_test_json_output_is_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_smoke_repo(root)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["smoke-test", "--repo-root", str(root), "--json"])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual("ok", payload["status"])
            self.assertIn("session_manifest", payload)
