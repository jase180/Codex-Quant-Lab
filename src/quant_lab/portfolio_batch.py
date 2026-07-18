"""Plan auditable batches of portfolio research runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

from .costs import resolve_cost_assumptions
from .portfolio_execution import execute_portfolio_run
from .portfolio_spec import load_portfolio_spec
from .research_plan_common import utc_now_iso

PORTFOLIO_BATCH_MANIFEST_SCHEMA_VERSION = "portfolio_batch_manifest.v1"
PORTFOLIO_BATCH_MANIFEST_FILENAME = "portfolio_batch_manifest.json"
PORTFOLIO_BATCH_RESULT_SCHEMA_VERSION = "portfolio_batch_result.v1"
PORTFOLIO_BATCH_RESULT_FILENAME = "portfolio_batch_result.json"
PORTFOLIO_BATCH_SUMMARY_FILENAME = "portfolio_batch_summary.md"


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


@dataclass(frozen=True)
class PortfolioBatchRunItemResult:
    """Execution result for one manifest item."""

    portfolio_id: str
    portfolio_path: str
    output_dir: str
    status: str
    command: list[str]
    metadata_path: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioBatchRunResult:
    """Durable result file for a sequential portfolio batch run."""

    schema_version: str
    created_at_utc: str
    manifest_path: str
    experiment_id: str
    planned_count: int
    completed_count: int
    failed_count: int
    skipped_count: int
    items: list[PortfolioBatchRunItemResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["items"] = [item.to_dict() for item in self.items]
        return payload


@dataclass(frozen=True)
class PortfolioBatchSummary:
    """Guardrail summary for one planned or executed portfolio batch."""

    manifest_path: str
    result_path: str | None
    summary_path: str
    planned_count: int
    completed_count: int
    failed_count: int
    skipped_count: int
    warnings: list[str]
    portfolio_summary_path: str | None = None


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


def portfolio_batch_result_path(manifest_path: str | Path) -> Path:
    return Path(manifest_path).parent / PORTFOLIO_BATCH_RESULT_FILENAME


def portfolio_batch_summary_path(manifest_path: str | Path) -> Path:
    return Path(manifest_path).parent / PORTFOLIO_BATCH_SUMMARY_FILENAME


def load_portfolio_batch_manifest(manifest_path: str | Path) -> PortfolioBatchManifest:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if str(payload.get("schema_version", "")) != PORTFOLIO_BATCH_MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"unsupported portfolio batch manifest schema: {payload.get('schema_version')}")
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError("portfolio batch manifest items must be a list.")

    items = [
        PortfolioBatchManifestItem(
            portfolio_id=str(item.get("portfolio_id", "")),
            portfolio_path=str(item.get("portfolio_path", "")),
            output_dir=str(item.get("output_dir", "")),
            command=[str(token) for token in item.get("command", [])],
            status=str(item.get("status", "")),
        )
        for item in raw_items
    ]
    manifest = PortfolioBatchManifest(
        schema_version=str(payload.get("schema_version", "")),
        created_at_utc=str(payload.get("created_at_utc", "")),
        portfolios_dir=str(payload.get("portfolios_dir", "")),
        output_dir=str(payload.get("output_dir", "")),
        item_count=int(payload.get("item_count", len(items))),
        items=items,
    )
    _validate_loaded_manifest(manifest)
    return manifest


def load_portfolio_batch_result(result_path: str | Path) -> PortfolioBatchRunResult:
    payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
    if str(payload.get("schema_version", "")) != PORTFOLIO_BATCH_RESULT_SCHEMA_VERSION:
        raise ValueError(f"unsupported portfolio batch result schema: {payload.get('schema_version')}")
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError("portfolio batch result items must be a list.")

    items = [
        PortfolioBatchRunItemResult(
            portfolio_id=str(item.get("portfolio_id", "")),
            portfolio_path=str(item.get("portfolio_path", "")),
            output_dir=str(item.get("output_dir", "")),
            status=str(item.get("status", "")),
            command=[str(token) for token in item.get("command", [])],
            metadata_path=_optional_str(item.get("metadata_path")),
            error=_optional_str(item.get("error")),
        )
        for item in raw_items
    ]
    result = PortfolioBatchRunResult(
        schema_version=str(payload.get("schema_version", "")),
        created_at_utc=str(payload.get("created_at_utc", "")),
        manifest_path=str(payload.get("manifest_path", "")),
        experiment_id=str(payload.get("experiment_id", "")),
        planned_count=int(payload.get("planned_count", len(items))),
        completed_count=int(payload.get("completed_count", 0)),
        failed_count=int(payload.get("failed_count", 0)),
        skipped_count=int(payload.get("skipped_count", 0)),
        items=items,
    )
    _validate_loaded_result(result)
    return result


def run_portfolio_batch(
    *,
    manifest_path: str | Path,
    experiment_id: str,
    continue_on_error: bool = False,
    created_at_utc: str | None = None,
) -> PortfolioBatchRunResult:
    """Execute manifest items sequentially and write a batch result file."""

    manifest_file = Path(manifest_path)
    manifest = load_portfolio_batch_manifest(manifest_file)
    item_results: list[PortfolioBatchRunItemResult] = []
    stopping_after_failure = False

    for item in manifest.items:
        if stopping_after_failure:
            item_results.append(_skipped_item_result(item, experiment_id))
            continue

        command = _command_with_experiment_id(item.command, experiment_id)
        try:
            planned = _parse_portfolio_run_command(command)
            cost_assumptions = resolve_cost_assumptions(
                cost_preset=planned["cost_preset"],
                commission_fixed=None,
                commission_rate=None,
                slippage_bps=None,
            )
            run = execute_portfolio_run(
                portfolio_path=planned["portfolio"],
                output_dir=planned["out"],
                initial_cash=float(planned["initial_cash"]),
                cost_assumptions=cost_assumptions,
                experiments_path=planned["experiments_path"],
                experiment_id=experiment_id,
                index_path=planned["index_path"],
                command=command,
            )
            item_results.append(
                PortfolioBatchRunItemResult(
                    portfolio_id=item.portfolio_id,
                    portfolio_path=item.portfolio_path,
                    output_dir=item.output_dir,
                    status="completed",
                    command=command,
                    metadata_path=run.artifact_paths["metadata"],
                )
            )
        except Exception as exc:
            item_results.append(
                PortfolioBatchRunItemResult(
                    portfolio_id=item.portfolio_id,
                    portfolio_path=item.portfolio_path,
                    output_dir=item.output_dir,
                    status="failed",
                    command=command,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            if not continue_on_error:
                stopping_after_failure = True

    result = PortfolioBatchRunResult(
        schema_version=PORTFOLIO_BATCH_RESULT_SCHEMA_VERSION,
        created_at_utc=created_at_utc or utc_now_iso(),
        manifest_path=str(manifest_file),
        experiment_id=experiment_id,
        planned_count=len(manifest.items),
        completed_count=sum(1 for item in item_results if item.status == "completed"),
        failed_count=sum(1 for item in item_results if item.status == "failed"),
        skipped_count=sum(1 for item in item_results if item.status == "skipped"),
        items=item_results,
    )
    result_path = portfolio_batch_result_path(manifest_file)
    result_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def summarize_portfolio_batch(
    *,
    manifest_path: str | Path,
    output_path: str | Path | None = None,
    max_planned_runs: int = 25,
    min_completed_runs: int = 2,
) -> PortfolioBatchSummary:
    """Write a markdown guardrail summary for one portfolio batch."""

    manifest_file = Path(manifest_path)
    manifest = load_portfolio_batch_manifest(manifest_file)
    result_file = portfolio_batch_result_path(manifest_file)
    result = load_portfolio_batch_result(result_file) if result_file.exists() else None
    planned_count = manifest.item_count
    completed_count = result.completed_count if result is not None else 0
    failed_count = result.failed_count if result is not None else 0
    skipped_count = result.skipped_count if result is not None else 0
    portfolio_summary = _existing_portfolio_summary_path(manifest_file)
    warnings = _batch_guardrail_warnings(
        planned_count=planned_count,
        completed_count=completed_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        result_exists=result is not None,
        max_planned_runs=max_planned_runs,
        min_completed_runs=min_completed_runs,
    )
    summary_file = Path(output_path) if output_path is not None else portfolio_batch_summary_path(manifest_file)
    summary = PortfolioBatchSummary(
        manifest_path=str(manifest_file),
        result_path=str(result_file) if result is not None else None,
        summary_path=str(summary_file),
        planned_count=planned_count,
        completed_count=completed_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        warnings=warnings,
        portfolio_summary_path=str(portfolio_summary) if portfolio_summary is not None else None,
    )
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(_render_portfolio_batch_summary(summary, result), encoding="utf-8")
    return summary


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


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    value_string = str(value)
    return value_string if value_string else None


def _validate_loaded_manifest(manifest: PortfolioBatchManifest) -> None:
    if manifest.item_count != len(manifest.items):
        raise ValueError("portfolio batch manifest item_count does not match items.")
    for item in manifest.items:
        if not item.portfolio_id.strip():
            raise ValueError("portfolio batch manifest item portfolio_id must not be empty.")
        if not item.portfolio_path.strip():
            raise ValueError("portfolio batch manifest item portfolio_path must not be empty.")
        if not item.output_dir.strip():
            raise ValueError("portfolio batch manifest item output_dir must not be empty.")
        if item.status != "planned":
            raise ValueError("portfolio batch manifest items must have status planned before running.")
        planned = _parse_portfolio_run_command(item.command)
        if planned["portfolio"] != item.portfolio_path:
            raise ValueError("portfolio batch manifest item portfolio_path does not match its command.")
        if planned["out"] != item.output_dir:
            raise ValueError("portfolio batch manifest item output_dir does not match its command.")


def _validate_loaded_result(result: PortfolioBatchRunResult) -> None:
    if result.planned_count != len(result.items):
        raise ValueError("portfolio batch result planned_count does not match items.")
    completed_count = sum(1 for item in result.items if item.status == "completed")
    failed_count = sum(1 for item in result.items if item.status == "failed")
    skipped_count = sum(1 for item in result.items if item.status == "skipped")
    if result.completed_count != completed_count:
        raise ValueError("portfolio batch result completed_count does not match items.")
    if result.failed_count != failed_count:
        raise ValueError("portfolio batch result failed_count does not match items.")
    if result.skipped_count != skipped_count:
        raise ValueError("portfolio batch result skipped_count does not match items.")


def _command_with_experiment_id(command: list[str], experiment_id: str) -> list[str]:
    updated = list(command)
    if "--experiment-id" in updated:
        index = updated.index("--experiment-id")
        if index + 1 >= len(updated):
            raise ValueError("manifest command has --experiment-id without a value.")
        updated[index + 1] = experiment_id
        return updated
    return [*updated, "--experiment-id", experiment_id]


def _parse_portfolio_run_command(command: list[str]) -> dict[str, str]:
    if len(command) < 2 or command[0] != "quant-lab" or command[1] != "portfolio-run":
        raise ValueError("portfolio batch manifest command must start with quant-lab portfolio-run.")
    return {
        "portfolio": _required_command_value(command, "--portfolio"),
        "out": _required_command_value(command, "--out"),
        "initial_cash": _required_command_value(command, "--initial-cash"),
        "cost_preset": _required_command_value(command, "--cost-preset"),
        "experiments_path": _required_command_value(command, "--experiments-path"),
        "index_path": _required_command_value(command, "--index-path"),
    }


def _required_command_value(command: list[str], flag: str) -> str:
    try:
        index = command.index(flag)
    except ValueError as exc:
        raise ValueError(f"portfolio batch manifest command is missing {flag}.") from exc
    if index + 1 >= len(command) or command[index + 1].startswith("--"):
        raise ValueError(f"portfolio batch manifest command has no value for {flag}.")
    return command[index + 1]


def _skipped_item_result(item: PortfolioBatchManifestItem, experiment_id: str) -> PortfolioBatchRunItemResult:
    return PortfolioBatchRunItemResult(
        portfolio_id=item.portfolio_id,
        portfolio_path=item.portfolio_path,
        output_dir=item.output_dir,
        status="skipped",
        command=_command_with_experiment_id(item.command, experiment_id),
        error="Skipped because an earlier batch item failed.",
    )


def _batch_guardrail_warnings(
    *,
    planned_count: int,
    completed_count: int,
    failed_count: int,
    skipped_count: int,
    result_exists: bool,
    max_planned_runs: int,
    min_completed_runs: int,
) -> list[str]:
    warnings: list[str] = []
    if planned_count > max_planned_runs:
        warnings.append(
            f"Large batch: {planned_count} planned runs exceeds the configured cap of {max_planned_runs}."
        )
    if not result_exists:
        warnings.append("No batch result file exists yet; this is planning evidence only.")
    if failed_count:
        warnings.append(f"{failed_count} run(s) failed; inspect errors before interpreting winners.")
    if skipped_count:
        warnings.append(f"{skipped_count} run(s) were skipped; the batch evidence is incomplete.")
    if completed_count == 0:
        warnings.append("No completed runs; there is no performance evidence to interpret.")
    elif completed_count < min_completed_runs:
        warnings.append(
            f"Only {completed_count} completed run(s); evidence is thin below {min_completed_runs} completed runs."
        )
    if result_exists and completed_count < planned_count:
        warnings.append("Not all planned runs completed; avoid comparing this as a full candidate set.")
    return warnings


def _existing_portfolio_summary_path(manifest_path: Path) -> Path | None:
    candidate = manifest_path.parent / "portfolio_summary.md"
    return candidate if candidate.exists() else None


def _render_portfolio_batch_summary(
    summary: PortfolioBatchSummary,
    result: PortfolioBatchRunResult | None,
) -> str:
    warnings = "\n".join(f"- {warning}" for warning in summary.warnings) if summary.warnings else "- none"
    portfolio_summary = summary.portfolio_summary_path or "not found"
    item_lines = "- no result file yet"
    if result is not None:
        item_lines = "\n".join(
            f"- `{item.status}` `{item.portfolio_id}`"
            + (f" -> `{item.metadata_path}`" if item.metadata_path else "")
            + (f" ({item.error})" if item.error else "")
            for item in result.items
        )

    return f"""# Portfolio Batch Summary

## Batch

- Manifest: `{summary.manifest_path}`
- Result: `{summary.result_path or "not found"}`
- Portfolio experiment summary: `{portfolio_summary}`

## Counts

- Planned: `{summary.planned_count}`
- Completed: `{summary.completed_count}`
- Failed: `{summary.failed_count}`
- Skipped: `{summary.skipped_count}`

## Guardrails

{warnings}

## Robustness Notes

- This batch compares allocation candidates from the manifest; it is not a full
  portfolio robustness check by itself.
- To test cost sensitivity, run comparable portfolio batches with stricter
  `--cost-preset` values and link those runs to the same experiment.
- To test benchmark sensitivity, rerun candidate portfolios with alternate
  benchmark symbols in their portfolio specs before writing the final summary.
- Read the portfolio experiment summary after linking those runs; it reports
  which cost presets and benchmarks are represented.

## Items

{item_lines}
"""
