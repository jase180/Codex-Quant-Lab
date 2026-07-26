# Roadmap To A Pretty Ready Quant Lab

This roadmap answers a different question than the early milestone docs.

The first eleven milestones proved that Codex-Quant-Lab can run local research
loops. The next question is:

```text
What has to exist before this feels like a dependable small quant lab instead
of a capable proof of concept?
```

The answer is not "more indicators" or "more automation" by itself. A useful
research lab needs trust, interpretation, realistic assumptions, repeatable
workflows, and enough polish that a user can return after a week and understand
what happened.

## Definition Of Pretty Ready

For this project, "pretty ready" means:

- A careful beginner can use the CLI without editing Python code.
- A saved result explains its data, assumptions, parameters, costs, and evidence.
- The lab warns loudly about weak data, weak samples, fragile sweeps, and
  benchmark underperformance.
- Strategy and portfolio research share the same mental model.
- Common research loops are documented with copyable commands.
- A local agent can recommend the next experiment from saved artifacts without
  taking over the repo.
- The codebase is still small enough for Codex and a junior engineer to extend.
- Tests cover the important behavior paths, not just happy-path demos.

It does **not** mean:

- live trading,
- broker integration,
- institutional-grade data,
- intraday simulation,
- options/futures support,
- a hosted web app,
- statistical proof that a strategy works,
- or an autonomous code-editing research bot.

Those can come later, but they should not be smuggled into the local research
foundation.

## Phase 1: Trust The Inputs

### Milestone 12: Data Source Trust

Status: planned.

Purpose: make data provenance, fingerprints, and quality warnings easy to
inspect before trusting strategy or portfolio results.

Deliverables:

- `show-data-source` for cached CSV plus provenance inspection.
- Single-run trust reports from `run_metadata.json`.
- Portfolio data trust reports from `portfolio_metadata.json`.
- Guided plan recommendations for trust checks.
- Cache inventory for duplicate or missing-provenance files.

Exit criteria:

- A user can explain every local CSV used by a result and see whether current
  files still match saved fingerprints.

Why this comes first:

- Bad or unexplained data can invalidate everything downstream. This is the most
  important gap before adding deeper research features.

## Phase 2: Trust The Interpretation

### Milestone 13: Evidence And Decision Quality

Status: complete.

Purpose: make it harder to overread a good-looking run or sweep.

Deliverables:

- Strategy and portfolio evidence labels. Delivered.
- Supporting and contradicting evidence sections. Delivered.
- Side-by-side train/test/walk-forward interpretation. Delivered.
- Explicit "what would change my mind?" decision prompts. Delivered.
- Better result labels: weak, mixed, promising, rejected, and no evidence.
  Delivered.

Exit criteria:

- A user can turn a collection of runs into an honest research conclusion without
  pretending the best backtest is proof.

Why this follows data trust:

- Once inputs are inspectable, the next highest risk is interpretation. The lab
  should teach skepticism as part of the workflow.

### Milestone 14: Backtest Realism And Robustness

Status: completed.

Purpose: challenge promising ideas with controlled perturbations before calling
them sturdy.

Deliverables:

- Strategy cost sensitivity.
- Strategy date-range sensitivity.
- Benchmark substitution checks.
- Parameter-neighborhood robustness.
- Portfolio robustness notes.
- Guided workflow integration for robustness checks.

Exit criteria:

- A user can take a promising idea, run a small set of robustness checks, and
  see where it survived or failed.

Why this matters:

- Milestone 13 made interpretation more honest. The next confidence gap is
  whether that interpretation survives stricter costs, different dates, and
  benchmark changes.

## Phase 3: Improve Research Breadth Without Black Boxes

### Milestone 15: Default Workflow And Canonical Conclusion

Status: substantially delivered.

Purpose: make the lab feel like one clear research workflow instead of a pile of
useful artifacts.

Deliverables:

- One documented default path: strategy, run, main report, conclusion, next
  test.
