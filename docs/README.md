# Documentation Index

Start here when the docs folder feels too wide. The project keeps detailed
history and milestone notes, but day-to-day work should usually begin with the
current workflow docs and the latest experiment handoffs.

## Start Here

- [Getting Running](runbooks/getting-running.md): setup, `doctor`, smoke test, and first
  local commands.
- [Runbooks](runbooks/runbooks.md): command-oriented map for operating the lab.
- [Research Workflow](runbooks/research-workflow.md): end-to-end strategy research flow.
- [Strategy Schema](architecture/strategy-schema.md): strict v1 JSON strategy format,
  including risk controls.
- Conceptual strategy catalog: `data/strategy_catalog/*.json` and
  `data/strategy_catalog/README.md` describe broad strategy families before
  they become executable strategy files.
- [Core Backtest Assumption Audit](architecture/core-backtest-assumption-audit.md): current
  execution, data, benchmark, and realism assumptions.
- [Research Guardrails](architecture/research-guardrails.md): constraints that
  prevent feature churn and research overfitting.

## Current Research State

- [SPY Long/Cash Trend Experiment](experiments/spy-long-cash-trend-experiment.md): original
  SPY SMA long/cash result.
- [SPY Drawdown-Control Next Experiment](experiments/spy-drawdown-control-next-experiment.md):
  revised drawdown-control hypothesis and result.
- [SPY Volatility-Target Drawdown-Control Experiment](experiments/spy-vol-target-drawdown-control-experiment.md):
  latest risk-control result handoff.
- [SPY 2024 Adjusted-Price Audit](experiments/spy-2024-adjusted-price-audit.md):
  adjusted-price and manually supplied dividend-amount audit for the cached SPY
  data policy.
- [SPY Benchmark Entry-Timing Audit](experiments/spy-benchmark-entry-timing-audit.md):
  checks whether first-close buy-and-hold entry affects the SPY long/cash
  conclusion.
- [SPY Two-Status Conclusion Refresh](experiments/spy-two-status-conclusion-refresh.md):
  first real conclusion using separate research-system and strategy-hypothesis
  statuses.
- [SPY/TLT Static 60/40 Allocation Experiment](experiments/spy-tlt-static-60-40-allocation-experiment.md):
  portfolio diversification test; valid research system, rejected exact
  allocation hypothesis.
- [Risk-Control Strategy Layer](architecture/risk-control-strategy-layer.md): design boundary
  for strategy/backtester risk controls versus local-agent advice.
- [Research Guardrails](architecture/research-guardrails.md): current freeze on
  new strategy features and agent expansion without a prewritten hypothesis.
- [Roadmap To Ready](architecture/roadmap-to-ready.md): longer-range plan to make the lab
  feel mature.

## Local Agent

- [Local Agent](architecture/local-agent.md): advisor contract, context bundle, and safety
  boundary.
- [Local Agent Runbook](runbooks/local-agent-runbook.md): copyable deterministic and
  Ollama-backed commands.
- [Milestone 17 Local-Agent Advisor](milestones/milestone-17-local-agent-advisor.md):
  implementation plan and boundary.

Current boundary: agent commands can prepare context and recommend the next
experiment, but they do not take over execution without a human/Codex step.

## Workflow And Evidence Design

- [Experiment Conclusion Schema](architecture/experiment-conclusion-schema.md): conclusion
  JSON/Markdown shape for humans and agents.
- [Trustworthy Example Workflow](runbooks/trustworthy-example-workflow.md): skeptical
  example workflow.
- [Portfolio Workflow](portfolio/portfolio-workflow.md): static-weight portfolio research
  path.
- [Maintenance CLI Workflow Organization](architecture/maintenance-cli-workflow-organization.md):
  CLI organization cleanup notes.

## Milestones

- [Milestones](milestones/milestones.md): full project milestone log.
- [Milestone 3 Research Usability](milestones/milestone-3-research-usability.md)
- [Milestone 4 Validation Realism](milestones/milestone-4-validation-realism.md)
- [Milestone 5 Strategy Research Depth](milestones/milestone-5-strategy-research-depth.md)
- [Milestone 6 Research Trustworthiness](milestones/milestone-6-research-trustworthiness.md)
- [Milestone 7 Guided Research Workflow](milestones/milestone-7-guided-research-workflow.md)
- [Milestone 8 Portfolio Multi-Asset Research](milestones/milestone-8-portfolio-multi-asset-research.md)
- [Milestone 9 Portfolio Usability Research Loops](milestones/milestone-9-portfolio-usability-research-loops.md)
- [Milestone 10 Portfolio Research Depth](milestones/milestone-10-portfolio-research-depth.md)
- [Milestone 11 Research Automation Guardrails](milestones/milestone-11-research-automation-guardrails.md)
- [Milestone 12 Data Source Trust](milestones/milestone-12-data-source-trust.md)
- [Milestone 13 Evidence Decision Quality](milestones/milestone-13-evidence-decision-quality.md)
- [Milestone 14 Backtest Realism Robustness](milestones/milestone-14-backtest-realism-robustness.md)
- [Milestone 15 Default Workflow Canonical Conclusion](milestones/milestone-15-default-workflow-canonical-conclusion.md)
- [Milestone 15 State Review](milestones/milestone-15-state-review.md)
- [Milestone 16 Session Manifests](milestones/milestone-16-session-manifests.md)
- [Milestone 17 Local-Agent Advisor](milestones/milestone-17-local-agent-advisor.md)

## Reference

- [Strategy Schema JSON Schema](architecture/strategy-schema-v1.schema.json)
- [Example Run Report](architecture/example_run_report.md)
- [TODO](architecture/TODO.md)
