"""CLI command handlers for session manifests."""

from __future__ import annotations

import argparse

from .session_manifest import format_session_status, load_session_manifest


def session_status_command(args: argparse.Namespace) -> int:
    manifest = load_session_manifest(args.manifest)
    print(format_session_status(manifest))
    return 0
