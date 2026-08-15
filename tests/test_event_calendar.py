from __future__ import annotations

import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path

from quant_lab.cli import main
from quant_lab.event_calendar import (
    EVENT_CALENDAR_COLUMNS,
    generate_calendar_rebalance_event_calendar,
    inspect_event_calendar,
)


class EventCalendarTest(unittest.TestCase):
    def test_generate_calendar_rebalance_events_from_dates_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            reference_data = temp_path / "reference.csv"
            _write_reference_data(reference_data)
            out_path = temp_path / "events.csv"

            result = generate_calendar_rebalance_event_calendar(
                reference_data_path=reference_data,
                out_path=out_path,
                start="2020-01-01",
                end="2020-06-30",
                window_trading_days=1,
                created_at_utc="2026-08-14T00:00:00Z",
            )

            self.assertEqual(out_path, result.csv_path)
            self.assertTrue(result.provenance_path.exists())
            self.assertGreater(result.event_count, 0)
            self.assertEqual(result.event_count, sum(result.counts_by_type.values()))

            rows = _read_rows(out_path)
            self.assertEqual(EVENT_CALENDAR_COLUMNS, list(rows[0].keys()))
            self.assertTrue(all(row["generated_without_return_data"] == "true" for row in rows))
            self.assertIn("month_end", {row["event_type"] for row in rows})
            self.assertIn("quarter_end", {row["event_type"] for row in rows})

    def test_inspect_event_calendar_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.csv"
            _write_event_rows(
                path,
                [
                    _event_row("duplicate", "month_end", "2020-01-31"),
                    _event_row("duplicate", "quarter_end", "2020-03-31"),
                ],
            )

            inspection = inspect_event_calendar(path)

            self.assertFalse(inspection.is_valid)
            self.assertIn("duplicate event_id", "\n".join(inspection.invalid_rows))

    def test_cli_event_calendar_generate_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            reference_data = temp_path / "reference.csv"
            _write_reference_data(reference_data)
            out_path = temp_path / "events.csv"

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                generate_exit_code = main(
                    [
                        "event-calendar",
                        "generate",
                        "--reference-data",
                        str(reference_data),
                        "--out",
                        str(out_path),
                        "--start",
                        "2020-01-01",
                        "--end",
                        "2020-06-30",
                        "--window-trading-days",
                        "1",
                        "--created-at-utc",
                        "2026-08-14T00:00:00Z",
                    ]
                )

            self.assertEqual(0, generate_exit_code)
            self.assertIn("Event Calendar Generated", stdout.getvalue())

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                inspect_exit_code = main(
                    ["event-calendar", "inspect", "--calendar", str(out_path)]
                )

            self.assertEqual(0, inspect_exit_code)
            self.assertIn("Status: valid", stdout.getvalue())


def _write_reference_data(path: Path) -> None:
    # The price columns are intentionally silly. The generator should only use
    # Date; this protects the event calendar from being selected from returns.
    rows = [
        ("2020-01-29", 100),
        ("2020-01-30", 999),
        ("2020-01-31", 50),
        ("2020-02-03", 500),
        ("2020-02-27", 101),
        ("2020-02-28", 1),
        ("2020-03-02", 250),
        ("2020-03-30", 300),
        ("2020-03-31", 10),
        ("2020-04-01", 400),
        ("2020-04-29", 100),
        ("2020-04-30", 100),
        ("2020-05-01", 100),
        ("2020-05-28", 100),
        ("2020-05-29", 100),
        ("2020-06-01", 100),
        ("2020-06-29", 100),
        ("2020-06-30", 100),
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Open", "High", "Low", "Close", "Volume"])
        writer.writeheader()
        for row_date, price in rows:
            writer.writerow(
                {
                    "Date": row_date,
                    "Open": price,
                    "High": price,
                    "Low": price,
                    "Close": price,
                    "Volume": 1000,
                }
            )


def _event_row(event_id: str, event_type: str, event_date: str) -> dict[str, str]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "event_date": event_date,
        "window_start": event_date,
        "window_end": event_date,
        "source_name": "test",
        "source_url_or_note": "test",
        "generated_without_return_data": "true",
        "created_at_utc": "2026-08-14T00:00:00Z",
    }


def _write_event_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_CALENDAR_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
