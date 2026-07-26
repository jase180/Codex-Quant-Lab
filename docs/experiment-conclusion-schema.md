# Experiment Conclusion Schema

## Purpose

`experiment_conclusion.md` and `experiment_conclusion.json` are the canonical
conclusion artifacts for one research experiment.

They are intentionally different from raw run metadata, evidence summaries, and
robustness reports:

- `experiment_conclusion.md` is the file a human should read first.
- `experiment_conclusion.json` is the file Codex or a local agent should parse
  first.
- Supporting artifacts remain available, but they should not compete with the
  conclusion as the top-level explanation.

The conclusion is not a claim of market truth. It is a conservative local
research state derived from linked artifacts.

## File Locations

Default output directory:

```text
artifacts/research/<experiment_slug>/
```

Default files:

```text
experiment_conclusion.md
experiment_conclusion.json
agent_context.md
```

The conclusion writer may allow custom paths, but guided workflows should point
to these default names.

## JSON Schema Version

Use:

```json
{
  "schema_version": "experiment_conclusion.v1"
}
```

The schema should be strict. Unknown top-level fields should be rejected by
future loaders unless a migration path exists.

## Top-Level JSON Shape

```json
{
  "schema_version": "experiment_conclusion.v1",
  "experiment_id": "EXP-001",
  "generated_at_utc": "2026-07-25T00:00:00Z",
  "generator": {
    "name": "quant-lab conclude-experiment",
    "mode": "deterministic",
    "version": "unknown"
  },
  "experiment": {
    "title": "QQQ SMA crossover trust check",
    "hypothesis": "A daily SMA crossover may reduce drawdown versus buy-and-hold.",
    "status": "running",
    "tags": ["qqq", "sma"],
    "strategy_path": "data/strategies/qqq_sma_crossover.json",
    "data_path": "data/cache/QQQ_2015-01-01_2025-12-31.csv"
  },
  "confidence_label": "mixed",
  "current_conclusion": "The current evidence is mixed...",
  "supporting_evidence": [],
  "contradicting_evidence": [],
  "robustness_notes": [],
  "do_not_repeat": [],
  "next_useful_tests": [],
  "open_questions": [],
  "source_artifacts": [],
  "agent_instructions": []
}
```

## Field Definitions

### `generator`

Records how the conclusion was produced.

Fields:

- `name`: command or tool name.
- `mode`: `deterministic`, `agent_assisted`, or `manual`.
- `version`: package version, Git commit, or `unknown`.

The first implementation should use `deterministic`.

### `experiment`

Copies the experiment identity fields needed for orientation. This is not a
replacement for the experiment registry; it is a snapshot for quick reading.

### `confidence_label`

Conservative label for the current state of evidence.

Allowed initial values:

- `no_evidence`
- `weak`
- `mixed`
- `promising`
- `rejected`
- `accepted`

This should align with existing evidence-label language where possible.

### `current_conclusion`

One paragraph that states the current research conclusion.

It should be boring and explicit. Example:

```text
The QQQ SMA crossover reduced drawdown in some linked runs, but it has not
shown reliable benchmark outperformance after validation and robustness checks.
Do not continue tuning SMA lengths until the failure mode is explained.
```

### `supporting_evidence`

List of evidence items that support the hypothesis.

Each item:

```json
{
  "label": "Best validation run beat benchmark",
  "run_id": "test_selected",
  "run_type": "test_selected_run",
  "metric": "excess_total_return",
  "value": 0.03,
  "artifact_path": "artifacts/research/.../run_metadata.json",
  "note": "Positive validation excess return."
}
```

### `contradicting_evidence`

List of evidence items that weaken or contradict the hypothesis. Same shape as
`supporting_evidence`.

Contradicting evidence should include benchmark underperformance, failed
validation, large drawdowns, tiny trade counts, missing trust checks, or failed
robustness checks when present.

### `robustness_notes`

Short structured notes about robustness artifacts.

Each item:

```json
{
  "check": "cost_sensitivity",
  "status": "missing",
  "artifact_path": null,
  "summary": "No linked cost_sensitivity_run rows were found."
}
```

