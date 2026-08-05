"""Execute campaign handoffs through existing experiment workflows."""

from __future__ import annotations

import argparse
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .campaign_conversion import CampaignExperimentInputs
from .default_experiment import run_default_experiment, validate_default_experiment_args
from .research_plan_common import utc_now_iso, write_json_payload


CAMPAIGN_EXECUTION_SCHEMA_VERSION = "campaign_execution.v1"
EXECUTION_JSON_FILENAME = "campaign_execution.json"
EXECUTION_MARKDOWN_FILENAME = "campaign_execution.md"


@dataclass(frozen=True)
class CampaignExecutionResult:
    schema_version: str
    status: str
    experiment_id: str | None
    output_dir: str
    conclusion_path: str | None
    conclusion_json_path: str | None
    read_first_path: str | None
    execution_json_path: str
    execution_markdown_path: str
    error: str | None
    elapsed_seconds: int
    created_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_campaign_experiment_inputs(inputs: CampaignExperimentInputs) -> CampaignExecutionResult:
    """Run the generated default experiment args and save execution evidence."""

    args = argparse.Namespace(**inputs.run_default_args)
    validate_default_experiment_args(args)
    started = time.monotonic()
    try:
        result = run_default_experiment(args)
        conclusion_json_path = _conclusion_json_path(result.conclusion_path)
        if not conclusion_json_path.exists():
            raise FileNotFoundError(f"expected experiment conclusion JSON does not exist: {conclusion_json_path}")
        execution = CampaignExecutionResult(
            schema_version=CAMPAIGN_EXECUTION_SCHEMA_VERSION,
            status="completed",
            experiment_id=result.experiment_id,
            output_dir=result.output_dir,
            conclusion_path=result.conclusion_path,
            conclusion_json_path=str(conclusion_json_path),
            read_first_path=result.read_first_path,
            execution_json_path=str(_execution_json_path(inputs)),
            execution_markdown_path=str(_execution_markdown_path(inputs)),
            error=None,
            elapsed_seconds=max(0, int(time.monotonic() - started)),
            created_at_utc=utc_now_iso(),
        )
    except Exception as exc:
        execution = CampaignExecutionResult(
            schema_version=CAMPAIGN_EXECUTION_SCHEMA_VERSION,
            status="failed",
            experiment_id=None,
            output_dir=inputs.output_dir,
            conclusion_path=None,
            conclusion_json_path=None,
            read_first_path=None,
            execution_json_path=str(_execution_json_path(inputs)),
            execution_markdown_path=str(_execution_markdown_path(inputs)),
            error=str(exc),
            elapsed_seconds=max(0, int(time.monotonic() - started)),
            created_at_utc=utc_now_iso(),
        )
        _save_execution_result(execution)
        raise

    _save_execution_result(execution)
    return execution


def _save_execution_result(execution: CampaignExecutionResult) -> None:
    write_json_payload(execution.execution_json_path, execution.to_dict())
    Path(execution.execution_markdown_path).write_text(_format_execution_markdown(execution), encoding="utf-8")


def _format_execution_markdown(execution: CampaignExecutionResult) -> str:
    return "\n".join(
        [
            "# Campaign Cycle Execution",
            "",
            "Report role: campaign execution receipt.",
            "",
            f"- Status: `{execution.status}`",
            f"- Experiment id: `{execution.experiment_id or '-'}`",
            f"- Output directory: `{execution.output_dir}`",
            f"- Read first: `{execution.read_first_path or '-'}`",
            f"- Conclusion: `{execution.conclusion_path or '-'}`",
            f"- Conclusion JSON: `{execution.conclusion_json_path or '-'}`",
            f"- Elapsed seconds: `{execution.elapsed_seconds}`",
            f"- Error: {execution.error or '-'}",
            "",
        ]
    )


def _execution_json_path(inputs: CampaignExperimentInputs) -> Path:
    return Path(inputs.run_default_args_path).with_name(EXECUTION_JSON_FILENAME)


def _execution_markdown_path(inputs: CampaignExperimentInputs) -> Path:
    return Path(inputs.run_default_args_path).with_name(EXECUTION_MARKDOWN_FILENAME)


def _conclusion_json_path(conclusion_path: str) -> Path:
    return Path(conclusion_path).with_suffix(".json")
