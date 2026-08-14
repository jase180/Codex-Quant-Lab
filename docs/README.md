# Documentation Index

Start here when the docs folder feels too wide. The project keeps detailed
history and milestone notes, but day-to-day work should usually begin with the
current workflow docs and the latest experiment handoffs.

## Start Here

- [Getting Running](runbooks/getting-running.md): setup, `doctor`, smoke test, and first
  local commands.
- [Runbooks](runbooks/runbooks.md): command-oriented map for operating the lab.
- [Research Workflow](runbooks/research-workflow.md): end-to-end strategy research flow.
- [Campaign Runbook](runbooks/campaign-runbook.md): bounded campaign commands,
  state files, and final reports.
- [Strategy Schema](architecture/strategy-schema.md): strict v1 JSON strategy format,
  including risk controls.
- Conceptual strategy catalog: `data/strategy_catalog/*.json` and
  `data/strategy_catalog/README.md` describe broad strategy families before
  they become executable strategy files.
- Research mechanism library: `data/research_mechanisms/*.json` and
  `data/research_mechanisms/README.md` describe market-structure raw material,
  forced actors, data requirements, capacity/friction claims, and falsification
  tests before an idea becomes an opportunity thesis.
- Conceptual opportunity catalog: `data/opportunity_catalog/*.json` and
  `data/opportunity_catalog/README.md` describe market niches, forced actors,
  capacity/friction claims, and falsification tests before strategy selection.
- Research universes: `data/universes/*.json` and `data/universes/README.md`
  define the allowed symbol sets for campaigns and multi-asset experiments.
- Extended ETF campaign config:
  `data/campaigns/liquid_etf_extended_discovery_campaign.json` uses
  `data/universes/liquid_etf_extended.json` for broader bounded discovery after
  the core ETF loop is behaving sensibly.
- Experiment template catalog: `data/experiment_template_catalog/*.json` and
  `data/parameter_neighborhoods/*.json` describe bounded experiment families and
  small prespecified parameter sets before candidate generation.
- [Core Backtest Assumption Audit](architecture/core-backtest-assumption-audit.md): current
  execution, data, benchmark, and realism assumptions.
- [Research Guardrails](architecture/research-guardrails.md): constraints that
  prevent feature churn and research overfitting.

## Current Research State

- [Project State For Review](../PROJECT_STATE_FOR_REVIEW.md): current repo shape,
  workflow, architecture, strengths/weaknesses, and reviewer questions.
- [SPY Long/Cash Trend Experiment](experiments/spy-long-cash-trend-experiment.md): original
  SPY SMA long/cash result.
- [SPY Drawdown-Control Next Experiment](experiments/spy-drawdown-control-next-experiment.md):
  revised drawdown-control hypothesis and result.
- [SPY Volatility-Target Drawdown-Control Experiment](experiments/spy-vol-target-drawdown-control-experiment.md):
  latest risk-control result handoff.
- [SPY Trend-Defense Campaign Closeout](experiments/spy-trend-defense-campaign-closeout.md):
  bounded campaign result; valid research workflow, exhausted current SPY
  trend-defense candidate space.
- [SPY Opportunity Expansion Campaign Closeout](experiments/spy-opportunity-expansion-campaign-closeout.md):
  bounded RSI pullback and breakout campaign result; valid workflow, but SPY
  single-asset timing still failed return-retention objectives.
- `data/campaigns/spy_opportunity_expansion_campaign.json`: small campaign
  config for testing bounded RSI pullback and breakout candidates after the SPY
  trend-defense closeout.
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
- [QQQ/SPY/TLT Top-1 Momentum Experiment](experiments/qqq-spy-tlt-top1-momentum-experiment.md):
  multi-asset relative-strength rotation test; QQQ provenance caveat was cleared
  by cache refresh and rerun, but the strategy hypothesis remains rejected.
- [SPY Rolling-Low Reversion Experiment](experiments/spy-rolling-low-reversion-experiment.md):
  statistical-reversion result; valid research system, rejected executable
  new-low variant.
