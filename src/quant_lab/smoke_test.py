"""Offline smoke workflow for proving the lab can run end to end."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .agent_cycle import AgentCycleResult, run_agent_cycle
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
    agent_cycle_json: str | None = None
    agent_cycle_markdown: str | None = None
    agent_recommended_action: str | None = None
    agent_proposed_command: str | None = None
    agent_stop_reason: str | None = None


def run_smoke_test(
    *,
    repo_root: str | Path = ".",
    output_dir: str | Path = "artifacts/smoke-test",
    force: bool = False,
    include_agent_cycle: bool = False,
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
    agent_cycle = _run_optional_agent_cycle(manifest_path, include_agent_cycle=include_agent_cycle)

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
        agent_cycle_json=_display_path(agent_cycle.cycle_json_path) if agent_cycle else None,
        agent_cycle_markdown=_display_path(agent_cycle.cycle_markdown_path) if agent_cycle else None,
        agent_recommended_action=agent_cycle.recommended_action if agent_cycle else None,
        agent_proposed_command=_normalize_command_paths(agent_cycle.proposed_command) if agent_cycle and agent_cycle.proposed_command else None,
        agent_stop_reason=agent_cycle.stop_reason if agent_cycle else None,
    )


def _run_optional_agent_cycle(manifest_path: str | Path, *, include_agent_cycle: bool) -> AgentCycleResult | None:
    if not include_agent_cycle:
        return None
    agent_cycle = run_agent_cycle(manifest_path, dry_run=True)
    _validate_agent_cycle(agent_cycle)
    return agent_cycle


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
            *_agent_cycle_lines(result),
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


def _validate_agent_cycle(agent_cycle: AgentCycleResult) -> None:
    if agent_cycle.recommended_action != "run_trust":
        raise RuntimeError(f"expected agent smoke-test action run_trust, got {agent_cycle.recommended_action}")
    if not agent_cycle.proposed_command or "summarize-run-trust" not in agent_cycle.proposed_command:
        raise RuntimeError("expected agent smoke-test to propose summarize-run-trust")


def _agent_cycle_lines(result: SmokeTestResult) -> list[str]:
    if result.agent_cycle_json is None:
        return []
    return [
        f"agent_cycle: {result.agent_cycle_json}",
        f"agent_cycle_markdown: {result.agent_cycle_markdown}",
        f"agent_recommended_action: {result.agent_recommended_action}",
        "agent_proposed_command:",
        result.agent_proposed_command or "-",
        f"agent_stop_reason: {result.agent_stop_reason}",
    ]


def _display_path(path: str | Path) -> str:
    return Path(path).as_posix()


def _normalize_command_paths(command: str) -> str:
    return command.replace("\\", "/")
