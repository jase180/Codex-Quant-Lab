# Milestone 16: Session Manifests And Workflow Resume

## Status

In progress. The deterministic session manifest model, status/replay CLI, and
research-plan refresh command are implemented.

## Goal

Make one research session easy to inspect, resume, and replay without turning
the session record into another conclusion report.

The canonical conclusion answers what was learned. The session manifest should
answer where the files are, what commands were intended or run, what decision
was recorded, and what should happen next.

## Non-Goals

- No replacement for `experiment_conclusion.md`.
- No automatic rerunning of historical commands.
- No live trading or broker integration.
- No large database.
- No dashboard.
- No hidden LLM dependency. Local agents can read the manifest, but the CLI
  should generate useful manifests deterministically.

## Proposed Artifacts

Each research output directory should eventually contain:

```text
session_manifest.json
session_manifest.md
```

The JSON is for Codex, local agents, and future CLI checks. The Markdown is for
quick human orientation.

## Proposed JSON Fields

```text
schema_version
session_id
experiment_id
title
hypothesis
created_at_utc
updated_at_utc
plan_path
output_dir
data_sources
strategy_paths
commands
key_artifacts
conclusion_path
decision_path
current_status
outstanding_next_steps
warnings
```

`commands` should distinguish planned commands from commands the lab can
confirm were executed. This avoids pretending the manifest knows more than the
CLI recorded.

## CLI Shape

Likely commands:

```bash
quant-lab session status --manifest artifacts/research/<experiment>/session_manifest.json
quant-lab session replay-plan --manifest artifacts/research/<experiment>/session_manifest.json
quant-lab session refresh --plan artifacts/research/<experiment>/research_plan.json
```

`status` should print one compact orientation line plus the conclusion path.
`replay-plan` should print commands or next steps without executing them.
`refresh` should rebuild the manifest from the research plan, registry, research
index, and known artifact filenames.

## Build Order

1. Define the manifest schema and Markdown layout in docs. (Done.)
2. Add a small deterministic model and formatter. (Done.)
3. Add `session status` for existing manifests. (Done.)
4. Add `session replay-plan` for existing manifests. (Done.)
5. Add `session refresh` from a research plan and artifact directory. (Done.)
6. Teach conclusion commands to update manifest pointers when a manifest exists.
   (Done.)
7. Teach decision commands to update manifest pointers when a manifest exists.
   (Done.)
8. Add missing-artifact and stale-report warnings that point back to the
   canonical conclusion.
9. Update README and workflow docs so returning users read:
   `session_manifest.md` for orientation, then `experiment_conclusion.md` for
   the actual research conclusion.

## Acceptance Criteria

- A user can return after a week and find the current conclusion, decision,
  plan, and key artifacts from one manifest.
- A future Codex session or local agent can read the manifest and know what file
  to inspect first.
- The manifest points to the conclusion as the source of truth instead of
  duplicating the conclusion.
- The CLI can explain whether the workflow appears incomplete or stale.
- Tests cover manifest parsing, formatting, stale pointers, and missing
  artifacts.

## Why This Comes Before Strategy Language V2

The next risk is not expressiveness; it is continuity. The lab can already run
useful strategy experiments, but a real research cycle creates enough files that
resuming cleanly matters. Session manifests make the existing workflow easier to
trust before adding a more powerful strategy language.
