"""Convert validated campaign proposals into existing workflow inputs."""

from __future__ import annotations

import json
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .campaign import CampaignConfig
from .campaign_proposal import CampaignProposal
from .research_plan_common import utc_now_iso, write_json_payload
from .strategy_templates import build_strategy_template, write_strategy_template


CAMPAIGN_EXPERIMENT_INPUTS_SCHEMA_VERSION = "campaign_experiment_inputs.v1"
RUN_DEFAULT_ARGS_FILENAME = "run_default_args.json"
RUN_DEFAULT_COMMAND_FILENAME = "run_default_command.md"
CAMPAIGN_STRATEGY_FILENAME = "strategy.json"

DEFAULT_TRAIN_END = "2020-12-31"
DEFAULT_TEST_START = "2021-01-01"
DEFAULT_DATE_WINDOWS = ("2015-01-02,2019-12-31", "2020-01-01,2025-12-30")


@dataclass(frozen=True)
class CampaignExperimentInputs:
    schema_version: str
    proposal_title: str
    strategy_path: str
    data_path: str
    output_dir: str
    run_default_args_path: str
    run_default_command_path: str
    command_tokens: list[str]
    created_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def prepare_campaign_experiment_inputs(
    proposal: CampaignProposal,
    *,
    config: CampaignConfig,
    cycle_dir: str | Path,
) -> CampaignExperimentInputs:
    """Write the artifacts needed to execute one existing default experiment.

    Campaign proposals are intentionally not executable commands. This adapter
    is the narrow bridge that turns approved proposal fields into the repo's
    existing `experiment run-default` interface.
    """

    if proposal.action != "run_experiment":
        raise ValueError("only run_experiment proposals can be converted to experiment inputs")
    if not proposal.strategy_template or not proposal.symbol:
        raise ValueError("run_experiment proposals require strategy_template and symbol")

    destination = Path(cycle_dir)
    destination.mkdir(parents=True, exist_ok=True)
    strategy_path = destination / CAMPAIGN_STRATEGY_FILENAME
    run_default_args_path = destination / RUN_DEFAULT_ARGS_FILENAME
    run_default_command_path = destination / RUN_DEFAULT_COMMAND_FILENAME
    output_dir = destination / "experiment"

    strategy_payload = build_strategy_template(
        proposal.strategy_template,
        symbol=proposal.symbol,
        strategy_id=_strategy_id(proposal),
        name=proposal.title,
        length=_template_length(proposal),
    )
    write_strategy_template(strategy_payload, strategy_path, force=True)

    command_tokens = _run_default_command_tokens(
        proposal,
        config=config,
        strategy_path=str(strategy_path),
        output_dir=str(output_dir),
    )
    inputs = CampaignExperimentInputs(
        schema_version=CAMPAIGN_EXPERIMENT_INPUTS_SCHEMA_VERSION,
        proposal_title=proposal.title,
        strategy_path=str(strategy_path),
        data_path=config.data_paths[proposal.symbol],
        output_dir=str(output_dir),
        run_default_args_path=str(run_default_args_path),
        run_default_command_path=str(run_default_command_path),
        command_tokens=command_tokens,
        created_at_utc=utc_now_iso(),
    )
    write_json_payload(run_default_args_path, inputs.to_dict())
    run_default_command_path.write_text(_format_command_markdown(inputs), encoding="utf-8")
    return inputs


def _run_default_command_tokens(
    proposal: CampaignProposal,
    *,
    config: CampaignConfig,
    strategy_path: str,
    output_dir: str,
) -> list[str]:
    if proposal.symbol is None:
        raise ValueError("proposal symbol is required")

    tokens = [
        "quant-lab",
        "experiment",
        "run-default",
        "--title",
        proposal.title,
        "--hypothesis",
        proposal.hypothesis,
        "--strategy",
        strategy_path,
        "--data",
        config.data_paths[proposal.symbol],
        "--symbol",
        proposal.symbol,
        "--out",
        output_dir,
        "--cost-preset",
        config.cost_preset,
        "--benchmark",
        config.benchmark,
        "--intended-benefit",
        _intended_benefit(proposal),
        "--primary-metric",
        "max_drawdown",
        "--minimum-acceptable-performance",
        _minimum_acceptable_performance(proposal),
        "--tradeoff",
        "May give up upside during sustained equity bull markets.",
        "--tag",
        "campaign",
        "--tag",
        _tag_slug(config.title),
        "--train-end",
        DEFAULT_TRAIN_END,
        "--test-start",
        DEFAULT_TEST_START,
        "--select-by",
        "sharpe_ratio",
    ]
    for value in _param_arguments(proposal):
        tokens.extend(["--param", value])
    for window in DEFAULT_DATE_WINDOWS:
        tokens.extend(["--date-window", window])
    for criterion in _success_criterion_arguments(proposal.success_criteria):
        tokens.extend(["--success-criterion", criterion])
    return tokens


