"""Typed run configuration shared by CLI workflows and artifact writers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .costs import CostAssumptions


@dataclass(frozen=True)
class RunExecutionConfig:
    """Stable run settings after CLI flags have been parsed.

    The CLI receives a broad ``argparse.Namespace``. Internals should use this
    narrower object so artifact writers do not depend on every CLI flag name.
    """

    data_path: str | Path
    index_path: str | Path
    initial_cash: float
    quantity: float
    sizing: str
    allocation: float
    benchmark: str
    cost_assumptions: CostAssumptions
    command_tokens: tuple[str, ...]
    experiment_id: str | None = None

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "RunExecutionConfig":
        return cls(
            data_path=args.data,
            index_path=args.index_path,
            initial_cash=float(args.initial_cash),
            quantity=float(args.quantity),
            sizing=str(args.sizing),
            allocation=float(args.allocation),
            benchmark=str(args.benchmark),
            cost_assumptions=args.cost_assumptions,
            command_tokens=tuple(args.command_tokens),
            experiment_id=getattr(args, "experiment_id", None),
        )

    @classmethod
    def from_values(
        cls,
        *,
        data_path: str | Path,
        index_path: str | Path,
        initial_cash: float,
        quantity: float,
        sizing: str,
        allocation: float,
        benchmark: str,
        cost_assumptions: CostAssumptions,
        command_tokens: Sequence[str],
        experiment_id: str | None = None,
    ) -> "RunExecutionConfig":
        return cls(
            data_path=data_path,
            index_path=index_path,
            initial_cash=float(initial_cash),
            quantity=float(quantity),
            sizing=sizing,
            allocation=float(allocation),
            benchmark=benchmark,
            cost_assumptions=cost_assumptions,
            command_tokens=tuple(command_tokens),
            experiment_id=experiment_id,
        )
