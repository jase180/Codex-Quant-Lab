# Runbooks

This page is the short map for operating the lab. Use it when you know what
you want to do, but not which document has the commands.

## Start Here

- [Getting Running](getting-running.md): install checks, dependency health,
  `doctor`, and the offline smoke test.
- [Research Workflow](research-workflow.md): the default one-strategy research
  loop from plan creation through conclusion.
- [Trustworthy Example Workflow](trustworthy-example-workflow.md): a copyable
  skeptical example that keeps one experiment narrow.

## Local-Agent Advisor

- [Local Agent](local-agent.md): the advisor contract, boundaries, context
  bundle, recommendation schema, and deferred execution rule.
- [Local Agent Runbook](local-agent-runbook.md): copyable commands for
  deterministic and Ollama-backed dry-run recommendations.

Current boundary:

- `agent cycle --dry-run` may package context and propose a command.
- A human or Codex session still decides whether to run that command.
- Non-dry-run agent execution is intentionally deferred.

## Portfolio Research

- [Portfolio Workflow](portfolio-workflow.md): static-weight portfolio
  definitions, candidate planning, and multi-symbol run artifacts.

## Planning And Status

- [Milestones](milestones.md): the full project milestone log.
- [Roadmap To Ready](roadmap-to-ready.md): what remains before the lab feels
  mature instead of merely useful.
- [Milestone 17 Local-Agent Advisor](milestone-17-local-agent-advisor.md):
  current local-agent advisor plan.

## Useful First Commands

Check environment health:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli doctor
```

Run an offline end-to-end smoke check:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli smoke-test --force
```

Refresh a session before asking for the next step:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli session refresh `
  --plan artifacts\research\<experiment>\research_plan.json
```

Ask for the next deterministic workflow step:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli research-plan next `
  --plan artifacts\research\<experiment>\research_plan.json
```

Run a safe local-agent dry run:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli agent cycle `
  --manifest artifacts\research\<experiment>\session_manifest.json `
  --dry-run
```

## Verified Offline E2E

The shortest currently verified no-network path is:

1. Run `doctor`.
2. Run `smoke-test --force`.
3. Refresh `artifacts\smoke-test\session_manifest.json` from
   `artifacts\smoke-test\research_plan.json`.
4. Run `research-plan next` on `artifacts\smoke-test\research_plan.json`.
5. Run deterministic `agent context`, `agent suggest`, and
   `agent cycle --dry-run` on `artifacts\smoke-test\session_manifest.json`.

Expected state:

- `doctor` reports `OK`.
- `smoke-test --force` reports `OK`.
- `research-plan next` recommends `run_trust`.
- `agent suggest` recommends `run_trust`.
- `agent cycle --dry-run` writes `artifacts\smoke-test\agent_cycle\` and
  stops before execution.

This proves the local wiring works. It does not produce research evidence
because the smoke workflow uses a tiny tracked CSV.
