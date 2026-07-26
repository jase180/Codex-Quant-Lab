# Milestone 15: Default Workflow And Canonical Conclusion

## Status

Planned.

## Goal

Make the lab feel like one clear research workflow instead of a pile of useful
artifacts.

Milestone 14 added enough robustness machinery that the next bottleneck is not
"can the lab create evidence?" The next bottleneck is:

```text
Can a beginner, or future Codex, quickly understand what was learned, what
should not be repeated, and what the next useful test is?
```

This milestone should turn saved data and saved findings into saved knowledge.

## Fresh-Eyes Problem Statement

The project now has many real capabilities:

- runs,
- metadata,
- metrics,
- charts,
- research notes,
- data trust reports,
- evidence summaries,
- guardrail reports,
- robustness reports,
- experiment registry entries,
- guided plans,
- portfolio summaries,
- batch summaries.

That is useful, but it creates a human-facing problem: too many artifacts can
compete to explain the same experiment. The repo needs one obvious path and one
obvious conclusion artifact.

## Non-Goals

- No new strategy schema version.
- No new portfolio optimizer.
- No live trading or broker integration.
- No large UI/dashboard.
- No deletion of raw artifacts.
- No attempt to make conclusions automatic truth. Conclusions remain local,
  conservative research notes derived from linked evidence.

## Deliverables

### 1. One Default Workflow

Status: planned.

Rewrite the first user-facing path around one plain workflow:

```text
strategy -> one run -> main report -> conclusion -> next test
```

Advanced plans, registries, sweeps, robustness checks, and batches should still
exist, but they should be presented as optional escalation paths.

Acceptance criteria:

- README starts with the default path, not the full capability inventory.
- The default path explains which report to read first.
- Advanced tools are grouped after the default path.
- The docs clearly separate beginner workflow from advanced research workflow.

### 2. Canonical Experiment Conclusion

Status: planned.

Create one artifact that future humans and future Codex should read first.

Proposed files:

```text
experiment_conclusion.md
experiment_conclusion.json
```

The Markdown is the human source of truth. The JSON is optional but useful for
future automation.

The conclusion should answer:

- What was tested?
- What evidence was linked?
- What survived robustness checks?
- What failed or contradicted the idea?
- What should not be repeated?
- What is the next useful test?
- What would change the conclusion?

Acceptance criteria:

- Add a CLI command that writes the conclusion from an experiment id.
- The command reads linked runs from the experiment registry and research index.
- The conclusion references supporting artifacts instead of copying all details.
- The conclusion has a clear `Do Not Repeat` section.
- The conclusion has a clear `Next Useful Test` section.
- Future guided plan output points to this conclusion before decision steps.

### 3. Human-Facing Report Hierarchy

Status: planned.

Reduce noise by defining a report hierarchy instead of deleting artifacts.

Proposed hierarchy:

```text
1. Main source of truth
   experiment_conclusion.md

2. Supporting interpretation
   evidence_summary.md
   robustness reports
   data trust reports
   portfolio_summary.md

3. Raw audit artifacts
   run_metadata.json
   portfolio_metadata.json
   metrics.json
   trades.csv
   equity_curve.csv
   charts
```

Acceptance criteria:

- README and workflow docs name this hierarchy.
- Existing reports say whether they are main, supporting, or raw/audit.
- Overlapping guardrail/evidence/robustness docs are cross-linked or folded
  into the conclusion flow where practical.
- No raw artifact is removed unless a test proves it is redundant and unused.

### 4. Core Backtest Audit

Status: planned.

Before simplifying the user-facing workflow too far, audit the core simulation
assumptions that conclusions depend on.

Audit topics:

- adjusted prices,
- dividends and splits,
- next-open fills,
- cash after exits,
- benchmark date alignment,
- indicator warm-up behavior,
- final-bar signal handling,
- transaction cost application.

Acceptance criteria:

- Write an audit doc for the current assumptions.
- Add or tighten tests before changing behavior.
- Identify which assumptions are acceptable for the small lab and which should
  become future milestones.
- Do not hide uncertainty; name it in the default workflow.

### 5. One Complete Real Experiment

Status: planned.

Run one boring, complete experiment end to end and use it to prune or demote
unhelpful workflow pieces.

Proposed experiment:

```text
SPY long/cash trend strategy
daily data
buy-and-hold benchmark
retail-liquid costs
one baseline
one small sweep or controlled variant
robustness checks only if the first evidence justifies them
canonical conclusion
```

Acceptance criteria:

- The experiment starts from the default workflow.
- The experiment produces a conclusion artifact.
- The conclusion says what not to repeat and what to test next.
- Any artifact that did not help reach the conclusion is either demoted in docs
  or marked as raw/audit-only.
- The example becomes the recommended walkthrough for new users.

### 6. Session Manifest, After The Conclusion Shape Is Clear

Status: planned.

Keep session manifests in Milestone 15, but do them after the conclusion
artifact has a stable shape. The manifest should organize the workflow; it
should not become one more competing explanation.

Acceptance criteria:

- A session manifest records plan, commands, key artifacts, conclusion path,
  decisions, and outstanding next steps.
- `quant-lab session status` or equivalent prints one-line orientation.
- `quant-lab session replay-plan` or equivalent prints intended commands
  without rerunning them.
- Missing/orphaned artifact checks point back to the canonical conclusion.

## Build Order

1. Plan and document the default workflow and report hierarchy.
2. Add the canonical conclusion artifact and CLI command.
3. Teach guided plans to recommend conclusions before decisions.
4. Audit core backtest assumptions and fill test gaps.
5. Run the complete SPY long/cash experiment.
6. Add session manifests around the stable workflow.
7. Rewrite README around the default path.

## Design Notes

- Optimize for a junior researcher returning after a week away.
- Prefer one clear conclusion over more parallel reports.
- Treat Codex as a future reader: it should know what to read first.
- Raw data stays available, but the default workflow should not require reading
  every raw file.
- The conclusion should be conservative, falsifiable, and explicit about what
  would change it.

## Exit Criteria

Milestone 15 is done when a user can run or inspect one experiment and answer:

```text
What did we learn?
What should we not repeat?
What should we test next?
Which file should I read first next time?
```

without needing to understand every artifact the lab can produce.
