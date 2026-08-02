# Documentation Index

Start here when the docs folder feels too wide. The project keeps detailed
history and milestone notes, but day-to-day work should usually begin with the
current workflow docs and the latest experiment handoffs.

## Start Here

- [Getting Running](getting-running.md): setup, `doctor`, smoke test, and first
  local commands.
- [Runbooks](runbooks.md): command-oriented map for operating the lab.
- [Research Workflow](research-workflow.md): end-to-end strategy research flow.
- [Strategy Schema](strategy-schema.md): strict v1 JSON strategy format,
  including risk controls.
- [Core Backtest Assumption Audit](core-backtest-assumption-audit.md): current
  execution, data, benchmark, and realism assumptions.

## Current Research State

- [SPY Long/Cash Trend Experiment](spy-long-cash-trend-experiment.md): original
  SPY SMA long/cash result.
- [SPY Drawdown-Control Next Experiment](spy-drawdown-control-next-experiment.md):
  revised drawdown-control hypothesis and result.
- [SPY Volatility-Target Drawdown-Control Experiment](spy-vol-target-drawdown-control-experiment.md):
  latest risk-control result handoff.
- [Risk-Control Strategy Layer](risk-control-strategy-layer.md): design boundary
  for strategy/backtester risk controls versus local-agent advice.
- [Roadmap To Ready](roadmap-to-ready.md): longer-range plan to make the lab
  feel mature.

## Local Agent

- [Local Agent](local-agent.md): advisor contract, context bundle, and safety
  boundary.
- [Local Agent Runbook](local-agent-runbook.md): copyable deterministic and
  Ollama-backed commands.
- [Milestone 17 Local-Agent Advisor](milestone-17-local-agent-advisor.md):
  implementation plan and boundary.

Current boundary: agent commands can prepare context and recommend the next
experiment, but they do not take over execution without a human/Codex step.

## Workflow And Evidence Design

- [Experiment Conclusion Schema](experiment-conclusion-schema.md): conclusion
  JSON/Markdown shape for humans and agents.
- [Trustworthy Example Workflow](trustworthy-example-workflow.md): skeptical
  example workflow.
- [Portfolio Workflow](portfolio-workflow.md): static-weight portfolio research
  path.
- [Maintenance CLI Workflow Organization](maintenance-cli-workflow-organization.md):
  CLI organization cleanup notes.

## Milestones

- [Milestones](milestones.md): full project milestone log.
- [Milestone 3 Research Usability](milestone-3-research-usability.md)
- [Milestone 4 Validation Realism](milestone-4-validation-realism.md)
- [Milestone 5 Strategy Research Depth](milestone-5-strategy-research-depth.md)
- [Milestone 6 Research Trustworthiness](milestone-6-research-trustworthiness.md)
- [Milestone 7 Guided Research Workflow](milestone-7-guided-research-workflow.md)
- [Milestone 8 Portfolio Multi-Asset Research](milestone-8-portfolio-multi-asset-research.md)
- [Milestone 9 Portfolio Usability Research Loops](milestone-9-portfolio-usability-research-loops.md)
- [Milestone 10 Portfolio Research Depth](milestone-10-portfolio-research-depth.md)
- [Milestone 11 Research Automation Guardrails](milestone-11-research-automation-guardrails.md)
- [Milestone 12 Data Source Trust](milestone-12-data-source-trust.md)
- [Milestone 13 Evidence Decision Quality](milestone-13-evidence-decision-quality.md)
- [Milestone 14 Backtest Realism Robustness](milestone-14-backtest-realism-robustness.md)
- [Milestone 15 Default Workflow Canonical Conclusion](milestone-15-default-workflow-canonical-conclusion.md)
- [Milestone 15 State Review](milestone-15-state-review.md)
- [Milestone 16 Session Manifests](milestone-16-session-manifests.md)
- [Milestone 17 Local-Agent Advisor](milestone-17-local-agent-advisor.md)

## Reference

- [Strategy Schema JSON Schema](strategy-schema-v1.schema.json)
- [Example Run Report](example_run_report.md)
- [TODO](TODO.md)
