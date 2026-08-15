"""CLI commands for generated research event calendars."""

from __future__ import annotations

import argparse

from .event_calendar import (
    format_event_calendar_generation,
    format_event_calendar_inspection,
    generate_calendar_rebalance_event_calendar,
    inspect_event_calendar,
)


def event_calendar_generate_command(args: argparse.Namespace) -> int:
    result = generate_calendar_rebalance_event_calendar(
        reference_data_path=args.reference_data,
        out_path=args.out,
        start=args.start,
        end=args.end,
        window_trading_days=args.window_trading_days,
        created_at_utc=args.created_at_utc,
        force=args.force,
    )
    print(format_event_calendar_generation(result))
    return 0


def event_calendar_inspect_command(args: argparse.Namespace) -> int:
    inspection = inspect_event_calendar(args.calendar)
    print(format_event_calendar_inspection(inspection))
    return 0 if inspection.is_valid else 1
