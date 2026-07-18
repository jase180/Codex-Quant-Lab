from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_lab.cli import main  # noqa: E402


class CliResearchPlanTests(unittest.TestCase):
    def test_research_plan_init_writes_plan_and_prints_baseline_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_dir = temp_path / "research" / "qqq_sma"
            experiments_path = temp_path / "experiments.jsonl"
            index_path = temp_path / "research_index.jsonl"

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "research-plan",
                        "init",
                        "--title",
                        "QQQ SMA trust check",
                        "--hypothesis",
                        "A crossover may reduce drawdown.",
                        "--strategy",
                        "data/strategies/qqq_sma.json",
                        "--data",
                        "data/cache/qqq.csv",
                        "--symbol",
                        "qqq",
                        "--tag",
                        "QQQ,sma",
                        "--out",
                        str(output_dir),
                        "--experiments-path",
                        str(experiments_path),
                        "--index-path",
                        str(index_path),
                        "--cost-preset",
                        "retail-liquid",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "research_plan.json").exists())
            self.assertTrue((output_dir / "research_plan.md").exists())
            plan = json.loads((output_dir / "research_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["schema_version"], "research_plan.v1")
            self.assertEqual(plan["experiment_id"], "EXP-001")
            self.assertEqual(plan["symbol"], "QQQ")
            self.assertEqual(plan["tags"], ["qqq", "sma"])
            self.assertEqual(plan["experiments_path"], str(experiments_path))
            self.assertEqual(plan["index_path"], str(index_path))
            self.assertEqual(plan["cost_preset"], "retail-liquid")
            self.assertEqual(plan["sizing"], "percent-equity")

            experiment = json.loads(experiments_path.read_text(encoding="utf-8").strip())
            self.assertEqual(experiment["experiment_id"], "EXP-001")
            self.assertEqual(experiment["title"], "QQQ SMA trust check")
            self.assertEqual(experiment["strategy_path"], "data/strategies/qqq_sma.json")
            self.assertEqual(experiment["data_path"], "data/cache/qqq.csv")

            output = stdout.getvalue()
            self.assertIn("Research plan created:", output)
            self.assertIn("experiment_id: EXP-001", output)
            self.assertIn("next_command:", output)
            self.assertIn("quant-lab run", output)
            self.assertIn("--out", output)
            self.assertIn(str(output_dir / "baseline"), output)
            self.assertIn("--experiment-id EXP-001", output)
            self.assertIn("--cost-preset retail-liquid", output)
            self.assertIn("--index-path", output)
            self.assertIn(str(index_path), output)

    def test_research_plan_init_can_reference_existing_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_dir = temp_path / "research" / "qqq_sma"
            experiments_path = temp_path / "experiments.jsonl"

            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "new-experiment",
                        "--experiments-path",
                        str(experiments_path),
                        "--experiment-id",
                        "EXP-010",
                        "--title",
                        "Existing idea",
                        "--hypothesis",
                        "Already recorded.",
                    ]
                )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(
                    [
                        "research-plan",
                        "init",
                        "--title",
                        "QQQ SMA trust check",
                        "--hypothesis",
                        "A crossover may reduce drawdown.",
                        "--strategy",
                        "data/strategies/qqq_sma.json",
                        "--data",
                        "data/cache/qqq.csv",
                        "--symbol",
                        "QQQ",
                        "--experiment-id",
                        "EXP-010",
                        "--out",
                        str(output_dir),
                        "--experiments-path",
                        str(experiments_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            records = [json.loads(line) for line in experiments_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["experiment_id"], "EXP-010")
            plan = json.loads((output_dir / "research_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["experiment_id"], "EXP-010")
            self.assertIn("experiment_id: EXP-010", stdout.getvalue())

    def test_research_plan_next_recommends_baseline_when_no_runs_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, _ = self._create_plan_fixture(Path(temp_dir))

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["research-plan", "next", "--plan", str(output_dir / "research_plan.json")])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: baseline", output)
            self.assertIn("No baseline run", output)
            self.assertIn("quant-lab run", output)
            self.assertIn(str(output_dir / "baseline"), output)

    def test_research_plan_next_recommends_sweep_after_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, index_path = self._create_plan_fixture(Path(temp_dir))
            self._write_index_records(index_path, [{"run_type": "run", "experiment_id": "EXP-001"}])

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["research-plan", "next", "--plan", str(output_dir / "research_plan.json")])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: sweep", output)
            self.assertIn("quant-lab sweep", output)
            self.assertIn("--param indicator_id.inputs.length=VALUE1,VALUE2", output)
            self.assertIn(str(output_dir / "sweep_001"), output)

    def test_research_plan_next_recommends_train_test_after_sweep(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, _, index_path = self._create_plan_fixture(Path(temp_dir))
            self._write_index_records(
                index_path,
                [
                    {"run_type": "run", "experiment_id": "EXP-001"},
                    {"run_type": "sweep_run", "experiment_id": "EXP-001"},
                ],
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                exit_code = main(["research-plan", "next", "--plan", str(output_dir / "research_plan.json")])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recommended_step: train_test", output)
            self.assertIn("--train-end YYYY-MM-DD", output)
            self.assertIn("--test-start YYYY-MM-DD", output)
            self.assertIn("--select-by sharpe_ratio", output)

    def _create_plan_fixture(self, temp_path: Path) -> tuple[Path, Path, Path]:
        output_dir = temp_path / "research" / "qqq_sma"
        experiments_path = temp_path / "experiments.jsonl"
        index_path = temp_path / "research_index.jsonl"
        with contextlib.redirect_stdout(io.StringIO()):
            main(
                [
                    "research-plan",
                    "init",
                    "--title",
                    "QQQ SMA trust check",
                    "--hypothesis",
                    "A crossover may reduce drawdown.",
                    "--strategy",
                    "data/strategies/qqq_sma.json",
                    "--data",
                    "data/cache/qqq.csv",
                    "--symbol",
                    "QQQ",
                    "--out",
                    str(output_dir),
                    "--experiments-path",
                    str(experiments_path),
                    "--index-path",
                    str(index_path),
                    "--cost-preset",
                    "retail-liquid",
                ]
            )
        return output_dir, experiments_path, index_path

    def _write_index_records(self, index_path: Path, records: list[dict]) -> None:
        index_path.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
