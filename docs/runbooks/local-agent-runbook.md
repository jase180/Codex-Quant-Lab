# Local Agent Runbook

This runbook is the copyable path for using the local-agent advisor safely.
It assumes the verified Windows venv, `.venv-win`, and keeps execution
human-triggered.

## Boundary

Current rule:

- `agent cycle --dry-run` is allowed.
- Non-dry-run `agent cycle` execution is deferred.
- The agent may recommend a `quant-lab` command, but a human or Codex session
  must decide whether to run it separately.

This keeps the local model useful as an advisor without turning it into an
unbounded operator.

## 1. Check The Environment

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli doctor
```

What it does:

- checks Python and project imports,
- checks pandas, matplotlib, and yfinance,
- checks required files,
- checks that artifacts can be written.

Use this first when returning to the repo after time away.

## 2. Create A Known-Good Offline Workflow

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli smoke-test --force
```

What it does:

- creates a small research plan using tracked sample data,
- runs one baseline,
- writes reports and metadata,
- refreshes a session manifest,
- prints the next recommended command.

This is a wiring check, not research evidence.

## 3. Refresh A Real Session Manifest

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli session refresh `
  --plan artifacts\research\<experiment>\research_plan.json
```

What it does:

- rebuilds `session_manifest.json`,
- rebuilds `session_manifest.md`,
- records current status,
- records missing or stale artifacts as warnings,
- records the next conservative workflow step.

Read this first after refresh:

```text
artifacts\research\<experiment>\session_manifest.md
```

## 4. Ask The Deterministic Workflow For The Next Step

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli research-plan next `
  --plan artifacts\research\<experiment>\research_plan.json
```

What it does:

- applies the built-in guided workflow rules,
- prints the next recommended step,
- prints the command when one is known.

Use this as the baseline comparison for local-agent advice.

## 5. Build The Agent Context Bundle

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli agent context `
  --manifest artifacts\research\<experiment>\session_manifest.json
```

What it writes:

```text
agent_context_bundle.json
agent_context_bundle.md
```

What it does:

- packages the manifest,
- embeds linked text artifacts,
- records missing or non-text files,
- lists operating rules and pending commands.

The local model should reason from this bundle, not from chat history.

## 6. Create A Deterministic Recommendation

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli agent suggest `
  --manifest artifacts\research\<experiment>\session_manifest.json
```

What it writes:

```text
agent_recommendation.json
agent_recommendation.md
```

What it does:

- creates a strict `agent_recommendation.v1` recommendation,
- uses deterministic workflow rules,
- uses `next_research_prompt` from `experiment_conclusion.json` when present,
- never calls a model.

This is the fallback path when model output is invalid.

## 7. Create A Model-Backed Recommendation

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli agent suggest `
  --manifest artifacts\research\<experiment>\session_manifest.json `
  --provider openai-compatible `
  --base-url http://localhost:11434/v1 `
  --model llama3.1:8b `
  --timeout-seconds 240
```

What it does:

- sends the same context contract to Ollama,
- spotlights `next_research_prompt` before the full context bundle,
- requests structured `agent_recommendation.v1` JSON,
- validates the model output,
- falls back to deterministic advice if validation fails.

Complete sessions short-circuit to deterministic `stop` before calling a model.

## 8. Run A Safe Dry-Run Cycle

Deterministic:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli agent cycle `
  --manifest artifacts\research\<experiment>\session_manifest.json `
  --dry-run
```

Model-backed:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli agent cycle `
  --manifest artifacts\research\<experiment>\session_manifest.json `
  --dry-run `
  --provider openai-compatible `
  --base-url http://localhost:11434/v1 `
  --model llama3.1:8b `
  --timeout-seconds 240
```

What it writes:

```text
agent_cycle/agent_context_bundle.json
agent_cycle/agent_context_bundle.md
agent_cycle/agent_recommendation.json
agent_cycle/agent_recommendation.md
agent_cycle/agent_cycle.json
agent_cycle/agent_cycle.md
```

What it does:

- packages context,
- writes a validated recommendation,
- records the proposed command,
- records why it stopped,
- stops before executing anything.

If the recommendation action is `research_design`, the cycle is doing its job:
the agent is advising on the next hypothesis or experiment design, not running a
new backtest.

## 9. Compare The Advice

Check these three outputs:

1. `research-plan next`
2. deterministic `agent cycle --dry-run`
3. model-backed `agent cycle --dry-run`

Healthy result:

- all three recommend the same workflow step, or
- the model recommends `needs_review` with a clear reason.

Suspicious result:

- the model recommends a command family that does not match its action,
- the model ignores manifest warnings,
- the model tries to edit code,
- the model wants to broaden the experiment before data trust exists.

The validator rejects obvious action-command mismatches. Use human review for
research judgment mismatches.

## 10. Validate A Saved Recommendation

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli agent validate-recommendation `
  --recommendation artifacts\research\<experiment>\agent_cycle\agent_recommendation.json
```

What it does:

- reloads the recommendation from disk,
- validates schema and command boundaries,
- prints the action, confidence, and command.

## Current Tested Happy Path

The in-progress validation experiment used this state:

```text
artifacts\research\agent_cycle_in_progress_check
```

It had:

- a baseline run,
- no run trust report,
- a refreshed session manifest.

Expected result:

- `research-plan next`: `run_trust`
- deterministic dry-run: `run_trust`
- model-backed dry-run: `run_trust`

The proposed command should be:

```powershell
quant-lab summarize-run-trust --metadata 'artifacts/research/agent_cycle_in_progress_check/baseline/run_metadata.json'
```

## If Something Looks Wrong

Prefer this order:

1. Run `quant-lab doctor`.
2. Refresh the session manifest.
3. Run `research-plan next`.
4. Run deterministic `agent cycle --dry-run`.
5. Run model-backed `agent cycle --dry-run`.
6. Compare outputs before running any proposed command.

Do not add non-dry-run execution while the deferred-execution boundary is in
place.
