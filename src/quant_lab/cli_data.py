"""CLI command handlers for data fetching and starter strategy files."""

from __future__ import annotations

import argparse

from .data_source import format_data_source_inspection, inspect_data_source
from .data_fetch import fetch_market_data, write_market_data_csv, write_market_data_provenance
from .strategy_templates import available_strategy_templates, build_strategy_template, write_strategy_template


def fetch_command(args: argparse.Namespace) -> int:
    data = fetch_market_data(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        interval=args.interval,
    )
    csv_path = write_market_data_csv(
        data=data,
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        output_dir=args.out,
    )
    provenance_path = write_market_data_provenance(
        csv_path=csv_path,
        data=data,
        symbol=args.symbol,
        requested_start=args.start,
        requested_end=args.end,
        interval=args.interval,
    )
    print(f"Fetched {len(data)} rows for {args.symbol.upper()}")
    print(f"data: {csv_path}")
    print(f"provenance: {provenance_path}")
    return 0


def show_data_source_command(args: argparse.Namespace) -> int:
    inspection = inspect_data_source(args.data)
    print(format_data_source_inspection(inspection))
    return 0


def list_strategy_templates_command(args: argparse.Namespace) -> int:
    for template_name in available_strategy_templates():
        print(template_name)
    return 0


def new_strategy_command(args: argparse.Namespace) -> int:
    payload = build_strategy_template(
        args.template,
        symbol=args.symbol,
        strategy_id=args.strategy_id,
        name=args.name,
    )
    output_path = write_strategy_template(payload, args.out, force=args.force)
    print(f"Strategy template written: {output_path}")
    print(f"template: {args.template}")
    print(f"strategy_id: {payload['strategy_id']}")
    print(f"symbol: {payload['market']['symbol']}")
    return 0