- [EEM SMA 200 ETF Campaign Probe](experiments/eem-sma-200-etf-campaign-probe.md):
  first liquid ETF universe campaign probe; valid system, partially supported
  strategy due failed robustness, weakened thesis.
- [EEM RSI Pullback ETF Shortlist Probe](experiments/eem-rsi-pullback-etf-shortlist-probe.md):
  first actual ETF campaign cycle after shortlist ranking; valid system,
  partially supported selected validation, failed robustness.
- [ETF Campaign Branch-Filter Probe](experiments/etf-campaign-branch-filter-probe.md):
  replay proving weakened campaign branches are carried forward as
  opportunity/template exclusions instead of merely blocking exact experiment
  titles.
- [Liquid ETF Three-Cycle Campaign Probe](experiments/liquid-etf-three-cycle-campaign-probe.md):
  bounded loop proof after explicit strategy-template metadata; campaign
  execution works, but candidate ranking remains too symbol-sticky.
- [Liquid ETF Diversity-Ranking Probe](experiments/liquid-etf-diversity-ranking-probe.md):
  repeated-symbol ranking penalty proof; the loop moved from `EEM -> EEM -> EEM`
  to `EEM -> EFA -> GLD` while preserving branch guardrails.
- [Liquid ETF Extended Universe Expansion](experiments/liquid-etf-extended-universe-expansion.md):
  added the 63-symbol extended ETF universe, fetched missing cache/provenance
  files, and verified the extended campaign candidate menu.
- [Liquid ETF Extended Campaign Closeout](experiments/liquid-etf-extended-campaign-closeout.md):
  first 5-cycle extended campaign stopped after four experiments with true
  `SEARCH_SPACE_EXHAUSTED`; the bottleneck is now thesis/template breadth, not
  ETF symbol count.
- [ETF Flow Breakout Probe](experiments/etf-flow-breakout-probe.md):
  first probe after adding the ETF-flow thesis/template branch; valid research
  system, partially supported strategy, weakened ETF-flow breakout branch.
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
- [Milestone 18 Campaign Orchestration](milestones/milestone-18-campaign-orchestration.md):
  bounded multi-cycle campaign roadmap and current implementation boundary.
- [Milestone 19 Niche Discovery Layer](milestones/milestone-19-niche-discovery-layer.md):
  planned opportunity-thesis layer for small-capacity market niches.
- [Milestone 20 Candidate Menu Discovery](milestones/milestone-20-candidate-menu-discovery.md):
  planned candidate-generator layer so providers choose among bounded
  experiments instead of inventing them.

Current boundary: agent commands can prepare context and recommend the next
experiment, but they do not take over execution without a human/Codex step.

Campaign boundary: `campaign run --loop` can execute bounded deterministic
campaigns through the existing `experiment run-default` workflow, read canonical
conclusion JSON, update campaign memory, and write `final_report.md/json`.
`campaign run` now generates a deterministic candidate menu before provider
selection, so deterministic/Ollama/Codex-style providers choose from candidate
IDs instead of inventing experiments. `campaign candidates` writes that menu for
inspection, including explicit `SEARCH_SPACE_EXHAUSTED` status when the bounded
search space is empty. `campaign choose-candidate` exposes the same provider
choice gate without execution. Ollama can produce strict candidate-choice JSON
with saved attempt artifacts, one retry, deterministic fallback, and explicit
`--execute-model-proposal` gating. Codex is currently a handoff provider that
writes the same context/prompt artifacts and stops for human review. The
controller continues to own validation, budgets, execution, and stopping.

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
- [Milestone 18 Campaign Orchestration](milestones/milestone-18-campaign-orchestration.md)
- [Milestone 19 Niche Discovery Layer](milestones/milestone-19-niche-discovery-layer.md)
- [Milestone 20 Candidate Menu Discovery](milestones/milestone-20-candidate-menu-discovery.md)

## Reference

- [Strategy Schema JSON Schema](architecture/strategy-schema-v1.schema.json)
- [Example Run Report](architecture/example_run_report.md)
- [TODO](architecture/TODO.md)