def _strategy_id(proposal: CampaignProposal) -> str:
    return _tag_slug(proposal.title).replace("-", "_")


def _template_length(proposal: CampaignProposal) -> int | None:
    if proposal.strategy_template != "sma-long-cash":
        return None
    return _single_positive_int(proposal.parameters.get("sma_length", 200), "sma_length")


def _param_arguments(proposal: CampaignProposal) -> list[str]:
    if proposal.strategy_template == "sma-long-cash":
        length = _single_positive_int(proposal.parameters.get("sma_length", 200), "sma_length")
        return [f"sma_{length}.inputs.length={length}"]
    if proposal.strategy_template == "ema-trend-follow":
        return ["ema_50.inputs.length=50"]
    raise ValueError(f"campaign conversion does not support template: {proposal.strategy_template}")


def _success_criterion_arguments(criteria: dict[str, Any]) -> list[str]:
    result: list[str] = []
    if "minimum_cagr_retention" in criteria:
        result.append(
            _criterion_json(
                {
                    "name": "return_retention",
                    "metric": "cagr",
                    "comparison": "strategy_vs_benchmark_ratio",
                    "operator": ">=",
                    "threshold": _number(criteria["minimum_cagr_retention"], "minimum_cagr_retention"),
                }
            )
        )
    if "minimum_relative_drawdown_reduction" in criteria:
        result.append(
            _criterion_json(
                {
                    "name": "drawdown_reduction",
                    "metric": "max_drawdown",
                    "comparison": "relative_reduction_vs_benchmark",
                    "operator": ">=",
                    "threshold": _number(
                        criteria["minimum_relative_drawdown_reduction"],
                        "minimum_relative_drawdown_reduction",
                    ),
                }
            )
        )
    if not result:
        raise ValueError("campaign proposal must include at least one supported success criterion")
    return result


def _criterion_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _intended_benefit(proposal: CampaignProposal) -> str:
    if "minimum_relative_drawdown_reduction" in proposal.success_criteria:
        return "Lower drawdown while retaining most benchmark CAGR."
    return proposal.rationale


def _minimum_acceptable_performance(proposal: CampaignProposal) -> str:
    parts: list[str] = []
    criteria = proposal.success_criteria
    if "minimum_cagr_retention" in criteria:
        parts.append(f"retain at least {float(criteria['minimum_cagr_retention']):.0%} of benchmark CAGR")
    if "minimum_relative_drawdown_reduction" in criteria:
        parts.append(
            f"reduce maximum drawdown by at least {float(criteria['minimum_relative_drawdown_reduction']):.0%} relative"
        )
    return "; ".join(parts) if parts else "Meet the proposal's prespecified success criteria."


def _format_command_markdown(inputs: CampaignExperimentInputs) -> str:
    return "\n".join(
        [
            f"# Planned Default Experiment: {inputs.proposal_title}",
            "",
            "Report role: campaign execution handoff.",
            "",
            "This command is generated from a validated campaign proposal. It has not been executed by this artifact.",
            "",
            "## Generated Inputs",
            "",
            f"- Strategy: `{inputs.strategy_path}`",
            f"- Data: `{inputs.data_path}`",
            f"- Output directory: `{inputs.output_dir}`",
            "",
            "## Command",
            "",
            "```bash",
            _shell_join_multiline(inputs.command_tokens),
            "```",
            "",
        ]
    )


def _shell_join_multiline(tokens: list[str]) -> str:
    lines: list[str] = []
    current: list[str] = []
    for token in tokens:
        current.append(shlex.quote(token))
        if token.startswith("--") and len(current) > 2:
            lines.append(" ".join(current[:-1]) + " \\")
            current = [current[-1]]
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def _single_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    return float(value)


def _tag_slug(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in cleaned.split("-") if part)[:80] or "campaign"
