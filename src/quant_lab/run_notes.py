"""Research note helpers shared by run and sweep workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_research_note(args: argparse.Namespace) -> str | None:
    if getattr(args, "note", None) is not None:
        note = str(args.note).strip()
        return note if note else None
    if getattr(args, "note_file", None) is not None:
        note = Path(args.note_file).read_text(encoding="utf-8").strip()
        return note if note else None
    return None


def save_research_note(note: str, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    note_path = destination / "research_note.md"
    note_path.write_text(note.rstrip() + "\n", encoding="utf-8")
    return str(note_path)


def research_note_summary_line(args: argparse.Namespace, output_dir: str | Path) -> str:
    if getattr(args, "note", None) is None and getattr(args, "note_file", None) is None:
        return ""
    return f"- Research note: `{Path(output_dir) / 'research_note.md'}`"


def note_command_lines(args: argparse.Namespace) -> list[str]:
    if getattr(args, "note", None) is not None:
        return [f"  --note {json.dumps(str(args.note))} \\"]
    if getattr(args, "note_file", None) is not None:
        return [f"  --note-file {args.note_file} \\"]
    return []
