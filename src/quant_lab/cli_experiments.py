"""CLI command handlers for experiment registry workflows."""

from __future__ import annotations

import argparse
from pathlib import Path

from .experiment_summary import format_experiment_decision_draft, format_experiment_evidence_summary
from .research_index import load_research_index
from .research_registry import (
    append_experiment_record,
    create_experiment_decision,
    create_experiment_record,
    decide_experiment_record,
    filter_experiments,
    find_experiment,
    format_experiment_csv,
    format_experiment_detail,
    format_experiment_table,
    link_runs_to_experiment,
    load_experiments,
    next_experiment_id,
    normalize_tags,
    replace_experiment_record,
    update_experiment_record,
)


def new_experiment_command(args: argparse.Namespace) -> int:
    records = load_experiments(args.experiments_path)
    experiment_id = args.experiment_id or next_experiment_id(records)
    record = create_experiment_record(
        experiment_id=experiment_id,
        title=args.title,
        hypothesis=args.hypothesis,
        status=args.status,
        tags=normalize_tags(args.tag),
        strategy_path=args.strategy,
        data_path=args.data,
        notes=args.notes,
    )
    registry_path = append_experiment_record(record, args.experiments_path)

    print(f"Experiment created: {record.experiment_id}")
    print(f"registry: {registry_path}")
    print(f"status: {record.status}")
    print(f"title: {record.title}")
    return 0


def list_experiments_command(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")

    records = load_experiments(args.experiments_path)
    records = filter_experiments(records, status=args.status, tag=args.tag)
    records = records[: args.limit]

    if not records:
        print(f"No experiments found in {args.experiments_path}")
        return 0

    if args.csv:
        print(format_experiment_csv(records))
    else:
        print(format_experiment_table(records))
    return 0


def show_experiment_command(args: argparse.Namespace) -> int:
    records = load_experiments(args.experiments_path)
    record = find_experiment(records, args.experiment_id)
    print(format_experiment_detail(record))
    return 0


def update_experiment_command(args: argparse.Namespace) -> int:
    if args.status is None and args.decision is None and args.notes is None and not args.tag:
        raise ValueError("update-experiment requires at least one of --status, --decision, --notes, or --tag")

    records = load_experiments(args.experiments_path)
    record = find_experiment(records, args.experiment_id)
    updated = update_experiment_record(
        record,
        status=args.status,
        decision=args.decision,
        notes=args.notes,
        add_tags=args.tag,
    )
    registry_path = replace_experiment_record(updated, args.experiments_path)

    print(f"Experiment updated: {updated.experiment_id}")
    print(f"registry: {registry_path}")
    print(f"status: {updated.status}")
    if updated.decision is not None:
        print(f"decision: {updated.decision}")
    return 0


def decide_experiment_command(args: argparse.Namespace) -> int:
    records = load_experiments(args.experiments_path)
    record = find_experiment(records, args.experiment_id)
    decision_record = create_experiment_decision(
        outcome=args.outcome,
        rationale=args.rationale,
        supporting_run=args.supporting_run,
        contradicting_run=args.contradicting_run,
        next_action=args.next_action,
    )
    updated = decide_experiment_record(record, decision_record, add_tags=args.tag)
    registry_path = replace_experiment_record(updated, args.experiments_path)

    print(f"Experiment decided: {updated.experiment_id}")
    print(f"registry: {registry_path}")
    print(f"status: {updated.status}")
    print(f"outcome: {decision_record.outcome}")
    print(f"rationale: {decision_record.rationale}")
    if decision_record.next_action is not None:
        print(f"next_action: {decision_record.next_action}")
    return 0


def link_run_command(args: argparse.Namespace) -> int:
    metadata_paths = [str(Path(metadata_path)) for metadata_path in args.metadata]
    missing_paths = [metadata_path for metadata_path in metadata_paths if not Path(metadata_path).exists()]
    if missing_paths:
        raise FileNotFoundError(f"run metadata file not found: {missing_paths[0]}")

    records = load_experiments(args.experiments_path)
    record = find_experiment(records, args.experiment_id)
    updated = link_runs_to_experiment(record, metadata_paths)
    registry_path = replace_experiment_record(updated, args.experiments_path)

    print(f"Experiment linked: {updated.experiment_id}")
    print(f"registry: {registry_path}")
    print(f"linked_runs: {len(updated.linked_runs)}")
    return 0


def summarize_experiment_command(args: argparse.Namespace) -> int:
    if args.recent_limit < 1:
        raise ValueError("--recent-limit must be at least 1")

    records = load_experiments(args.experiments_path)
    experiment = find_experiment(records, args.experiment_id)
    index_records = load_research_index(args.index_path)
    print(
        format_experiment_evidence_summary(
            experiment,
            index_records,
            recent_limit=args.recent_limit,
        )
    )
    return 0


def draft_decision_command(args: argparse.Namespace) -> int:
    records = load_experiments(args.experiments_path)
    experiment = find_experiment(records, args.experiment_id)
    index_records = load_research_index(args.index_path)
    print(format_experiment_decision_draft(experiment, index_records))
    return 0
