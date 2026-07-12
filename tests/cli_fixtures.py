from __future__ import annotations

import json
from pathlib import Path


def _strategy_payload() -> dict:
    return {
        "schema_version": "v1",
        "strategy_id": "cli_smoke",
        "name": "CLI Smoke",
        "description": "A compact strategy used to test the CLI runner.",
        "strategy_type": "rule_based",
        "position_mode": "long_only",
        "market": {"symbol": "TEST", "timeframe": "1d"},
        "indicators": [
            {"id": "sma_2", "kind": "sma", "inputs": {"source": "close", "length": 2}},
            {"id": "sma_3", "kind": "sma", "inputs": {"source": "close", "length": 3}},
        ],
        "entry": {
            "when": "all",
            "conditions": [
                {
                    "left": {"price": "close"},
                    "operator": "gt",
                    "right": {"indicator": "sma_2"},
                }
            ],
        },
        "exit": {
            "when": "all",
            "conditions": [
                {
                    "left": {"price": "close"},
                    "operator": "lt",
                    "right": {"indicator": "sma_2"},
                }
            ],
        },
    }


def _write_ohlcv_fixture(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "date,open,high,low,close,volume",
                "2026-01-01,10,10,10,10,100",
                "2026-01-02,11,11,11,11,100",
                "2026-01-03,12,12,12,12,100",
                "2026-01-04,9,9,9,9,100",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_walk_forward_ohlcv_fixture(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "date,open,high,low,close,volume",
                "2026-01-01,10,10,10,10,100",
                "2026-01-02,11,11,11,11,100",
                "2026-01-03,12,12,12,12,100",
                "2026-01-04,13,13,13,13,100",
                "2026-01-05,12,12,12,12,100",
                "2026-01-06,14,14,14,14,100",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_index_fixture(path: Path) -> None:
    records = [
        {
            "index_schema_version": "research_index.v1",
            "created_at_utc": "2026-01-01T00:00:00Z",
            "run_type": "run",
            "run_id": None,
            "experiment_id": "EXP-001",
            "strategy_id": "slow_strategy",
            "strategy_name": "Slow Strategy",
            "symbol": "SPY",
            "timeframe": "1d",
            "data_start": "2026-01-01",
            "data_end": "2026-01-31",
            "final_equity": 1010,
            "total_return": 0.01,
            "cagr": 0.12,
            "sharpe_ratio": 0.5,
            "max_drawdown": -0.05,
            "trade_count": 2,
            "benchmark_total_return": 0.02,
            "benchmark_max_drawdown": -0.03,
            "excess_total_return": -0.01,
            "sizing": "fixed-shares",
            "initial_cash": 1000,
            "quantity": 1,
            "allocation": 1,
            "commission_fixed": 0,
            "commission_rate": 0,
            "slippage_bps": 0,
            "output_dir": "artifacts/spy_run",
            "metadata_path": "artifacts/spy_run/run_metadata.json",
            "git_commit": "abc",
        },
        {
            "index_schema_version": "research_index.v1",
            "created_at_utc": "2026-01-02T00:00:00Z",
            "run_type": "run",
            "run_id": None,
            "experiment_id": "EXP-002",
            "strategy_id": "fast_strategy",
            "strategy_name": "Fast Strategy",
            "symbol": "QQQ",
            "timeframe": "1d",
            "data_start": "2026-01-01",
            "data_end": "2026-01-31",
            "final_equity": 1100,
            "total_return": 0.10,
            "cagr": 1.2,
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.10,
            "trade_count": 4,
            "benchmark_total_return": 0.06,
            "benchmark_max_drawdown": -0.08,
            "excess_total_return": 0.04,
            "sizing": "percent-equity",
            "initial_cash": 1000,
            "quantity": 1,
            "allocation": 1,
            "commission_fixed": 0,
            "commission_rate": 0,
            "slippage_bps": 0,
            "output_dir": "artifacts/qqq_run",
            "metadata_path": "artifacts/qqq_run/run_metadata.json",
            "git_commit": "def",
        },
    ]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
