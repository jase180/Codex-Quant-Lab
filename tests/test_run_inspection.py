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


def _write_data(path: Path) -> Path:
    path.write_text(
        "date,open,high,low,close,volume\n"
        "2026-01-01,1,2,1,2,100\n"
        "2026-01-02,2,3,2,3,100\n",
        encoding="utf-8",
    )
    return path


def _write_metadata(path: Path, data_path: Path) -> Path:
    fingerprint = fingerprint_file(data_path)
    payload = {
        "metadata_schema_version": "run_metadata.v1",
        "data": {
            "path": str(data_path),
            "row_count": 2,
            "start": "2026-01-01",
            "end": "2026-01-02",
            **fingerprint,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
