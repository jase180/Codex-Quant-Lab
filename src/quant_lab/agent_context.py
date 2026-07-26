"""Build local-agent context bundles from a session manifest."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .research_plan_common import utc_now_iso, write_json_payload
from .session_manifest import SessionArtifact, SessionManifest, load_session_manifest, session_manifest_markdown_path


AGENT_CONTEXT_SCHEMA_VERSION = "agent_context.v1"
AGENT_CONTEXT_JSON_FILENAME = "agent_context_bundle.json"
AGENT_CONTEXT_MARKDOWN_FILENAME = "agent_context_bundle.md"
DEFAULT_MAX_CHARS_PER_FILE = 12_000


@dataclass(frozen=True)
class AgentContextFile:
    kind: str
    role: str
    path: str
    exists: bool
    included: bool
    content: str | None = None
    note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AgentContext:
    schema_version: str
    generated_at_utc: str
    manifest_path: str
    manifest: dict
    operating_rules: list[str]
    read_order: list[str]
    files: list[AgentContextFile]
    next_commands: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "generated_at_utc": self.generated_at_utc,
            "manifest_path": self.manifest_path,
            "manifest": self.manifest,
            "operating_rules": list(self.operating_rules),
            "read_order": list(self.read_order),
            "files": [file.to_dict() for file in self.files],
            "next_commands": list(self.next_commands),
            "warnings": list(self.warnings),
        }


def build_agent_context(
    manifest_path: str | Path,
    *,
    max_chars_per_file: int = DEFAULT_MAX_CHARS_PER_FILE,
    generated_at_utc: str | None = None,
) -> AgentContext:
    if max_chars_per_file < 1:
        raise ValueError("max_chars_per_file must be at least 1")

    manifest_file = Path(manifest_path)
    manifest = load_session_manifest(manifest_file)
    manifest_payload = _normalize_payload_paths(manifest.to_dict())
    artifacts = _context_artifacts(manifest_file, manifest)
    files = [_read_context_file(artifact, max_chars_per_file=max_chars_per_file) for artifact in artifacts]
    return AgentContext(
        schema_version=AGENT_CONTEXT_SCHEMA_VERSION,
        generated_at_utc=generated_at_utc or utc_now_iso(),
        manifest_path=_display_path(manifest_file),
        manifest=manifest_payload,
        operating_rules=_operating_rules(),
        read_order=[file.path for file in files if file.exists],
        files=files,
        next_commands=[_normalize_command_paths(command.command) for command in manifest.commands if command.status != "executed"],
        warnings=[_normalize_command_paths(warning) for warning in manifest.warnings],
    )


def save_agent_context(context: AgentContext, output_dir: str | Path | None = None) -> tuple[str, str]:
    destination = Path(output_dir or context.manifest["output_dir"])
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / AGENT_CONTEXT_JSON_FILENAME
    markdown_path = destination / AGENT_CONTEXT_MARKDOWN_FILENAME
    write_json_payload(json_path, context.to_dict())
    markdown_path.write_text(format_agent_context_markdown(context), encoding="utf-8")
    return _display_path(json_path), _display_path(markdown_path)


def format_agent_context_markdown(context: AgentContext) -> str:
    return "\n".join(
        [
            f"# Agent Context Bundle: {context.manifest['session_id']}",
            "",
            "Report role: bounded advisor input.",
            "",
            "## Operating Rules",
            "",
            *_bullet_lines(context.operating_rules),
            "",
            "## Session",
            "",
            f"- Status: `{context.manifest['current_status']}`",
            f"- Experiment: `{context.manifest['experiment_id']}`",
            f"- Title: {context.manifest['title']}",
            f"- Hypothesis: {context.manifest['hypothesis']}",
            f"- Manifest: `{context.manifest_path}`",
            "",
            "## Read Order",
            "",
            *_bullet_lines(f"`{path}`" for path in context.read_order),
            "",
            "## Next Commands",
            "",
            *_code_block_lines(context.next_commands),
            "",
            "## Warnings",
            "",
            *_bullet_lines(context.warnings),
            "",
            "## Included Files",
            "",
            *_file_sections(context.files),
            "",
        ]
    )


def agent_context_to_json(context: AgentContext) -> str:
    return json.dumps(context.to_dict(), indent=2, sort_keys=True)


def _context_artifacts(manifest_path: Path, manifest: SessionManifest) -> list[SessionArtifact]:
    artifacts = [
        SessionArtifact(kind="session_manifest_json", path=str(manifest_path), role="main"),
        SessionArtifact(kind="session_manifest_markdown", path=str(session_manifest_markdown_path(manifest.output_dir)), role="main"),
        SessionArtifact(kind="research_plan", path=manifest.plan_path, role="plan"),
    ]
    if manifest.conclusion_path:
        artifacts.append(SessionArtifact(kind="experiment_conclusion", path=manifest.conclusion_path, role="main"))
        artifacts.append(
            SessionArtifact(kind="experiment_conclusion_json", path=str(Path(manifest.conclusion_path).with_suffix(".json")), role="main")
        )

    seen_paths = {_normalized_path(artifact.path) for artifact in artifacts}
    for artifact in manifest.key_artifacts:
        key = _normalized_path(artifact.path)
        if key not in seen_paths:
            artifacts.append(artifact)
            seen_paths.add(key)
    return artifacts


def _read_context_file(artifact: SessionArtifact, *, max_chars_per_file: int) -> AgentContextFile:
    path = Path(artifact.path)
    if not path.exists():
        return AgentContextFile(
            kind=artifact.kind,
            role=artifact.role,
            path=_display_path(path),
            exists=False,
            included=False,
            note="File is referenced by the session manifest but does not exist.",
        )
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return AgentContextFile(
            kind=artifact.kind,
            role=artifact.role,
            path=_display_path(path),
            exists=True,
            included=False,
            note="File is not UTF-8 text and was not embedded.",
        )

    if len(content) > max_chars_per_file:
        return AgentContextFile(
            kind=artifact.kind,
            role=artifact.role,
            path=_display_path(path),
            exists=True,
            included=True,
            content=content[:max_chars_per_file],
            note=f"Content truncated to {max_chars_per_file} characters.",
        )
    return AgentContextFile(
        kind=artifact.kind,
        role=artifact.role,
        path=_display_path(path),
        exists=True,
        included=True,
        content=content,
    )


def _operating_rules() -> list[str]:
    return [
        "Recommend the next experiment or analysis step; do not edit source code.",
        "Use saved artifacts as the source of truth; do not rely on chat history.",
        "Treat weak samples, missing trust reports, and benchmark underperformance as real warnings.",
        "Return a bounded recommendation and stop before running commands.",
    ]


def _file_sections(files: list[AgentContextFile]) -> list[str]:
    lines: list[str] = []
    for file in files:
        lines.extend(
            [
                f"### {file.kind}",
                "",
                f"- Path: `{file.path}`",
                f"- Role: `{file.role}`",
                f"- Exists: `{file.exists}`",
                f"- Included: `{file.included}`",
            ]
        )
        if file.note:
            lines.append(f"- Note: {file.note}")
        if file.content is not None:
            lines.extend(["", "```text", file.content.rstrip(), "```"])
        lines.append("")
    return lines or ["- none"]


def _code_block_lines(commands: list[str]) -> list[str]:
    if not commands:
        return ["- none"]
    lines: list[str] = []
    for command in commands:
        lines.extend(["```bash", command, "```", ""])
    return lines


def _bullet_lines(items) -> list[str]:
    values = [str(item) for item in items if str(item)]
    return [f"- {item}" for item in values] if values else ["- none"]


def _normalized_path(path: str | Path) -> str:
    return str(Path(path))


def _display_path(path: str | Path) -> str:
    return Path(path).as_posix()


def _normalize_command_paths(command: str) -> str:
    return command.replace("\\", "/")


def _normalize_payload_paths(payload):
    if isinstance(payload, dict):
        return {key: _normalize_payload_paths(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_normalize_payload_paths(value) for value in payload]
    if isinstance(payload, str):
        return _normalize_command_paths(payload)
    return payload
