"""Offline smoke workflow for proving the lab can run end to end."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .cli_session import build_session_manifest_from_research_plan
from .costs import resolve_cost_assumptions
from .data_quality import build_data_quality_report
from .research_plan import create_research_plan, save_research_plan
from .research_registry import append_experiment_record, create_experiment_record
from .run_artifacts import RunArtifactResult, run_single_backtest
from .run_config import RunExecutionConfig
from .run_metadata import command_tokens
from .session_manifest import save_session_manifest
from .strategy_schema import load_strategy


@dataclass(frozen=True)
class SmokeTestResult:
    status: str
    output_dir: str
    experiment_id: str
    research_plan: str
    research_plan_markdown: str
    baseline_metadata: str
    baseline_report: str
    session_manifest: str
    session_manifest_markdown: str
    next_command: str
    read_first: str
    note: str


def run_smoke_test(
    *,
    repo_root: str | Path = ".",
    output_dir: str | Path = "artifacts/smoke-test",
    force: bool = False,
) -> SmokeTestResult:
    """Run a tiny local workflow without internet or external services."""

    root = Path(repo_root)
    out = Path(output_dir)
    if not out.is_absolute():
        out = root / out
    if out.exists():
        if not force:
            raise FileExistsError(f"smoke-test output already exists: {out}. Use --force to replace it.")
        # The CLI makes `--force` explicit before reaching this branch. Keeping
        # deletion scoped to the chosen output directory prevents accidental
        # cleanup of unrelated artifacts.
        shutil.rmtree(out)

    experiment_id = "EXP-001"
    strategy_path = root / "data" / "strategies" / "sma_crossover.json"
    data_path = root / "data" / "sample_ohlcv.csv"
    experiments_path = out / "experiments.jsonl"
    index_path = out / "research_index.jsonl"

    append_experiment_record(
        create_experiment_record(
            experiment_id=experiment_id,
            title="Sample smoke workflow",
            hypothesis="The tracked sample data can prove the local workflow is installed and producing artifacts.",
            status="planned",
            tags=["smoke-test"],
            strategy_path=str(strategy_path),
            data_path=str(data_path),
            notes="Created by quant-lab smoke-test.",
        ),
        experiments_path,
    )
    plan = create_research_plan(
        title="Sample smoke workflow",
        hypothesis="The tracked sample data can prove the local workflow is installed and producing artifacts.",
        strategy_path=strategy_path,
        data_path=data_path,
        symbol="QQQ",
        experiment_id=experiment_id,
        experiments_path=experiments_path,
        index_path=index_path,
        output_dir=out,
        sizing="percent-equity",
        allocation=1.0,
        benchmark="buy-and-hold",
        cost_preset="retail-liquid",
        tags=["smoke-test"],
    )
    plan_path, plan_markdown_path = save_research_plan(plan)

    run_output = _run_baseline(plan)
    manifest = build_session_manifest_from_research_plan(plan_path)
    manifest_path, manifest_markdown_path = save_session_manifest(manifest)

    next_command = manifest.commands[0].command if manifest.commands else "quant-lab session status --manifest " + manifest_path
    read_first = manifest_markdown_path
    return SmokeTestResult(
        status="ok",
        output_dir=_display_path(out),
        experiment_id=experiment_id,
        research_plan=_display_path(plan_path),
        research_plan_markdown=_display_path(plan_markdown_path),
        baseline_metadata=_display_path(run_output.artifact_paths["metadata"]),
        baseline_report=_display_path(run_output.artifact_paths["report"]),
        session_manifest=_display_path(manifest_path),
        session_manifest_markdown=_display_path(manifest_markdown_path),
        next_command=_normalize_command_paths(next_command),
        read_first=_display_path(read_first),
        note="This is a wiring check using a tiny tracked CSV, not research evidence.",
    )


def format_smoke_test_result(result: SmokeTestResult) -> str:
    return "\n".join(
        [
            "Quant Lab smoke-test: OK",
            f"output_dir: {result.output_dir}",
            f"experiment_id: {result.experiment_id}",
            f"research_plan: {result.research_plan}",
            f"baseline_report: {result.baseline_report}",
            f"baseline_metadata: {result.baseline_metadata}",
            f"session_manifest: {result.session_manifest}",
            f"read_first: {result.read_first}",
            "next_command:",
            result.next_command,
            f"note: {result.note}",
        ]
    )


def smoke_test_result_to_json(result: SmokeTestResult) -> str:
    return json.dumps(asdict(result), indent=2, sort_keys=True)


def _run_baseline(plan) -> RunArtifactResult:
    cost_assumptions = resolve_cost_assumptions(
        cost_preset=plan.cost_preset,
        commission_fixed=plan.commission_fixed,
        commission_rate=plan.commission_rate,
        slippage_bps=plan.slippage_bps,
    )
    config = RunExecutionConfig.from_values(
        data_path=plan.data_path,
        index_path=plan.index_path,
        initial_cash=plan.initial_cash,
        quantity=plan.quantity,
        sizing=plan.sizing,
        allocation=plan.allocation,
        benchmark=plan.benchmark,
        cost_assumptions=cost_assumptions,
        command_tokens=command_tokens(
            "quant-lab",
            [
                "smoke-test",
                "--out",
                plan.output_dir,
            ],
        ),
        experiment_id=plan.experiment_id,
        experiments_path=plan.experiments_path,
    )
    strategy_spec = load_strategy(plan.strategy_path)
    data = pd.read_csv(plan.data_path)
    data_quality = build_data_quality_report(data)
    return run_single_backtest(
        config=config,
        data=data,
        data_quality=data_quality,
        strategy_spec=strategy_spec,
        output_dir=Path(plan.output_dir) / "baseline",
        run_name=strategy_spec.name,
        research_note_path=None,
    )


def _display_path(path: str | Path) -> str:
    return Path(path).as_posix()


def _normalize_command_paths(command: str) -> str:
    return command.replace("\\", "/")
