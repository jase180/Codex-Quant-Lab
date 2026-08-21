# Research Dataset Plans

This folder stores `research_dataset_plan.v1` records.

Dataset plans are not market data. They define the minimum raw material needed
to test a research mechanism honestly. Use them to decide what to acquire,
curate, or validate before adding strategy features.

Status meanings:

- `planned`: the dataset is specified but not yet built.
- `available`: the dataset exists locally and has passed the listed checks.
- `blocked`: the dataset cannot be built with current tools or accessible data.

Generated event-calendar files live in `data/event_calendars/`. Inspect them
before any backtest or return join with `quant-lab event-calendar inspect`.

Current plans:

- `calendar_rebalance_daily_proxy`: available generated event calendar for
  month-end and quarter-end proxy windows.
- `forced_index_membership_events`: planned event-membership dataset for index
  additions, deletions, and reconstitutions. It requires announcement dates,
  effective dates, source provenance, survivorship-safe prices, and liquidity
  proxies before any forced-flow strategy should be created.
- `tax_loss_selling_candidates`: planned survivorship-aware equity candidate
  dataset for late-year losers and early-year rebound windows. It requires
  delisting handling, size/liquidity buckets, spread proxies, deterministic tax
  windows, and pre-rebound year-to-date return screens.
