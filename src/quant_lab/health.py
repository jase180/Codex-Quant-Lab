"""Environment and repo health checks for local Quant Lab work."""

from __future__ import annotations

import importlib
import json
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


HealthStatus = Literal["ok", "warn", "fail"]


@dataclass(frozen=True)
class HealthCheck:
    name: str
    status: HealthStatus
    message: str


@dataclass(frozen=True)
class HealthReport:
    status: HealthStatus
    checks: list[HealthCheck]
    next_command: str


def run_doctor(*, repo_root: str | Path = ".", artifacts_dir: str | Path = "artifacts", data_cache_dir: str | Path = "data/cache") -> HealthReport:
    """Inspect whether the local checkout is ready for normal CLI research.

    The doctor command intentionally avoids live market-data calls. It should be
    safe for a future local agent to run before making a recommendation.
    """

    root = Path(repo_root)
    checks = [
        _python_version_check(),
        _import_check("pandas"),
        _import_check("matplotlib"),
        _import_check("yfinance"),
        _import_check("backtester_core"),
        _import_check("quant_lab"),
        _import_check("metrics_reporting"),
        _required_file_check(root / "pyproject.toml"),
        _required_file_check(root / "data" / "sample_ohlcv.csv"),
        _required_file_check(root / "data" / "strategies" / "sma_crossover.json"),
        _required_file_check(root / "docs" / "getting-running.md"),
        _artifacts_write_check(root / artifacts_dir),
        _data_cache_check(root / data_cache_dir),
    ]
    return HealthReport(
        status=_overall_status(checks),
        checks=checks,
        next_command="quant-lab research-plan init --help",
    )


def format_health_report(report: HealthReport) -> str:
    lines = [f"Quant Lab doctor: {report.status.upper()}"]
    for check in report.checks:
        lines.append(f"[{check.status.upper()}] {check.name}: {check.message}")
    lines.append(f"next: {report.next_command}")
    return "\n".join(lines)


def health_report_to_json(report: HealthReport) -> str:
    return json.dumps(asdict(report), indent=2, sort_keys=True)


def _overall_status(checks: list[HealthCheck]) -> HealthStatus:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "ok"


def _python_version_check() -> HealthCheck:
    version = sys.version_info
    current = f"{version.major}.{version.minor}.{version.micro}"
    if version < (3, 10):
        return HealthCheck("python", "fail", f"Python {current} is too old; Python 3.10+ is required.")
    return HealthCheck("python", "ok", f"Python {current} on {platform.system()}.")


def _import_check(module_name: str) -> HealthCheck:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - exact import failures vary by environment.
        return HealthCheck(module_name, "fail", f"Cannot import {module_name}: {exc}")

    version = getattr(module, "__version__", None)
    if version:
        return HealthCheck(module_name, "ok", f"Import succeeded, version {version}.")
    return HealthCheck(module_name, "ok", "Import succeeded.")


def _required_file_check(path: Path) -> HealthCheck:
    if path.exists():
        return HealthCheck(_display_path(path), "ok", "Found.")
    return HealthCheck(_display_path(path), "fail", "Missing required project file.")


def _artifacts_write_check(path: Path) -> HealthCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".doctor_write_test"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
    except Exception as exc:
        return HealthCheck(_display_path(path), "fail", f"Cannot write artifacts here: {exc}")
    return HealthCheck(_display_path(path), "ok", "Writable.")


def _data_cache_check(path: Path) -> HealthCheck:
    if not path.exists():
        return HealthCheck(_display_path(path), "warn", "Data cache does not exist yet; run quant-lab fetch for real data.")
    csv_files = sorted(path.glob("*.csv"))
    if not csv_files:
        return HealthCheck(_display_path(path), "warn", "Data cache has no CSV files yet; run quant-lab fetch for real data.")
    provenance_count = sum(1 for csv_path in csv_files if csv_path.with_suffix(".provenance.json").exists())
    return HealthCheck(
        _display_path(path),
        "ok",
        f"Found {len(csv_files)} cached CSV file(s), {provenance_count} with provenance sidecars.",
    )


def _display_path(path: Path) -> str:
    return path.as_posix()
