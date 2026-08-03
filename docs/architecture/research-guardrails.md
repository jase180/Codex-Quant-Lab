# Research Guardrails

Report role: operating constraint.

This project is now useful enough that the main risk is no longer disconnected
ceremony. The main risk is adding strategy features in reaction to failed
backtests until the research process itself overfits history.

## Current Boundary

Do not add a new strategy primitive just because the latest experiment failed.

Before adding a new strategy feature, write a short research design note that
states:

- what failed in the previous evidence,
- why the new primitive should behave differently,
- the exact rule to test,
- the pass/fail thresholds,
- what would stop this branch,
- and which existing conclusion says not to repeat the old branch.

The first test should usually change one meaningful idea, not a broad grid of
new knobs.

## Strategy Feature Rule

New backtester or strategy-layer features should require all of these:

- A prewritten hypothesis.
- One primary comparison benchmark.
- Realistic costs.
- A small validation plan.
- A tracked result handoff, even if the result fails.

Avoid this loop:

```text
backtest failed
add a control
backtest failed
add another control
```

That loop can look like research while quietly fitting implementation choices
to known history.

## Agent Boundary

Freeze local-agent capability expansion for now.

Allowed:

- Let the agent read existing conclusions.
- Let the agent propose a next experiment under the current recommendation
  contract.
- Let deterministic workflow rules continue to recommend missing reports or
  conclusions.

Not allowed without a new explicit plan:

- Agent-controlled execution.
- Agent-authored strategy code.
- New model-provider features.
- New recommendation actions beyond the existing safe workflow-shaped actions.

The project needs several more human-reviewed experiment conclusions before
more agent autonomy is useful.

## Current Research Priority

The next technical priority is economic correctness, not strategy breadth.

Before partial exposure, trailing stops, drawdown stops, or broader risk-control
features, audit and document:

- whether `auto_adjust=True` adjusts open/high/low/close consistently,
- how dividends are reflected,
- how splits are reflected,
- whether buy-and-hold on adjusted prices represents the intended total-return
  comparison,
- and whether next-open fills on adjusted opens are internally coherent.

## Partial Exposure Boundary

Partial exposure is plausible, but it should not be implemented yet as a
reaction to the failed SMA long/cash and volatility-target branches.

If tested later, pre-register a narrow hypothesis first, such as:

```text
A fixed 50% exposure below the 200-day SMA will retain more return than cash
while still improving drawdown relative to buy-and-hold.
```

Set the return-retention, drawdown-improvement, and validation thresholds before
running the experiment. Do not begin with a broad exposure sweep.

## What To Preserve

Keep:

- `experiment_conclusion.md/json` as the canonical conclusion,
- `strategy.json` snapshots in run artifacts,
- `run_metadata.json` and data fingerprints,
- realistic cost assumptions,
- buy-and-hold benchmark comparisons,
- next-open fill tests,
- and negative result handoffs.

The lab should reward stopping a weak branch as much as finding a promising
one.
