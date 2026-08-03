# SPY Two-Status Conclusion Refresh

Report role: experiment conclusion handoff.

This note records the first real SPY experiment conclusion regenerated after
the project separated research-system validity from strategy-hypothesis
outcome.

## Source Experiment

- Experiment id: `EXP-003`
- Experiment directory:
  `artifacts/research/spy_200_sma_long_cash_default_benchmark`
- Canonical conclusion:
  `artifacts/research/spy_200_sma_long_cash_default_benchmark/experiment_conclusion.md`
- Plan:
  `artifacts/research/spy_200_sma_long_cash_default_benchmark/research_plan.json`

## Prespecified Objective Added

The local research plan now records:

- Intended benefit: lower drawdown with acceptable return retention.
- Benchmark: `buy-and-hold`.
- Primary metric: `max_drawdown`.
- Minimum acceptable performance: retain at least 80% of buy-and-hold CAGR,
  reduce max drawdown by at least 25% relative, and remain acceptable after
  retail-liquid costs.
- Trade-off: may underperform SPY total return during strong bull markets.

Success criteria:

| criterion | metric | comparison | threshold |
| --- | --- | --- | ---: |
| `return_retention` | `cagr` | strategy / benchmark | `>= 0.8` |
| `drawdown_reduction` | `max_drawdown` | relative reduction vs benchmark | `>= 0.25` |

## Refreshed Conclusion

The refreshed `experiment_conclusion.md/json` now reports:

```text
Research-system status: valid
Strategy-hypothesis status: rejected
```

The strategy status is evaluated from the train/test selected validation run:

| criterion | result | observed |
| --- | --- | ---: |
| `return_retention` | fail | `0.4884` |
| `drawdown_reduction` | fail | `0.1683` |

Interpretation:

The repo successfully measured the experiment, preserved the relevant workflow
checks, and produced a valid negative result. The strategy failed its
prespecified investment objective. That is not a research-system failure.

## Implementation Note

Older `research_index.jsonl` rows do not store `benchmark_cagr`. The conclusion
builder now derives benchmark CAGR from `benchmark_total_return` plus the saved
run metadata row count when needed. This lets older saved runs evaluate CAGR
retention criteria without rerunning the whole workflow.
