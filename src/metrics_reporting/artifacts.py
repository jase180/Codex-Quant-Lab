from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Sequence

from .metrics import RunMetrics, validate_equity_curve


def save_run_artifacts(
    output_dir: str | Path,
    metrics: RunMetrics,
    equity_curve: Sequence[dict[str, float | str]],
    report_markdown: str,
) -> dict[str, str]:
    validated_curve = validate_equity_curve(equity_curve)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    metrics_path = destination / "metrics.json"
    equity_curve_path = destination / "equity_curve.csv"
    report_path = destination / "report.md"

    metrics_path.write_text(
        json.dumps(metrics.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    with equity_curve_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "equity"])
        writer.writeheader()
        for point in validated_curve:
            writer.writerow(
                {
                    "date": point["date"],
                    "equity": float(point["equity"]),
                }
            )

    report_path.write_text(report_markdown, encoding="utf-8")

    return {
        "metrics": str(metrics_path),
        "equity_curve": str(equity_curve_path),
        "report": str(report_path),
    }
