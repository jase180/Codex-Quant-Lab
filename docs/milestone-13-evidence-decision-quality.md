# Milestone 13: Evidence And Decision Quality

## Status

Planned.

## Goal

Make it harder to overread a good-looking run, sweep, or batch.

Milestone 12 made input data easier to inspect and distrust. Milestone 13 should
do the same for interpretation. The lab should help a user separate:

```text
what happened,
what evidence supports the hypothesis,
what evidence contradicts it,
what is still uncertain,
and what should be tested next.
```

The goal is not to produce a magic score or automatic "best strategy" label. The
goal is to make research conclusions more honest.

## Current Starting Point

Working capabilities:

- `summarize-experiment` combines experiment records with linked run index rows.
- Existing summaries show most recent run, best and weakest excess return, run
  type breakdown, top evidence, weak evidence, and recent runs.
- `draft-decision` proposes conservative accept/reject/continue fields.
- `decide-experiment` records structured decisions.
- `summarize-sweep-guardrails` warns about fragile parameter sweeps.
- Portfolio experiment summaries exist for linked portfolio runs.
- Data trust reports now exist for strategy and portfolio baselines.

Main gaps:

- Evidence summaries are useful but still too metric-table heavy.
- There is no explicit evidence label such as `weak`, `mixed`, or `promising`.
- Train/test and walk-forward records are not interpreted as separate evidence
  classes in plain language.
- Decision drafts do not yet ask what would change the user's mind.
- Strategy and portfolio evidence summaries do not share enough interpretive
  vocabulary.

## Non-Goals

- No automatic promotion of a strategy.
- No live trading or paper-trading integration.
- No statistical proof claims.
- No hidden optimizer.
- No machine-learning model selection framework.
- No broad UI/dashboard work.
- No replacement of human judgment with a single score.

This milestone should stay deterministic, local, and humble.

## Deliverables

### 1. Evidence Label Heuristics

Status: delivered for internal strategy evidence labeling.

Add deterministic labels that summarize the shape of evidence without pretending
to prove anything.

Possible labels:

```text
no_evidence
weak
mixed
promising
rejected
```

Acceptance criteria:

- Labels are generated from linked run index rows.
- Labels consider benchmark excess return, validation run presence, weakest
  linked evidence, trade counts, and run type coverage.
- Label reasons are printed beside the label.
- Tests cover no evidence, benchmark underperformance, positive unvalidated
  evidence, positive validation, and mixed evidence.
- The docs clearly state that labels are heuristics, not proof.

### 2. Richer Strategy Evidence Summary

Status: delivered.

Upgrade `summarize-experiment` so it reads less like a leaderboard and more like
a research review.

Acceptance criteria:

- Adds an "Evidence Label" section.
- Adds "Supporting Evidence" and "Contradicting Evidence" sections.
- Separates exploratory runs, sweeps, train/test runs, and walk-forward runs.
- Calls out when the best run is not a validation run.
- Calls out when validation evidence disagrees with sweep evidence.
- Keeps existing tables because they remain useful for inspection.

### 3. Decision Draft Improvements

Status: planned.

Make `draft-decision` more useful for a junior researcher trying not to fool
themselves.

Acceptance criteria:

- Includes the evidence label and label reasons.
- Adds "what would change my mind?" prompts.
- Adds suggested next tests based on the evidence gap.
- Keeps the generated `decide-experiment` command copyable.
- Does not write to the registry until the user explicitly runs
  `decide-experiment`.

### 4. Portfolio Evidence Interpretation

Status: planned.

Apply the same interpretive vocabulary to portfolio experiment summaries.

Acceptance criteria:

- Portfolio summaries include a conservative evidence label.
- Labels consider benchmark excess return, drawdown, linked run count, and
  whether a data trust report exists for the baseline.
- Summaries call out when allocation variants are too few or too many.
- Summaries call out when the best allocation is only marginally better than the
  benchmark.

### 5. Guided Workflow Integration

Status: planned.

Teach guided plans to recommend evidence interpretation at the right time.

Acceptance criteria:

- `research-plan next` recommends evidence summary after trust and before
  decision.
- `portfolio-plan next` uses the richer portfolio evidence summary before
  compare/decision steps.
- README and workflow docs show the improved interpretation step.
- Recommendations remain conservative: summarize before deciding, and validate
  before accepting.

## Build Order

1. Evidence label model and tests.
2. Strategy evidence summary upgrade.
3. Decision draft improvements.
4. Portfolio evidence interpretation.
5. Guided workflow and docs updates.

## Design Notes

- Prefer plain strings and small dataclasses over a complicated scoring engine.
- Keep labels explainable. Every label should have reasons a user can read.
- Use benchmark excess return as a first filter, not the only filter.
- Treat validation runs as stronger evidence than sweep winners.
- Treat mixed or contradictory evidence as useful, not as failure of the tool.
- Keep "accept" rare. The default scientific posture is "continue" or "reject"
  until validation is stronger.
- Avoid adding new artifact formats unless the existing summary files cannot
  express the result.

## Exit Criteria

Milestone 13 is done when a user can turn linked strategy or portfolio runs into
an honest evidence summary, see why the lab considers the evidence weak, mixed,
promising, or rejected, and draft a decision that includes uncertainty plus the
next test that would actually change the conclusion.
