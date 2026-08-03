"""CLI command handlers for data fetching and starter strategy files."""

from __future__ import annotations

import argparse

from .adjusted_price_audit import fetch_yfinance_adjustment_sample, write_adjusted_price_audit
from .data_source import (
    format_data_cache_inventory,
    format_data_source_inspection,
    inspect_data_source,
    list_data_cache,
)
from .data_fetch import fetch_market_data, write_market_data_csv, write_market_data_provenance
from .strategy_templates import available_strategy_templates, build_strategy_template, write_strategy_template


def audit_adjusted_prices_command(args: argparse.Namespace) -> int:
    expected_dividend_amounts = _parse_expected_dividend_amounts(args.expected_dividend)
    expected_dividend_dates = _merge_dates(
        args.expected_dividend_date,
        list(expected_dividend_amounts),
    )
    comparison = fetch_yfinance_adjustment_sample(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
    )
    audit = write_adjusted_price_audit(
        comparison=comparison,
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        out_dir=args.out,
        expected_dividend_dates=expected_dividend_dates,
        expected_dividend_amounts=expected_dividend_amounts,
        expected_split_dates=args.expected_split_date,
        tolerance=args.tolerance,
    )
    print(f"Adjusted price audit written: {audit.markdown_path}")
    print(f"result: {audit.result}")
    print(f"rows_compared: {audit.compared_rows}")
    print(f"max_close_difference: {audit.max_close_difference}")
    print(f"max_ohlc_difference: {audit.max_ohlc_difference}")
    print(f"dividend_amount_mismatches: {len(audit.dividend_amount_mismatches)}")
    print(f"comparison: {audit.comparison_path}")
    if audit.warnings:
        print("warnings:")
        for warning in audit.warnings:
            print(f"- {warning}")
    return 0


def _parse_expected_dividend_amounts(values: list[str]) -> dict[str, float]:
    expected_amounts: dict[str, float] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("Expected dividend amounts must use YYYY-MM-DD=amount format.")
        date, amount_text = value.split("=", 1)
        if not date:
            raise ValueError("Expected dividend amount is missing a date.")
        try:
            amount = float(amount_text)
        except ValueError as exc:
            raise ValueError(f"Expected dividend amount for {date} is not numeric: {amount_text}") from exc
        if amount <= 0:
            raise ValueError(f"Expected dividend amount for {date} must be positive.")
        expected_amounts[date] = amount
    return expected_amounts


def _merge_dates(primary_dates: list[str], secondary_dates: list[str]) -> list[str]:
    # Preserve user order while removing duplicates, so reports stay predictable.
    merged: list[str] = []
    seen: set[str] = set()
    for date in [*primary_dates, *secondary_dates]:
        if date in seen:
            continue
        seen.add(date)
        merged.append(date)
    return merged


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


def list_data_cache_command(args: argparse.Namespace) -> int:
    inventory = list_data_cache(args.data_dir)
    print(format_data_cache_inventory(inventory))
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
        length=args.length,
    )
    output_path = write_strategy_template(payload, args.out, force=args.force)
    print(f"Strategy template written: {output_path}")
    print(f"template: {args.template}")
    print(f"strategy_id: {payload['strategy_id']}")
    print(f"symbol: {payload['market']['symbol']}")
    if args.length is not None:
        print(f"length: {args.length}")
    return 0
