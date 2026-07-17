from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.run_metadata import fingerprint_file  # noqa: E402


class RunMetadataTests(unittest.TestCase):
    def test_fingerprint_file_hashes_raw_file_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = Path(temp_dir) / "sample.csv"
            contents = b"date,open,high,low,close,volume\n2026-01-01,1,2,1,2,100\n"
            data_path.write_bytes(contents)

            fingerprint = fingerprint_file(data_path)

            self.assertEqual(fingerprint["file_sha256"], hashlib.sha256(contents).hexdigest())
            self.assertEqual(fingerprint["file_size_bytes"], len(contents))
            self.assertTrue(str(fingerprint["modified_at_utc"]).endswith("Z"))

            data_path.write_bytes(contents + b"2026-01-02,2,3,2,3,100\n")
            changed = fingerprint_file(data_path)

            self.assertNotEqual(changed["file_sha256"], fingerprint["file_sha256"])


if __name__ == "__main__":
    unittest.main()
