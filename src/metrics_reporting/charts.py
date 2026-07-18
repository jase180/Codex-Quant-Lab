"""Chart helpers for equity and drawdown artifacts."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Sequence

# Matplotlib tries to create its config/cache under the user's profile by
# default. Some managed Windows shells block that path, so provide a writable
# temp fallback unless the caller already chose `MPLCONFIGDIR`.
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "codex_quant_lab_matplotlib"))

import matplotlib

# "Agg" is matplotlib's file-only backend. It lets tests and CLI runs create PNGs
# inside WSL or CI without needing a desktop windowing system.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from .metrics import validate_equity_curve


def drawdown_curve(equity_curve: Sequence[dict[str, float | str]]) -> list[dict[str, float | str]]:
    validated_curve = validate_equity_curve(equity_curve)
    peak = float(validated_curve[0]["equity"])
    drawdowns: list[dict[str, float | str]] = []

    for point in validated_curve:
        equity = float(point["equity"])
        # Drawdown is measured from the highest equity seen so far, not from the
        # starting cash. A new high resets the peak before future declines.
        peak = max(peak, equity)
        drawdowns.append(
            {
                "date": str(point["date"]),
                "drawdown": (equity / peak) - 1.0,
            }
        )

    return drawdowns


def save_equity_curve_chart(
    strategy_curve: Sequence[dict[str, float | str]],
    benchmark_curve: Sequence[dict[str, float | str]],
    output_path: str | Path,
    benchmark_label: str = "Benchmark",
) -> str:
    strategy_frame = _curve_frame(strategy_curve, "equity")
    benchmark_frame = _curve_frame(benchmark_curve, "equity")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    fig, axis = plt.subplots(figsize=(10, 5))
    axis.plot(strategy_frame["date"], strategy_frame["equity"], label="Strategy")
    axis.plot(benchmark_frame["date"], benchmark_frame["equity"], label=benchmark_label)
    axis.set_title("Equity Curve")
    axis.set_xlabel("Date")
    axis.set_ylabel("Equity")
    axis.grid(True, alpha=0.3)
    axis.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(destination)
    plt.close(fig)
    return str(destination)


def save_drawdown_chart(
    strategy_curve: Sequence[dict[str, float | str]],
    benchmark_curve: Sequence[dict[str, float | str]],
    output_path: str | Path,
    benchmark_label: str = "Benchmark",
) -> str:
    strategy_frame = _drawdown_frame(strategy_curve)
    benchmark_frame = _drawdown_frame(benchmark_curve)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    fig, axis = plt.subplots(figsize=(10, 5))
    axis.plot(strategy_frame["date"], strategy_frame["drawdown"], label="Strategy")
    axis.plot(benchmark_frame["date"], benchmark_frame["drawdown"], label=benchmark_label)
    axis.set_title("Drawdown")
    axis.set_xlabel("Date")
    axis.set_ylabel("Drawdown")
    axis.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    axis.grid(True, alpha=0.3)
    axis.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(destination)
    plt.close(fig)
    return str(destination)


def _curve_frame(equity_curve: Sequence[dict[str, float | str]], value_column: str) -> pd.DataFrame:
    validated_curve = validate_equity_curve(equity_curve)
    return pd.DataFrame(
        {
            "date": pd.to_datetime([point["date"] for point in validated_curve]),
            value_column: [float(point["equity"]) for point in validated_curve],
        }
    )


def _drawdown_frame(equity_curve: Sequence[dict[str, float | str]]) -> pd.DataFrame:
    drawdowns = drawdown_curve(equity_curve)
    return pd.DataFrame(
        {
            "date": pd.to_datetime([point["date"] for point in drawdowns]),
            "drawdown": [float(point["drawdown"]) for point in drawdowns],
        }
    )
