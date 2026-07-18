from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.cli import main  # noqa: E402
from quant_lab.run_inspection import format_run_verification, verify_run_input_file  # noqa: E402
from quant_lab.run_metadata import fingerprint_file  # noqa: E402
from quant_lab.run_trust import summarize_run_trust  # noqa: E402


class RunInspectionTests(unittest.TestCase):
    def test_verify_run_input_file_reports_matching_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_path = _write_data(temp_path / "ohlcv.csv")
            metadata_path = _write_metadata(temp_path / "run_metadata.json", data_path)

            verification = verify_run_input_file(metadata_path)
            output = format_run_verification(verification)

            self.assertEqual(verification["result"], "reproducible input file")
            self.assertEqual(verification["checks"]["file_sha256"]["status"], "match")
            self.assertEqual(verification["checks"]["row_count"]["status"], "match")
            self.assertEqual(verification["checks"]["date_range"]["status"], "match")
            self.assertIn("file_sha256: match", output)
            self.assertIn("result: reproducible input file", output)

    def test_verify_run_input_file_reports_changed_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_path = _write_data(temp_path / "ohlcv.csv")
            metadata_path = _write_metadata(temp_path / "run_metadata.json", data_path)
            data_path.write_text(
                "date,open,high,low,close,volume\n"
                "2026-01-01,1,2,1,2,100\n"
                "2026-01-02,2,3,2,3,100\n"
                "2026-01-03,3,4,3,4,100\n",
                encoding="utf-8",
            )

            verification = verify_run_input_file(metadata_path)

            self.assertEqual(verification["result"], "input file differs from metadata")
            self.assertEqual(verification["checks"]["file_sha256"]["status"], "mismatch")
            self.assertEqual(verification["checks"]["row_count"]["status"], "mismatch")
            self.assertEqual(verification["checks"]["date_range"]["status"], "mismatch")

    def test_verify_run_input_file_reports_missing_data_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_path = _write_data(temp_path / "ohlcv.csv")
            metadata_path = _write_metadata(temp_path / "run_metadata.json", data_path)
            data_path.unlink()

            verification = verify_run_input_file(metadata_path)

            self.assertEqual(verification["result"], "data file missing")
            self.assertEqual(verification["checks"]["file_exists"]["status"], "missing")

    def test_verify_run_command_prints_verification_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_path = _write_data(temp_path / "ohlcv.csv")
            metadata_path = _write_metadata(temp_path / "run_metadata.json", data_path)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["verify-run", "--metadata", str(metadata_path)])

            self.assertEqual(exit_code, 0)
            self.assertIn("Run Verification", stdout.getvalue())
            self.assertIn("file_sha256: match", stdout.getvalue())

    def test_summarize_run_trust_writes_markdown_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_path = _write_data(temp_path / "ohlcv.csv")
            provenance_path = data_path.with_suffix(".provenance.json")
            provenance_path.write_text(
                json.dumps(
                    {
                        "provenance_schema_version": "market_data_provenance.v1",
                        "provider": "fixture",
                        "symbol": "QQQ",
                        "requested_start": "2026-01-01",
                        "requested_end": "2026-01-31",
                        "data_start": "2026-01-01",
                        "data_end": "2026-01-02",
                        "fetched_at_utc": "2026-02-01T00:00:00Z",
                        "row_count": 2,
                    }
                ),
                encoding="utf-8",
            )
            quality_path = _write_data_quality(temp_path / "data_quality.json")
            metadata_path = _write_metadata(
                temp_path / "run_metadata.json",
                data_path,
                data_quality_path=quality_path,
            )

            report = summarize_run_trust(metadata_path)

            report_path = temp_path / "run_trust_report.md"
            self.assertEqual(report.report_path, str(report_path))
            self.assertEqual(report.worst_warning, "none")
            self.assertTrue(report_path.exists())
            markdown = report_path.read_text(encoding="utf-8")
            self.assertIn("# Run Trust Report", markdown)
            self.assertIn("Verification result: reproducible input file", markdown)
            self.assertIn("Provider: fixture", markdown)
            self.assertIn("Worst severity: none", markdown)

    def test_summarize_run_trust_warns_for_changed_data_and_missing_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_path = _write_data(temp_path / "ohlcv.csv")
            metadata_path = _write_metadata(temp_path / "run_metadata.json", data_path)
            data_path.write_text(
                "date,open,high,low,close,volume\n"
                "2026-01-01,1,2,1,2,100\n"
                "2026-01-02,2,3,2,3,100\n"
                "2026-01-03,3,4,3,4,100\n",
                encoding="utf-8",
            )

            report = summarize_run_trust(metadata_path)

            self.assertEqual(report.worst_warning, "critical")
            self.assertIn("input file differs from metadata", report.warnings)
            self.assertIn("data quality artifact missing", report.warnings)
            self.assertIn("missing provenance sidecar", report.warnings)

    def test_summarize_run_trust_treats_missing_provenance_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_path = _write_data(temp_path / "ohlcv.csv")
            quality_path = _write_data_quality(temp_path / "data_quality.json")
            metadata_path = _write_metadata(
                temp_path / "run_metadata.json",
                data_path,
                data_quality_path=quality_path,
            )

            report = summarize_run_trust(metadata_path)

            self.assertEqual(report.worst_warning, "warning")
            self.assertIn("missing provenance sidecar", report.warnings)

    def test_summarize_run_trust_command_prints_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_path = _write_data(temp_path / "ohlcv.csv")
            quality_path = _write_data_quality(temp_path / "data_quality.json")
            metadata_path = _write_metadata(
                temp_path / "run_metadata.json",
                data_path,
                data_quality_path=quality_path,
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["summarize-run-trust", "--metadata", str(metadata_path)])

            self.assertEqual(exit_code, 0)
            self.assertIn("Run trust report written:", stdout.getvalue())
            self.assertIn("verification_result: reproducible input file", stdout.getvalue())


def _write_data(path: Path) -> Path:
    path.write_text(
        "date,open,high,low,close,volume\n"
        "2026-01-01,1,2,1,2,100\n"
        "2026-01-02,2,3,2,3,100\n",
        encoding="utf-8",
    )
    return path


def _write_metadata(path: Path, data_path: Path, data_quality_path: Path | None = None) -> Path:
    fingerprint = fingerprint_file(data_path)
    payload = {
        "metadata_schema_version": "run_metadata.v1",
        "strategy": {"strategy_id": "fixture_strategy"},
        "data": {
            "path": str(data_path),
            "row_count": 2,
            "start": "2026-01-01",
            "end": "2026-01-02",
            "symbol": "QQQ",
            **fingerprint,
        },
        "artifacts": {},
    }
    if data_quality_path is not None:
        payload["artifacts"]["data_quality"] = str(data_quality_path)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_data_quality(path: Path) -> Path:
    payload = {
        "row_count": 2,
        "start": "2026-01-01",
        "end": "2026-01-02",
        "duplicate_dates": 0,
        "missing_ohlcv_values": 0,
        "zero_volume_rows": 0,
        "non_positive_price_rows": 0,
        "findings": [],
        "warnings": [],
        "worst_severity": "none",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
