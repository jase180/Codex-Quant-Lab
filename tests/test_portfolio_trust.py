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
from quant_lab.portfolio_trust import summarize_portfolio_data_trust  # noqa: E402
from quant_lab.run_metadata import fingerprint_file  # noqa: E402


class PortfolioTrustTests(unittest.TestCase):
    def test_summarize_portfolio_data_trust_writes_markdown_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            qqq_data = _write_data(temp_path / "QQQ.csv")
            spy_data = _write_data(temp_path / "SPY.csv")
            _write_provenance(qqq_data, symbol="QQQ")
            _write_provenance(spy_data, symbol="SPY")
            metadata_path = _write_portfolio_metadata(temp_path / "portfolio_metadata.json", qqq_data, spy_data)

            report = summarize_portfolio_data_trust(metadata_path)

            report_path = temp_path / "portfolio_data_trust_report.md"
            self.assertEqual(report.report_path, str(report_path))
            self.assertEqual(report.worst_warning, "none")
            self.assertTrue(report_path.exists())
            markdown = report_path.read_text(encoding="utf-8")
            self.assertIn("# Portfolio Data Trust Report", markdown)
            self.assertIn("| QQQ | reproducible input file | none | 2 | 0 |", markdown)
            self.assertIn("### benchmark: SPY", markdown)
            self.assertIn("Provider: fixture", markdown)

    def test_summarize_portfolio_data_trust_warns_for_changed_symbol_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            qqq_data = _write_data(temp_path / "QQQ.csv")
            spy_data = _write_data(temp_path / "SPY.csv")
            _write_provenance(spy_data, symbol="SPY")
            metadata_path = _write_portfolio_metadata(temp_path / "portfolio_metadata.json", qqq_data, spy_data)
            qqq_data.write_text(
                "date,open,high,low,close,volume\n"
                "2026-01-01,1,2,1,2,100\n"
                "2026-01-02,2,3,2,3,100\n"
                "2026-01-03,3,4,3,4,100\n",
                encoding="utf-8",
            )

            report = summarize_portfolio_data_trust(metadata_path)

            self.assertEqual(report.worst_warning, "critical")
            self.assertIn("symbol QQQ: input file differs from metadata", report.warnings)

    def test_summarize_portfolio_data_trust_treats_missing_provenance_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            qqq_data = _write_data(temp_path / "QQQ.csv")
            spy_data = _write_data(temp_path / "SPY.csv")
            metadata_path = _write_portfolio_metadata(temp_path / "portfolio_metadata.json", qqq_data, spy_data)

            report = summarize_portfolio_data_trust(metadata_path)

            self.assertEqual(report.worst_warning, "warning")
            self.assertIn("symbol QQQ: missing provenance sidecar", report.warnings)
            self.assertIn("benchmark SPY: missing provenance sidecar", report.warnings)

    def test_summarize_portfolio_data_trust_resolves_symbol_paths_from_spec_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_dir = temp_path / "data"
            spec_dir = temp_path / "candidates"
            run_dir = temp_path / "run"
            data_dir.mkdir()
            spec_dir.mkdir()
            run_dir.mkdir()
            qqq_data = _write_data(data_dir / "QQQ.csv")
            spy_data = _write_data(data_dir / "SPY.csv")
            _write_provenance(qqq_data, symbol="QQQ")
            _write_provenance(spy_data, symbol="SPY")
            spec_path = spec_dir / "portfolio.json"
            spec_path.write_text("{}", encoding="utf-8")
            metadata_path = _write_portfolio_metadata(
                run_dir / "portfolio_metadata.json",
                qqq_data,
                spy_data,
                qqq_path="../data/QQQ.csv",
                portfolio_spec_path=spec_path,
            )

            report = summarize_portfolio_data_trust(metadata_path)

            self.assertEqual(report.worst_warning, "none")
            self.assertIn("Resolved path:", report.markdown)
            self.assertIn("QQQ | reproducible input file", report.markdown)

    def test_summarize_portfolio_data_trust_command_prints_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            qqq_data = _write_data(temp_path / "QQQ.csv")
            spy_data = _write_data(temp_path / "SPY.csv")
            metadata_path = _write_portfolio_metadata(temp_path / "portfolio_metadata.json", qqq_data, spy_data)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["summarize-portfolio-data-trust", "--metadata", str(metadata_path)])

            self.assertEqual(exit_code, 0)
            self.assertIn("Portfolio data trust report written:", stdout.getvalue())
            self.assertIn("worst_warning: warning", stdout.getvalue())


def _write_data(path: Path) -> Path:
    path.write_text(
        "date,open,high,low,close,volume\n"
        "2026-01-01,1,2,1,2,100\n"
        "2026-01-02,2,3,2,3,100\n",
        encoding="utf-8",
    )
    return path


def _write_provenance(path: Path, *, symbol: str) -> None:
    path.with_suffix(".provenance.json").write_text(
        json.dumps(
            {
                "provenance_schema_version": "market_data_provenance.v1",
                "provider": "fixture",
                "symbol": symbol,
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


def _write_portfolio_metadata(
    path: Path,
    qqq_data: Path,
    spy_data: Path,
    *,
    qqq_path: str | None = None,
    portfolio_spec_path: Path | None = None,
) -> Path:
    qqq_fingerprint = fingerprint_file(qqq_data)
    spy_fingerprint = fingerprint_file(spy_data)
    payload = {
        "metadata_schema_version": "portfolio_metadata.v1",
        "portfolio_id": "qqq_spy_static_60_40",
        "name": "QQQ SPY Static 60/40",
        "alignment_policy": "intersection",
        "rebalance_frequency": "monthly",
        "portfolio_spec": {
            "path": str(portfolio_spec_path) if portfolio_spec_path is not None else None,
        },
        "symbols": [
            {
                "symbol": "QQQ",
                "path": qqq_path or str(qqq_data),
                "target_weight": 0.6,
                "row_count": 2,
                "aligned_row_count": 2,
                "dropped_rows": 0,
                "start": "2026-01-01",
                "end": "2026-01-02",
                "quality_severity": "none",
                **qqq_fingerprint,
            }
        ],
        "benchmark": {
            "symbol": "SPY",
            "data_path": str(spy_data),
            **spy_fingerprint,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
