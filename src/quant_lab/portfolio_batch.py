"""Plan auditable batches of portfolio research runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

from .portfolio_spec import load_portfolio_spec
from .research_plan_common import utc_now_iso

PORTFOLIO_BATCH_MANIFEST_SCHEMA_VERSION = "portfolio_batch_manifest.v1"
PORTFOLIO_BATCH_MANIFEST_FILENAME = "portfolio_batch_manifest.json"


@dataclass(frozen=True)
class PortfolioBatchManifestItem:
    """One planned portfolio run inside a batch manifest."""

    portfolio_id: str
    portfolio_path: str
    output_dir: str
    command: list[str]
    status: str = "planned"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioBatchManifest:
    """Durable dry-run plan for a group of portfolio candidates."""

    schema_version: str
    created_at_utc: str
    portfolios_dir: str
    output_dir: str
    item_count: int
    items: list[PortfolioBatchManifestItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["items"] = [item.to_dict() for item in self.items]
        return payload


def plan_portfolio_batch(
    *,
    portfolios_dir: str | Path,
    output_dir: str | Path,
    initial_cash: float = 100_000.0,
    cost_preset: str = "none",
    experiments_path: str | Path = "artifacts/experiments.jsonl",
    index_path: str | Path = "artifacts/research_index.jsonl",
    force: bool = False,
    created_at_utc: str | None = None,
) -> PortfolioBatchManifest:
    """Create a manifest for portfolio specs without running backtests."""

    source_dir = Path(portfolios_dir)
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Portfolio candidate directory does not exist: {source_dir}")

    portfolio_paths = sorted(path for path in source_dir.glob("*.json") if path.is_file())
    if not portfolio_paths:
        raise ValueError(f"No portfolio JSON specs found in {source_dir}.")

    destination_dir = Path(output_dir)
    manifest_path = destination_dir / PORTFOLIO_BATCH_MANIFEST_FILENAME
    if manifest_path.exists() and not force:
        raise FileExistsError(f"Portfolio batch manifest already exists: {manifest_path}. Use --force to overwrite it.")

    items = [
        _build_manifest_item(
            portfolio_path=portfolio_path,
            batch_output_dir=destination_dir,
            initial_cash=initial_cash,
            cost_preset=cost_preset,
            experiments_path=experiments_path,
            index_path=index_path,
        )
        for portfolio_path in portfolio_paths
    ]
    manifest = PortfolioBatchManifest(
        schema_version=PORTFOLIO_BATCH_MANIFEST_SCHEMA_VERSION,
        created_at_utc=created_at_utc or utc_now_iso(),
        portfolios_dir=str(source_dir),
        output_dir=str(destination_dir),
        item_count=len(items),
        items=items,
    )

    destination_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def portfolio_batch_manifest_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / PORTFOLIO_BATCH_MANIFEST_FILENAME


def _build_manifest_item(
    *,
    portfolio_path: Path,
    batch_output_dir: Path,
    initial_cash: float,
    cost_preset: str,
    experiments_path: str | Path,
    index_path: str | Path,
) -> PortfolioBatchManifestItem:
    portfolio = load_portfolio_spec(portfolio_path)
    run_output_dir = batch_output_dir / "runs" / portfolio_path.stem
    command = _portfolio_run_command(
        portfolio_path=portfolio_path,
        output_dir=run_output_dir,
        initial_cash=initial_cash,
        cost_preset=cost_preset,
        experiments_path=experiments_path,
        index_path=index_path,
    )
    return PortfolioBatchManifestItem(
        portfolio_id=portfolio.portfolio_id,
        portfolio_path=str(portfolio_path),
        output_dir=str(run_output_dir),
        command=command,
    )


def _portfolio_run_command(
    *,
    portfolio_path: Path,
    output_dir: Path,
    initial_cash: float,
    cost_preset: str,
    experiments_path: str | Path,
    index_path: str | Path,
) -> list[str]:
    # The later batch runner can append `--experiment-id` when a user chooses
    # which experiment should own the evidence. The dry-run manifest keeps the
    # reproducible portfolio-run defaults visible without requiring that choice.
    return _command_tokens(
        [
            "portfolio-run",
            "--portfolio",
            str(portfolio_path),
            "--out",
            str(output_dir),
            "--initial-cash",
            str(float(initial_cash)),
            "--cost-preset",
            str(cost_preset),
            "--experiments-path",
            str(experiments_path),
            "--index-path",
            str(index_path),
        ]
    )


def _command_tokens(argv: Sequence[str]) -> list[str]:
    return ["quant-lab", *[str(token) for token in argv]]
