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
