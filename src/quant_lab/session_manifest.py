"""Session manifest model and deterministic Markdown formatter."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json
from pathlib import Path
from typing import Iterable

from .research_plan_common import utc_now_iso, validate_required_text_fields, write_json_payload


SESSION_MANIFEST_SCHEMA_VERSION = "session_manifest.v1"
SESSION_MANIFEST_JSON_FILENAME = "session_manifest.json"
SESSION_MANIFEST_MARKDOWN_FILENAME = "session_manifest.md"
COMMAND_STATUSES = {"planned", "suggested", "executed", "unknown"}
ARTIFACT_ROLES = {"main", "supporting", "raw_audit", "plan", "decision", "unknown"}
MANIFEST_STATUSES = {"planned", "in_progress", "needs_conclusion", "needs_decision", "complete", "unknown"}


@dataclass(frozen=True)
class SessionCommand:
    """One command connected to the research session.

    The manifest is allowed to know about commands the workflow suggested, but
    it should only mark a command `executed` when a future CLI command can prove
    that from saved artifacts. This keeps resume/replay state honest.
    """

    label: str
    command: str
    status: str = "suggested"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SessionArtifact:
    """Pointer to one important file produced or expected by a session."""

    kind: str
    path: str
    role: str = "supporting"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SessionManifest:
    schema_version: str
    session_id: str
    experiment_id: str
    title: str
    hypothesis: str
    created_at_utc: str
    updated_at_utc: str
    plan_path: str
    output_dir: str
    data_sources: list[str] = field(default_factory=list)
    strategy_paths: list[str] = field(default_factory=list)
    commands: list[SessionCommand] = field(default_factory=list)
    key_artifacts: list[SessionArtifact] = field(default_factory=list)
    conclusion_path: str | None = None
    decision_path: str | None = None
    current_status: str = "unknown"
    outstanding_next_steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "experiment_id": self.experiment_id,
            "title": self.title,
            "hypothesis": self.hypothesis,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "plan_path": self.plan_path,
            "output_dir": self.output_dir,
            "data_sources": list(self.data_sources),
            "strategy_paths": list(self.strategy_paths),
            "commands": [command.to_dict() for command in self.commands],
            "key_artifacts": [artifact.to_dict() for artifact in self.key_artifacts],
            "conclusion_path": self.conclusion_path,
            "decision_path": self.decision_path,
            "current_status": self.current_status,
            "outstanding_next_steps": list(self.outstanding_next_steps),
            "warnings": list(self.warnings),
        }


def create_session_manifest(
    *,
    session_id: str,
    experiment_id: str,
    title: str,
    hypothesis: str,
    plan_path: str | Path,
    output_dir: str | Path,
    data_sources: Iterable[str | Path] = (),
    strategy_paths: Iterable[str | Path] = (),
    commands: Iterable[SessionCommand] = (),
    key_artifacts: Iterable[SessionArtifact] = (),
    conclusion_path: str | Path | None = None,
    decision_path: str | Path | None = None,
    current_status: str = "unknown",
    outstanding_next_steps: Iterable[str] = (),
    warnings: Iterable[str] = (),
    created_at_utc: str | None = None,
    updated_at_utc: str | None = None,
) -> SessionManifest:
    timestamp = created_at_utc or utc_now_iso()
    manifest = SessionManifest(
        schema_version=SESSION_MANIFEST_SCHEMA_VERSION,
        session_id=session_id.strip(),
        experiment_id=experiment_id.strip(),
        title=title.strip(),
        hypothesis=hypothesis.strip(),
        created_at_utc=timestamp,
        updated_at_utc=updated_at_utc or timestamp,
        plan_path=str(plan_path),
        output_dir=str(output_dir),
        data_sources=_dedupe_strings(data_sources),
        strategy_paths=_dedupe_strings(strategy_paths),
        commands=list(commands),
        key_artifacts=list(key_artifacts),
        conclusion_path=_optional_path(conclusion_path),
        decision_path=_optional_path(decision_path),
        current_status=current_status.strip() or "unknown",
        outstanding_next_steps=_dedupe_strings(outstanding_next_steps),
        warnings=_dedupe_strings(warnings),
    )
    validate_session_manifest(manifest)
    return manifest


def validate_session_manifest(manifest: SessionManifest) -> None:
    required_fields = {
        "schema_version": manifest.schema_version,
        "session_id": manifest.session_id,
        "experiment_id": manifest.experiment_id,
        "title": manifest.title,
        "hypothesis": manifest.hypothesis,
        "created_at_utc": manifest.created_at_utc,
        "updated_at_utc": manifest.updated_at_utc,
        "plan_path": manifest.plan_path,
        "output_dir": manifest.output_dir,
        "current_status": manifest.current_status,
    }
    validate_required_text_fields(required_fields, context="session manifest")
    if manifest.schema_version != SESSION_MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"unsupported session manifest schema: {manifest.schema_version}")
    if manifest.current_status not in MANIFEST_STATUSES:
        raise ValueError(f"session manifest current_status must be one of {sorted(MANIFEST_STATUSES)}")
    for command in manifest.commands:
        _validate_command(command)
    for artifact in manifest.key_artifacts:
        _validate_artifact(artifact)


def session_manifest_json_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / SESSION_MANIFEST_JSON_FILENAME


def session_manifest_markdown_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / SESSION_MANIFEST_MARKDOWN_FILENAME


def save_session_manifest(manifest: SessionManifest) -> tuple[str, str]:
    validate_session_manifest(manifest)
    output_dir = Path(manifest.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = session_manifest_json_path(output_dir)
    write_json_payload(json_path, manifest.to_dict())

    markdown_path = session_manifest_markdown_path(output_dir)
    markdown_path.write_text(format_session_manifest_markdown(manifest), encoding="utf-8")
    return str(json_path), str(markdown_path)


def replace_session_manifest(manifest: SessionManifest) -> tuple[str, str]:
    """Overwrite an existing manifest after another command updates session state."""

    return save_session_manifest(manifest)


def load_session_manifest(manifest_path: str | Path) -> SessionManifest:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    manifest = SessionManifest(
        schema_version=str(payload.get("schema_version", "")),
        session_id=str(payload.get("session_id", "")),
        experiment_id=str(payload.get("experiment_id", "")),
        title=str(payload.get("title", "")),
        hypothesis=str(payload.get("hypothesis", "")),
        created_at_utc=str(payload.get("created_at_utc", "")),
        updated_at_utc=str(payload.get("updated_at_utc", "")),
        plan_path=str(payload.get("plan_path", "")),
        output_dir=str(payload.get("output_dir", "")),
        data_sources=[str(item) for item in payload.get("data_sources", [])],
        strategy_paths=[str(item) for item in payload.get("strategy_paths", [])],
        commands=[_command_from_dict(item) for item in payload.get("commands", [])],
        key_artifacts=[_artifact_from_dict(item) for item in payload.get("key_artifacts", [])],
        conclusion_path=_optional_str(payload.get("conclusion_path")),
        decision_path=_optional_str(payload.get("decision_path")),
        current_status=str(payload.get("current_status", "unknown")),
        outstanding_next_steps=[str(item) for item in payload.get("outstanding_next_steps", [])],
        warnings=[str(item) for item in payload.get("warnings", [])],
    )
    validate_session_manifest(manifest)
    return manifest


def update_manifest_after_conclusion(
    manifest: SessionManifest,
    *,
    conclusion_markdown_path: str | Path,
    conclusion_json_path: str | Path,
    agent_context_path: str | Path,
    next_command: str | None = None,
    updated_at_utc: str | None = None,
) -> SessionManifest:
    next_steps = []
    commands = [command for command in manifest.commands if command.label != "Recommended next step: conclude_experiment"]
    if manifest.decision_path is None:
        next_steps = ["draft_decision: The canonical conclusion exists; draft a conservative decision before writing it to the registry."]
        if next_command is not None:
            commands.append(
                SessionCommand(
                    label="Recommended next step: draft_decision",
                    command=next_command,
                    status="suggested",
                )
            )

    return replace(
        manifest,
        updated_at_utc=updated_at_utc or utc_now_iso(),
        commands=commands,
        key_artifacts=_upsert_artifacts(
            manifest.key_artifacts,
            [
                SessionArtifact(kind="experiment_conclusion", path=str(conclusion_markdown_path), role="main"),
                SessionArtifact(kind="experiment_conclusion_json", path=str(conclusion_json_path), role="main"),
                SessionArtifact(kind="agent_context", path=str(agent_context_path), role="supporting"),
            ],
        ),
        conclusion_path=str(conclusion_markdown_path),
        current_status="complete" if manifest.decision_path is not None else "needs_decision",
        outstanding_next_steps=next_steps,
        warnings=_remove_conclusion_missing_warnings(manifest.warnings),
    )


def update_manifest_after_decision(
    manifest: SessionManifest,
    *,
    decision_path: str,
    updated_at_utc: str | None = None,
) -> SessionManifest:
    return replace(
        manifest,
        updated_at_utc=updated_at_utc or utc_now_iso(),
        commands=[command for command in manifest.commands if command.label != "Recommended next step: draft_decision"],
        key_artifacts=_upsert_artifacts(
            manifest.key_artifacts,
            [SessionArtifact(kind="experiment_decision", path=decision_path, role="decision")],
        ),
        decision_path=decision_path,
        current_status="complete",
        outstanding_next_steps=[],
        warnings=_remove_decision_warnings(manifest.warnings),
    )


def format_session_manifest_markdown(manifest: SessionManifest) -> str:
    validate_session_manifest(manifest)
    return "\n".join(
        [
            f"# Session Manifest: {manifest.session_id}",
            "",
            "Report role: workflow orientation.",
            "",
            "## Status",
            "",
            f"- Current status: `{manifest.current_status}`",
            f"- Experiment: `{manifest.experiment_id}`",
            f"- Updated UTC: `{manifest.updated_at_utc}`",
            "",
            "## Read First",
            "",
            f"- Session orientation: `{_display_path(session_manifest_markdown_path(manifest.output_dir))}`",
            f"- Research conclusion: `{manifest.conclusion_path or '-'}`",
            f"- Machine conclusion: `{_json_conclusion_path(manifest.conclusion_path)}`",
            "",
            "## Question",
            "",
            f"- Title: {manifest.title}",
            f"- Hypothesis: {manifest.hypothesis}",
            f"- Plan: `{manifest.plan_path}`",
            f"- Output directory: `{manifest.output_dir}`",
            "",
            "## Inputs",
            "",
            *_named_bullets("Data", manifest.data_sources),
            *_named_bullets("Strategy", manifest.strategy_paths),
            "",
            "## Commands",
            "",
            *_command_markdown(manifest.commands),
            "",
            "## Key Artifacts",
            "",
            *_artifact_markdown(manifest.key_artifacts),
            "",
            "## Decision",
            "",
            f"- Decision path: `{manifest.decision_path or '-'}`",
            "",
            "## Outstanding Next Steps",
            "",
            *_bullet_lines(manifest.outstanding_next_steps),
            "",
            "## Warnings",
            "",
            *_bullet_lines(manifest.warnings),
            "",
        ]
    )


def format_session_status(manifest: SessionManifest) -> str:
    """Return compact resume text for humans, Codex, and local agents."""

    validate_session_manifest(manifest)
    lines = [
        f"Session: {manifest.session_id}",
        f"status: {manifest.current_status}",
        f"experiment: {manifest.experiment_id}",
        f"title: {manifest.title}",
        f"read_first: {_display_path(manifest.conclusion_path or session_manifest_markdown_path(manifest.output_dir))}",
        f"plan: {_display_path(manifest.plan_path)}",
    ]
    if manifest.decision_path is not None:
        lines.append(f"decision: {_display_path(manifest.decision_path)}")
    if manifest.outstanding_next_steps:
        lines.append(f"next: {manifest.outstanding_next_steps[0]}")
    if manifest.warnings:
        lines.append(f"warning: {manifest.warnings[0]}")
    return "\n".join(lines)


def format_session_replay_plan(manifest: SessionManifest, *, include_executed: bool = False) -> str:
    """Return commands recorded in the manifest without executing them."""

    validate_session_manifest(manifest)
    commands = [
        command
        for command in manifest.commands
        if include_executed or command.status != "executed"
    ]
    lines = [
        f"# Session Replay Plan: {manifest.session_id}",
        "",
        f"Experiment: `{manifest.experiment_id}`",
        f"Status: `{manifest.current_status}`",
        "",
        "These commands are printed for review only. This command does not run them.",
        "",
        "## Commands",
        "",
        *_command_replay_lines(commands),
        "",
        "## Outstanding Next Steps",
        "",
        *_bullet_lines(manifest.outstanding_next_steps),
        "",
        "## Read First",
        "",
        f"- `{_display_path(manifest.conclusion_path or session_manifest_markdown_path(manifest.output_dir))}`",
        "",
    ]
    return "\n".join(lines)


def _validate_command(command: SessionCommand) -> None:
    validate_required_text_fields(
        {"label": command.label, "command": command.command, "status": command.status},
        context="session command",
    )
    if command.status not in COMMAND_STATUSES:
        raise ValueError(f"session command status must be one of {sorted(COMMAND_STATUSES)}")


def _validate_artifact(artifact: SessionArtifact) -> None:
    validate_required_text_fields(
        {"kind": artifact.kind, "path": artifact.path, "role": artifact.role},
        context="session artifact",
    )
    if artifact.role not in ARTIFACT_ROLES:
        raise ValueError(f"session artifact role must be one of {sorted(ARTIFACT_ROLES)}")


def _command_from_dict(payload: dict) -> SessionCommand:
    return SessionCommand(
        label=str(payload.get("label", "")),
        command=str(payload.get("command", "")),
        status=str(payload.get("status", "unknown")),
    )


def _artifact_from_dict(payload: dict) -> SessionArtifact:
    return SessionArtifact(
        kind=str(payload.get("kind", "")),
        path=str(payload.get("path", "")),
        role=str(payload.get("role", "unknown")),
    )


def _upsert_artifacts(existing: list[SessionArtifact], updates: list[SessionArtifact]) -> list[SessionArtifact]:
    artifacts = list(existing)
    for update in updates:
        artifacts = [artifact for artifact in artifacts if artifact.path != update.path and artifact.kind != update.kind]
        artifacts.append(update)
    return artifacts


def _remove_conclusion_missing_warnings(warnings: list[str]) -> list[str]:
    return [
        warning
        for warning in warnings
        if "experiment_conclusion" not in warning and "Canonical conclusion is missing" not in warning
    ]


def _remove_decision_warnings(warnings: list[str]) -> list[str]:
    return [warning for warning in warnings if "decision" not in warning.lower()]


def _dedupe_strings(items: Iterable[object]) -> list[str]:
    normalized: list[str] = []
    for item in items:
        value = str(item).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _optional_path(value: str | Path | None) -> str | None:
    if value is None:
        return None
    return _optional_str(str(value))


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    value_string = str(value).strip()
    return value_string or None


def _json_conclusion_path(markdown_path: str | None) -> str:
    if markdown_path is None:
        return "-"
    path = Path(markdown_path)
    if path.name == "experiment_conclusion.md":
        return _display_path(path.with_name("experiment_conclusion.json"))
    return "-"


def _display_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _named_bullets(label: str, items: list[str]) -> list[str]:
    if not items:
        return [f"- {label}: none"]
    return [f"- {label}: `{item}`" for item in items]


def _command_markdown(commands: list[SessionCommand]) -> list[str]:
    if not commands:
        return ["- None"]
    return [f"- `{command.status}` {command.label}: `{command.command}`" for command in commands]


def _command_replay_lines(commands: list[SessionCommand]) -> list[str]:
    if not commands:
        return ["- None"]
    lines: list[str] = []
    for command in commands:
        lines.append(f"- {command.label} (`{command.status}`)")
        lines.append("")
        lines.append("  ```bash")
        lines.append(f"  {_display_path(command.command)}")
        lines.append("  ```")
    return lines


def _artifact_markdown(artifacts: list[SessionArtifact]) -> list[str]:
    if not artifacts:
        return ["- None"]
    return [f"- `{artifact.role}` {artifact.kind}: `{artifact.path}`" for artifact in artifacts]


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None"]
