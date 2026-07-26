import json
import tempfile
import unittest
from pathlib import Path

from quant_lab.health import format_health_report, health_report_to_json, run_doctor


def _write_minimal_repo(root: Path) -> None:
    (root / "data" / "strategies").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    (root / "data" / "sample_ohlcv.csv").write_text("date,open,high,low,close,volume\n", encoding="utf-8")
    (root / "data" / "strategies" / "sma_crossover.json").write_text("{}\n", encoding="utf-8")
    (root / "docs" / "getting-running.md").write_text("# Getting Running\n", encoding="utf-8")


class HealthTest(unittest.TestCase):
    def test_doctor_warns_but_does_not_fail_when_data_cache_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_repo(root)

            report = run_doctor(repo_root=root)

            self.assertEqual("warn", report.status)
            self.assertTrue(any(check.name.endswith("data/cache") and check.status == "warn" for check in report.checks))
            self.assertFalse(any(check.status == "fail" for check in report.checks))

    def test_doctor_fails_when_required_project_files_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            report = run_doctor(repo_root=root)

            self.assertEqual("fail", report.status)
            self.assertTrue(any(check.status == "fail" and "pyproject.toml" in check.name for check in report.checks))

    def test_doctor_json_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_repo(root)

            payload = json.loads(health_report_to_json(run_doctor(repo_root=root)))

            self.assertEqual("warn", payload["status"])
            self.assertEqual("quant-lab research-plan init --help", payload["next_command"])
            self.assertIn("checks", payload)

    def test_format_health_report_prints_status_checks_and_next_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_repo(root)

            output = format_health_report(run_doctor(repo_root=root))

            self.assertIn("Quant Lab doctor: WARN", output)
            self.assertIn("[OK] python:", output)
            self.assertIn("next: quant-lab research-plan init --help", output)
