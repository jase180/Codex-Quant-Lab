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

Create a deterministic recommendation without calling a model:

```bash
quant-lab agent suggest \
  --manifest artifacts/research/<experiment>/session_manifest.json
```

The command writes:

```text
agent_recommendation.json
agent_recommendation.md
```

Create a model-backed recommendation through an OpenAI-compatible local
endpoint:

```bash
quant-lab agent suggest \
  --manifest artifacts/research/<experiment>/session_manifest.json \
  --provider openai-compatible \
  --base-url http://localhost:11434/v1 \
  --model llama3.1:8b
```

If the provider is unreachable, returns invalid JSON, or returns JSON that does
not validate as `agent_recommendation.v1`, the command saves the deterministic
fallback recommendation and records the model failure as a risk.

Complete sessions short-circuit to the deterministic `stop` recommendation
before calling a model. A recorded decision is treated as authoritative state,
not as something a local model should reinterpret.

The provider requests structured JSON output with the
`agent_recommendation.v1` schema. Recommendations are also validated for obvious
action-command mismatches, such as `recommended_action: summarize` paired with
`quant-lab summarize-run-trust`.

Validate a recommendation before trusting it:

```bash
quant-lab agent validate-recommendation \
  --recommendation artifacts/research/<experiment>/agent_recommendation.json
```

Create one human-gated cycle without executing the proposed command:

```bash
quant-lab agent cycle \
  --manifest artifacts/research/<experiment>/session_manifest.json \
  --dry-run
```

The command writes a cycle directory containing:

```text
agent_context_bundle.json
agent_context_bundle.md
agent_recommendation.json
agent_recommendation.md
agent_cycle.json
agent_cycle.md
```

`agent cycle --dry-run` is the current safest loop entry point. It packages the
context, recommendation, proposed command, and stop reason, then stops before
running anything.

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

## Recommendation Contract

Agent recommendations use strict `agent_recommendation.v1` JSON:

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

Runnable actions require `next_command`, and `next_command` must start with
`quant-lab `. `stop` and `needs_review` do not require a command.

Allowed confidence values are:

- `low`
- `medium`
- `high`

## Stop Conditions

The advisor should stop and ask for review when:

- required artifacts are missing,
- the manifest has stale-artifact warnings,
- the recommended command would edit source code,
- the next step requires choosing new research assumptions,
- evidence is weak or contradictory,
- the model cannot produce valid JSON,
- the requested cycle limit has been reached.
- the command is running as `agent cycle --dry-run`.

## Why This Boundary Exists

Quant research workflows are easy to over-automate. The lab should make
experiments easier to repeat and interpret, not easier to overfit. A bounded
advisor gives useful momentum while keeping the CLI artifacts and human review
as the source of truth.

## Ollama Setup

Ollama is a practical first local runtime because it exposes an
OpenAI-compatible local endpoint.

Install and pull a model:

```powershell
winget install Ollama.Ollama
ollama pull llama3.1:8b
```

Check the local endpoint:

```powershell
curl http://localhost:11434/v1/models
```

Then run `agent suggest` with `--provider openai-compatible`.

The current recommended first model for this repo is `llama3.1:8b`. It is small
enough for a 32 GB RAM workstation and passed the strict
`agent_recommendation.v1` JSON contract during local integration testing.
