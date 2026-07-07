"""Structured metadata for reproducible research runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class StrategyMetadata:
    strategy_id: str
    name: str
    schema_version: str
    strategy_type: str


@dataclass(frozen=True)
class DataMetadata:
    path: str
    row_count: int
    start: str | None
    end: str | None
    symbol: str | None = None
    timeframe: str | None = None


@dataclass(frozen=True)
class SizingMetadata:
    mode: str
    initial_cash: float
    quantity: float
    allocation: float


@dataclass(frozen=True)
class CostMetadata:
    preset: str
    commission_fixed: float
    commission_rate: float
    slippage_bps: float


@dataclass(frozen=True)
class EnvironmentMetadata:
    git_commit: str


@dataclass(frozen=True)
class RunMetadata:
    """Stable, versioned shape for run provenance.

    The nested dataclasses make the JSON easy to extend. For example, adding a
    new cost field later should only touch ``CostMetadata`` instead of every
    caller that writes `run_metadata.json`.
    """

    metadata_schema_version: str
    run_type: str
    run_id: str | None
    created_at_utc: str
    command: list[str]
    strategy: StrategyMetadata
    data: DataMetadata
    sizing: SizingMetadata
    costs: CostMetadata
    environment: EnvironmentMetadata
    parameters: dict[str, str | int | float] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)

    def with_artifacts(self, artifacts: Mapping[str, str]) -> "RunMetadata":
        # Dataclasses are immutable here, so this acts like a safe setter: it
        # returns a copy with artifacts attached after the files have been saved.
        return replace(self, artifacts=dict(artifacts))

    def to_dict(self) -> dict:
        return asdict(self)


def save_run_metadata(metadata: RunMetadata, output_dir: str | Path) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    metadata_path = destination / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(metadata_path)


def command_tokens(program_name: str, argv: Sequence[str]) -> list[str]:
    return [program_name, *[str(token) for token in argv]]
