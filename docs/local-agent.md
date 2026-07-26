# Local Agent Advisor

This project treats a local agent as an experiment advisor, not as the owner of
the repo.

The agent should read the current research state, recommend the next experiment
or analysis step, explain why, and stop. It should not freely edit source code,
mutate registries outside the CLI, run unlimited experiments, or treat a good
backtest as proof.

## Current Entry Points

Check whether the repo is runnable:

```bash
quant-lab doctor
```

Run an offline wiring check:

```bash
quant-lab smoke-test
```

Build the context bundle a local advisor should read:

```bash
quant-lab agent context \
  --manifest artifacts/research/<experiment>/session_manifest.json
```

The command writes:

```text
agent_context_bundle.json
agent_context_bundle.md
```

Use `--json` when another process needs the context on stdout:

```bash
quant-lab agent context \
  --manifest artifacts/research/<experiment>/session_manifest.json \
  --json
```

## Context Contract

The context bundle starts from `session_manifest.json`. It includes:

- the full session manifest payload,
- operating rules,
- read order,
- pending next commands,
- manifest warnings,
- selected linked artifact contents,
- explicit records for missing or non-text files.

The bundle does not depend on chat history. A future Codex session, local model,
or other process should be able to read it cold.

## Operating Rules

The advisor must follow these rules:

- Recommend the next experiment or analysis step; do not edit source code.
- Use saved artifacts as the source of truth; do not rely on chat history.
- Treat weak samples, missing trust reports, and benchmark underperformance as
  real warnings.
- Return a bounded recommendation and stop before running commands.

## Read Order

For a normal research session:

1. `session_manifest.md`
2. `agent_context_bundle.md`
3. `experiment_conclusion.md`, if present
4. `experiment_conclusion.json`, if present
5. supporting evidence and trust reports referenced by the bundle
6. raw metadata only when needed

For automation, prefer:

1. `session_manifest.json`
2. `agent_context_bundle.json`
3. `experiment_conclusion.json`, if present
4. linked `run_metadata.json` files only when needed

## Expected Recommendation Shape

The next milestone phase will make this strict, but the intended shape is:

```json
{
  "schema_version": "agent_recommendation.v1",
  "recommended_action": "run_trust",
  "reason": "A baseline exists, but the data-trust report is missing.",
  "next_command": "quant-lab summarize-run-trust --metadata artifacts/.../run_metadata.json",
  "risks": ["The sample is too short for research interpretation."],
  "do_not_repeat": ["Do not widen into a sweep before data trust is checked."],
  "confidence": "medium"
}
```

Allowed actions will be intentionally small and workflow-shaped, such as:

- `baseline`
- `run_trust`
- `sweep`
- `train_test`
- `summarize`
- `robustness`
- `conclude`
- `decide`
- `stop`
- `needs_review`

## Stop Conditions

The advisor should stop and ask for review when:

- required artifacts are missing,
- the manifest has stale-artifact warnings,
- the recommended command would edit source code,
- the next step requires choosing new research assumptions,
- evidence is weak or contradictory,
- the model cannot produce valid JSON,
- the requested cycle limit has been reached.

## Why This Boundary Exists

Quant research workflows are easy to over-automate. The lab should make
experiments easier to repeat and interpret, not easier to overfit. A bounded
advisor gives useful momentum while keeping the CLI artifacts and human review
as the source of truth.
