# Runbooks

This page is the short map for operating the lab. Use it when you know what
you want to do, but not which document has the commands.

## Start Here

- [Documentation Index](../README.md): docs organized by task, current research
  state, local-agent work, milestones, and reference material.
- [Getting Running](getting-running.md): install checks, dependency health,
  `doctor`, and the offline smoke test.
- [Research Workflow](research-workflow.md): the default one-strategy research
  loop from plan creation through conclusion.
- [Campaign Runbook](campaign-runbook.md): bounded deterministic campaign
  execution, resume commands, state files, and final report.
- [Trustworthy Example Workflow](trustworthy-example-workflow.md): a copyable
  skeptical example that keeps one experiment narrow.
- [Research Guardrails](../architecture/research-guardrails.md): when not to
  add new strategy features or agent capabilities.

## Local-Agent Advisor

- [Local Agent](../architecture/local-agent.md): the advisor contract, boundaries, context
  bundle, recommendation schema, and deferred execution rule.
- [Local Agent Runbook](local-agent-runbook.md): copyable commands for
  deterministic and Ollama-backed dry-run recommendations.

Current boundary:

- `agent cycle --dry-run` may package context and propose a command.
- A human or Codex session still decides whether to run that command.
- Non-dry-run agent execution is intentionally deferred.

## Portfolio Research

- [Portfolio Workflow](../portfolio/portfolio-workflow.md): static-weight portfolio
  definitions, candidate planning, and multi-symbol run artifacts.

## Planning And Status

- [Milestones](../milestones/milestones.md): the full project milestone log.
- [Roadmap To Ready](../architecture/roadmap-to-ready.md): what remains before the lab feels
  mature instead of merely useful.
- [Milestone 17 Local-Agent Advisor](../milestones/milestone-17-local-agent-advisor.md):
  current local-agent advisor plan.

## Current SPY Research Handoffs

- [SPY Long/Cash Trend Experiment](../experiments/spy-long-cash-trend-experiment.md):
  original 200-day SMA long/cash result.
- [SPY Drawdown-Control Next Experiment](../experiments/spy-drawdown-control-next-experiment.md):
  revised drawdown-control test and rejection.
- [SPY Volatility-Target Drawdown-Control Experiment](../experiments/spy-vol-target-drawdown-control-experiment.md):
  latest risk-control test; drawdown improved, return retention failed.
- [SPY 2024 Adjusted-Price Audit](../experiments/spy-2024-adjusted-price-audit.md):
  audit of 2024 SPY adjusted OHLC behavior and manually supplied dividend
  amounts.
- [SPY Benchmark Entry-Timing Audit](../experiments/spy-benchmark-entry-timing-audit.md):
  audit showing the SPY long/cash rejection survives a next-open benchmark
  entry check.

## Useful First Commands

Check environment health:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli doctor
```

Run an offline end-to-end smoke check:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli smoke-test --force
```

Include the deterministic local-agent dry-run check:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli smoke-test --force --agent-cycle
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

Ask for a conceptual next strategy idea before creating executable JSON:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli ideas suggest
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
2. Run `smoke-test --force --agent-cycle`.

Expected state:

- `doctor` reports `OK`.
- `smoke-test --force --agent-cycle` reports `OK`.
- The baseline smoke workflow writes `artifacts\smoke-test\`.
- The deterministic agent cycle recommends `run_trust`.
- The deterministic agent cycle writes `artifacts\smoke-test\agent_cycle\`
  and stops before execution.

This proves the local wiring works. It does not produce research evidence
because the smoke workflow uses a tiny tracked CSV.
