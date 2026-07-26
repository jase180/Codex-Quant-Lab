# Milestone 17: Local Agent Advisor

## Status

Planned.

## Goal

Add a local-agent advisor loop that can read the current experiment state,
recommend the next research step, explain why, and stop.

This milestone is deliberately not about giving an agent full control of the
repo. The agent should help choose the next experiment or analysis cycle. It
should not freely rewrite code, mutate registries behind the CLI, or run
unbounded batches.

## Product Boundary

The first local agent is an experiment recommender.

Allowed:

- Read `session_manifest.json`.
- Read the linked plan, run metadata, reports, warnings, and conclusion files.
- Recommend the next conservative research action.
- Produce a structured recommendation artifact.
- Include one suggested `quant-lab` command when appropriate.

Not allowed in this milestone:

- Editing strategy or Python source files.
- Running commands without a human/Codex approval step.
- Running unlimited cycles.
- Treating a good backtest as proof.
- Hiding changed assumptions, skipped trust checks, or weak evidence.

## Why This Comes Next

The lab now has enough durable state for an agent to orient itself:

- guided research plans,
- saved run metadata,
- data-trust and evidence artifacts,
- canonical experiment conclusions,
- session manifests with stale/missing artifact warnings.

The next highest-value step is not a more expressive strategy language. It is a
clear interface between the lab and an agent that can say, "given the current
evidence, this is the next experiment worth running."

## Phase 1: Operator Health And Smoke Path

Goal: make the project easy for a human or agent to prove runnable.

Planned work:

- Add `quant-lab doctor` for dependency, import, artifact-directory, and data
  cache checks.
- Add or document a one-command smoke workflow that uses tracked sample data.
- Ensure the command output says which file to read next.
- Keep the smoke workflow honest by labeling it as a wiring check, not research
  evidence.

Exit criteria:

- A fresh checkout can prove that the environment is ready without guessing at
  commands.
- A local agent can run or request a health check before giving research advice.

## Phase 2: Agent Context Contract

Goal: define exactly what the agent reads.

Planned work:

- Document the required context files in `docs/local-agent.md`.
- Build a context assembler that starts from `session_manifest.json`.
- Include only the current plan, current recommendation, latest relevant
  reports, conclusion, warnings, and artifact paths.
- Record missing or stale context explicitly instead of silently omitting it.

Exit criteria:

- A human can inspect the same context the agent receives.
- The agent prompt does not depend on chat history.

## Phase 3: Recommendation Schema

Goal: make agent output strict and testable.

Initial shape:

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

Planned work:

- Define allowed `recommended_action` values.
- Validate required fields.
- Reject unknown actions.
- Save both JSON and Markdown recommendation artifacts.
- Add tests around valid, invalid, and cautious recommendations.

Exit criteria:

- The repo can tell whether an agent recommendation is structurally valid before
  a human decides whether to run it.

## Phase 4: Deterministic Advisor Command

Goal: implement the agent shape before adding a model.

Command sketch:

```bash
quant-lab agent suggest --manifest artifacts/research/<name>/session_manifest.json
```

Behavior:

- Reads the manifest and linked files.
- Uses deterministic workflow rules first.
- Writes `agent_recommendation.json`.
- Writes `agent_recommendation.md`.
- Prints the recommended action and next command.

Exit criteria:

- The CLI can produce a valid recommendation artifact without calling an LLM.
- The deterministic path becomes the fallback when a local model fails.

## Phase 5: Local Model Adapter

Goal: let a local model reason over the same context contract.

Provider shape:

```bash
quant-lab agent suggest \
  --manifest artifacts/research/<name>/session_manifest.json \
  --provider openai-compatible \
  --base-url http://localhost:11434/v1 \
  --model qwen2.5:7b
```

Candidate local runtimes:

- Ollama.
- LM Studio.
- llama.cpp server.
- Any OpenAI-compatible local HTTP endpoint.

Planned work:

- Build a small provider interface.
- Send a cautious research-advisor prompt.
- Parse model output as JSON.
- Validate the output against the recommendation schema.
- Fall back to deterministic advice if the model output is invalid.

Exit criteria:

- A local model can suggest the next research step, but invalid or vague output
  cannot enter the workflow as a valid recommendation.

## Phase 6: Human-Gated Iteration

Goal: support iteration without pretending it is full autonomy.

Command sketch:

```bash
quant-lab agent cycle \
  --manifest artifacts/research/<name>/session_manifest.json \
  --max-steps 3 \
  --dry-run
```

Rules:

- `--max-steps` is required for any non-dry-run cycle.
- The command may only run approved `quant-lab` research commands.
- Every step must write a recommendation artifact.
- Stop on failed commands, missing context, invalid model output, stale
  artifacts, or a needed human decision.
- No source-code edits.

Exit criteria:

- The agent can help iterate through a short bounded research loop while leaving
  an auditable trail of recommendations, commands, outputs, and stop reasons.

## Done Criteria

Milestone 17 is done when:

- setup/runnability can be checked by command,
- the local-agent context contract is documented,
- recommendations have a strict schema,
- deterministic `agent suggest` works,
- local-model `agent suggest` works through at least one OpenAI-compatible
  adapter,
- `agent cycle --dry-run` can show a bounded plan,
- non-dry-run cycling is guarded by explicit limits and stop conditions,
- README and workflow docs explain that the agent recommends experiments rather
  than owning the repo.

## Follow-On Work

After this milestone, the lab can return to broader research features:

- Strategy Language V2.
- Portfolio realism.
- Example research library.
- Packaging, CI, and maintenance hardening.