- A canonical experiment conclusion artifact that records what was learned,
  what not to repeat, and what to test next.
- Agent-readable conclusion fields plus context instructions for local agents
  that help critique conclusions or suggest the next research cycle.
- A human-facing report hierarchy that separates the main source of truth from
  supporting and raw audit artifacts.
- A core backtest audit covering adjusted prices, fills, cash, benchmark
  alignment, indicator warm-up, and costs.
- One complete real SPY long/cash experiment.
- Session manifests deferred to Milestone 16 after the conclusion shape became
  stable.

Exit criteria:

- A user can stop for a week, come back, read one conclusion artifact, and
  understand what the research question was, what evidence exists, what should
  not be repeated, and what remains.

Why this came before session manifests:

- The project could already produce many useful files. The conclusion had to
  become the source of truth before a session manifest could safely organize the
  surrounding workflow.

### Milestone 16: Session Manifests And Workflow Resume

Status: complete.

Purpose: make one research session easy to inspect, resume, and replay without
turning the session record into another conclusion report.

Deliverables:

- A documented session manifest schema. Delivered.
- `session_manifest.json` and `session_manifest.md` formatters. Delivered.
- `quant-lab session status` for one-line orientation. Delivered.
- `quant-lab session replay-plan` for intended commands without rerunning them.
  Delivered.
- `quant-lab session refresh` to rebuild pointers from known research
  artifacts. Delivered.
- Stale or missing artifact warnings that point back to the canonical
  conclusion. Delivered.

Exit criteria:

- A user can return after a week and find the current conclusion, decision,
  plan, and key artifacts from one manifest.

Why this comes next:

- The lab has enough real workflow now to know what belongs in a session record.
  The manifest should preserve continuity before the strategy language becomes
  more expressive.

### Milestone 17: Local Agent Advisor

Status: in progress.

Purpose: let a local agent read the current research state, recommend the next
experiment or analysis step, explain why, and stop.

Deliverables:

- `quant-lab doctor` for dependency, import, artifact-directory, and data-cache
  checks.
  Delivered.
- `quant-lab smoke-test` for an offline end-to-end wiring check that writes a
  plan, baseline run, and session manifest.
  Delivered.
- A local-agent context contract rooted in `session_manifest.json`.
  Delivered.
- A strict `agent_recommendation.v1` schema.
  Delivered.
- Deterministic `quant-lab agent suggest` that works without a model.
  Delivered.
- A local OpenAI-compatible model adapter for Ollama, LM Studio, llama.cpp, or
  similar endpoints.
  Delivered.
- Human-gated `agent cycle --dry-run` with stop-before-execution artifacts.
  Delivered.
- Future non-dry-run `agent cycle` with explicit step limits, stop conditions,
  and no source-code edits.
  Deferred until explicit human review.

Exit criteria:

- A local agent can recommend the next experiment from saved artifacts while
  leaving a validated recommendation artifact and stopping before unapproved
  action.

Why this comes next:

- The lab now has durable plans, conclusions, run metadata, and session
  manifests. That is enough structure for a useful research advisor. The next
  risk is not lack of indicators; it is making sure the advisor is bounded,
  inspectable, and honest about weak evidence.

### Milestone 18: Strategy Language V2

Status: proposed.

Purpose: expand what strategies can express while preserving strict validation
and no-lookahead behavior.

Deliverables:

- A versioned `strategy_schema.v2`.
- Position-state-aware rules, such as "only enter if flat" or "only exit if
  long."
- Risk controls such as stop loss, trailing stop, take profit, max holding days,
  and cooldown.
- More indicator primitives only where they unlock common research questions.
- Migration docs from v1 to v2.

Exit criteria:

- A user can express common daily long-only systems without writing Python, and
  the schema still rejects ambiguous or lookahead-prone ideas.

Why this waits:

- More expressive strategies are useful, but they become dangerous if the lab
  does not first define the agent boundary that will recommend future research
  steps.