Suggested `status` values:

- `missing`
- `passed`
- `mixed`
- `failed`
- `not_applicable`

### `do_not_repeat`

List of research actions that should not be repeated without a changed
hypothesis.

Examples:

- `Do not keep widening SMA length sweeps on QQQ until validation failure is explained.`
- `Do not accept a run that only beats cash but trails buy-and-hold.`
- `Do not rerun the same window after seeing date-sensitivity failures.`

### `next_useful_tests`

Small falsifiable follow-up tests.

Each item:

```json
{
  "test": "Run the same predefined trend rule on SPY.",
  "reason": "Checks whether the drawdown tradeoff generalizes beyond QQQ.",
  "success_criteria": "Positive excess return versus buy-and-hold with retail-liquid costs.",
  "suggested_command": "quant-lab ..."
}
```

The command can be `null` when human judgment is needed first.

### `open_questions`

Questions that block confidence.

Examples:

- `Did adjusted prices include dividends consistently for all compared assets?`
- `Is the result driven by one short market regime?`
- `Are there enough trades for the metric shape to mean anything?`

### `source_artifacts`

All important files used to generate the conclusion.

Each item:

```json
{
  "kind": "run_metadata",
  "path": "artifacts/research/.../run_metadata.json",
  "role": "supporting"
}
```

Suggested `kind` values:

- `experiment_registry`
- `research_index`
- `run_metadata`
- `portfolio_metadata`
- `evidence_summary`
- `robustness_report`
- `data_trust_report`
- `portfolio_summary`
- `manual_note`

### `agent_instructions`

Instructions a local agent should follow before proposing the next cycle.

Default items:

- `Read experiment_conclusion.json before scanning raw artifacts.`
- `Treat current_conclusion as provisional, not market truth.`
- `Respect do_not_repeat unless the hypothesis changes.`
- `Propose small falsifiable next tests, not broad optimization.`
- `Cite source_artifacts when making claims.`
- `Preserve no-lookahead and next-open-fill assumptions.`

## Markdown Layout

`experiment_conclusion.md` should use this section order:

```text
# Experiment Conclusion: EXP-001

## Current Conclusion

## Confidence

## What Was Tested

## What Supports This

## What Contradicts This

## Robustness Status

## Do Not Repeat

## Next Useful Tests

## Open Questions

## Source Artifacts

## Agent Instructions
```

The Markdown should be concise. It should link to supporting artifacts instead
of copying every row from existing reports.

## Agent Context Layout

`agent_context.md` is optional in the first implementation, but when written it
should be small and stable:

```text
# Agent Context

Read first:
- experiment_conclusion.json
- experiment_conclusion.md

Rules:
- Do not optimize to the best backtest row.
- Respect do_not_repeat.
- Suggest one or two small next tests.
- Cite source artifacts.
- Ask for data verification when provider assumptions matter.
```

## Deterministic First, Agent Assisted Later

The first CLI implementation should generate a useful conclusion without any
LLM. Local agents can later:

- critique the deterministic conclusion,
- rewrite prose,
- propose next tests,
- identify missing evidence,
- compare against prior conclusions.

The agent should not be the only source of the conclusion. The source of truth
is the linked artifacts plus the structured conclusion fields.

## Initial CLI Target

Proposed command:

```bash
quant-lab conclude-experiment \
  --experiment-id EXP-001 \
  --experiments-path artifacts/experiments.jsonl \
  --index-path artifacts/research_index.jsonl \
  --out artifacts/research/qqq_sma_trust
```

Default outputs:

```text
artifacts/research/qqq_sma_trust/experiment_conclusion.md
artifacts/research/qqq_sma_trust/experiment_conclusion.json
artifacts/research/qqq_sma_trust/agent_context.md
```

## Validation Requirements

Tests should cover:

- no linked evidence,
- positive supporting evidence,
- contradicting validation evidence,
- missing robustness checks,
- mixed robustness checks,
- `do_not_repeat` generation,
- `next_useful_tests` generation,
- strict schema field names,
- Markdown section order,
- agent instructions presence.
