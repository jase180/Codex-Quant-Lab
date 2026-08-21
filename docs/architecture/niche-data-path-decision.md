# Niche Data Path Decision

Role: decision memo for choosing the next data-acquisition slice. This is not a
strategy result, a dataset, or a permission to backtest. It ranks the two
currently planned niche data paths so the next research step is deliberate.

Current candidate paths:

- `forced_index_membership_events`: event-level data for index additions,
  deletions, and reconstitutions.
- `tax_loss_selling_candidates`: survivorship-aware late-year loser and
  early-year rebound equity universe.

## Decision

Run a source-availability audit before building either dataset.

If an auditable free/exportable historical source exists for index membership
events with announcement dates and effective dates, pursue
`forced_index_membership_events` first. It has the cleaner mechanism, narrower
schema, and a concrete blocked opportunity thesis already waiting for data.

If that source does not exist, do not synthesize events from loose web lists.
Move to `tax_loss_selling_candidates` only if a survivorship-aware equity
universe with delisted symbols is available. A current-survivor-only yfinance
study should be treated as invalid for this mechanism, because it would likely
turn a data bias into fake alpha.

## Comparison

| Criterion | Forced index membership events | Tax-loss selling candidates |
| --- | --- | --- |
| Mechanism clarity | Strong. Additions, deletions, and reconstitutions have identifiable forced or benchmark-constrained participants. | Strong but less directly observed. Taxable selling is plausible, but daily bars cannot prove the seller motive. |
| Small-capital advantage | Medium to strong if effects concentrate in low-liquidity names around forced flows. | Strong if the universe includes smaller, less-liquid losers that large capital cannot trade efficiently. |
| Current engine fit | Medium. The first honest step is no-trade event diagnostics; executable strategies may need event-window entries later. | Medium. The engine can test fixed entry/exit windows after candidate construction, but the dataset is harder than the strategy. |
| Source feasibility | Uncertain. Official historical index constituent and announcement archives may be paid, incomplete, or hard to normalize. | Hard. Survivorship-aware historical equity universes with delisted symbols are often vendor data. |
| Main data-bias risk | Announcement/effective-date leakage and missing deleted/acquired names. | Survivorship bias, delisting handling, and post-selection return leakage. |
| Earliest honest diagnostic | Event-study returns around announcement and effective windows by event type and liquidity bucket. | Cohort returns for prespecified late-year loser buckets and early-year windows, split by size/liquidity. |
| Risk of fake alpha | Medium if event dates are scraped without provenance or announcement timing. | High if built from current surviving tickers or tuned loser thresholds. |
| Implementation burden | Moderate after a source is found; event schema is narrow. | High even after a source is found; requires security master, delistings, adjusted bars, and corporate-action flags. |

## What This Means

The practical ordering is:

1. Audit source availability for `forced_index_membership_events`.
2. If viable, build the smallest event calendar and run no-trade diagnostics
   before any executable strategy.
3. If blocked, audit survivorship-aware sources for
   `tax_loss_selling_candidates`.
4. If neither has acceptable source data, mark both paths blocked and return to
   mechanism discovery instead of forcing a weak backtest.

## Do Not Do Next

- Do not run a yfinance-only tax-loss study over current surviving symbols.
- Do not backtest forced-flow strategies from undocumented event lists.
- Do not add new indicators or strategy templates to compensate for missing
  niche data.
- Do not broaden the ETF indicator campaign just because these data paths are
  harder.

## Next Slice

Perform a source-availability audit for the two planned datasets. The output
should be a tracked source-audit note that answers:

- Which sources exist?
- Are they auditable and legally usable?
- Do they include the dates and identifiers required by the dataset plan?
- Are delisted/removed securities included where required?
- Is the dataset viable, blocked, or only suitable for a biased diagnostic?