### Milestone 19: Portfolio Realism

Status: proposed.

Purpose: make portfolio tests more realistic without turning into a professional
order-management simulator.

Deliverables:

- Rebalance drift thresholds.
- Symbol-level cash drag and uninvested cash reporting.
- Allocation constraints and min/max weights in candidate generation.
- Optional simple volatility targeting or inverse-volatility weighting.
- Better portfolio benchmark sets, such as static blended benchmarks.

Exit criteria:

- Portfolio tests reflect common allocation research questions and clearly show
  when implementation assumptions drive the result.

Why this comes after strategy language:

- Strategy and portfolio logic should mature together, but portfolio realism can
  stay simpler until the agent and strategy-contract foundations are stronger.

## Phase 4: Make It Comfortable To Use

### Milestone 20: CLI UX And Configuration Polish

Status: proposed.

Purpose: make normal use less verbose without hiding important assumptions.

Deliverables:

- Project-level config file for default artifact directories, cost preset,
  benchmark, and cache path.
- Clearer command grouping and help text.
- Better error messages for common beginner mistakes.
- README quickstart that matches the current command surface.

Exit criteria:

- A new user can install, run the sample workflow, diagnose common setup issues,
  and understand failures without reading source code.

Why this waits:

- UX polish should stabilize around the real workflows, not around early command
  shapes that may still change.

### Milestone 21: Example Research Library

Status: proposed.

Purpose: provide high-quality example projects that show how to use the lab
honestly.

Deliverables:

- One complete strategy research example.
- One complete portfolio research example.
- One intentionally failed/rejected idea.
- One data-quality warning example.
- Markdown reports committed under docs, with generated artifacts kept ignored.

Exit criteria:

- A learner can follow complete examples and see what honest interpretation
  looks like when evidence is weak, mixed, or contradicted.

Why this matters:

- Examples teach the intended taste of the tool better than feature lists.

## Phase 5: Hardening

### Milestone 22: Test, Packaging, And Maintenance Hardening

Status: proposed.

Purpose: make the codebase boring in the best way.

Deliverables:

- A smaller set of stable internal APIs for run execution, artifact writing,
  trust reporting, and workflow planning.
- Test helpers/factories that reduce duplicated fixture setup.
- Basic CI instructions or GitHub Actions workflow.
- Dependency/environment docs for Windows, WSL, and local virtualenv use.
- A maintenance checklist for adding a new command or artifact type.

Exit criteria:

- The project can accept new features without the codebase becoming difficult
  for Codex or the owner to reason about.

Why this is a milestone, not a chore:

- A local quant lab grows many small commands and artifact files. Without
  maintenance structure, the project will become powerful but unpleasant.

## Pretty Ready Exit Criteria

The project is "pretty ready" after Milestone 22 if:

- A full sample strategy workflow can be run from fresh setup docs.
- A full sample portfolio workflow can be run from fresh setup docs.
- Both workflows produce data trust, evidence, benchmark, and decision artifacts.
- A saved result can be inspected, compared, verified, and summarized from the
  CLI.
- The user can generate variations and batches without hidden optimization.
- A local agent can recommend bounded next experiments from saved state.
- Common false-confidence traps are called out in reports.
- The codebase has clear module boundaries and a passing test suite.

At that point, the lab is still not a trading platform. But it is no longer just
a proof of concept. It is a small, honest, local research environment.

## Recommended Build Sequence

1. Milestones 15 and 16 are complete enough to make saved research readable and
   resumable.
2. Build Milestone 17 so local-agent recommendations have a strict contract.
3. Reassess whether Strategy Language V2 or Portfolio Realism is more urgent.
4. Build Milestones 18 and 19.
5. Polish setup, examples, and maintenance through Milestones 20 through 22.

This order keeps the project honest: first trust inputs, then trust
interpretation, then challenge robustness, then broaden the research surface,
then polish.
