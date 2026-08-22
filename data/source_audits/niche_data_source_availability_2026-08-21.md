# Niche Data Source Availability Audit

Role: source-availability audit for the two planned niche dataset paths:

- `forced_index_membership_events`
- `tax_loss_selling_candidates`

Audit date: 2026-08-21.

This document does not build a dataset and does not approve a strategy. It asks
whether the raw source material is good enough to justify the next data slice.

## Verdict

Pursue a limited `forced_index_membership_events` pilot first, but only as a
source-provenance and no-trade event-study dataset.

Do not pursue `tax_loss_selling_candidates` with the current free/cached data.
An honest tax-loss study needs survivorship-aware historical equity membership,
delisted securities, delisting handling, corporate-action fields, and stable
security identifiers. Current yfinance-style survivor data is not enough.

## Forced Index Membership Events

Status: `viable_pilot`.

Best near-term path: create a small S&P index-change pilot from official S&P
Global press releases and cross-check against one secondary source. The pilot
should preserve announcement/published date, effective date, index name, action,
symbol, company name, and source URL per row.

Observed sources:

- S&P Global press releases publish recent index changes with effective dates,
  index names, action, company, ticker, and sector. Example recent release:
  `https://press.spglobal.com/2026-08-13-Reddit-Set-to-Join-S-P-500-and-Sun-Communities-to-Join-S-P-MidCap-400`.
- Older S&P Global press releases also exist in searchable form, including
  2021 and 2023 examples with effective-date tables.
- `https://github.com/shawnlinxl/snp-history` provides S&P 500 additions and
  removals from 2000-2016 with announcement and implementation dates, but its
  README warns that dates can be inaccurate, pre-2017 data has not been
  verified, and changes before 2000 are missing.
- Norgate documents paid historical index constituent coverage for S&P, Russell,
  Nasdaq, Dow, NYSE, AU, and CA indices, including S&P 500 from March 1957 and
  Russell 3000 from July 1990:
  `https://norgatedata.com/data-content-tables.php`.

What is good:

- The mechanism is concrete: index funds, benchmark-aware managers, and other
  index-linked products are plausible forced or constrained actors.
- Announcement and effective dates are visible in official recent S&P releases,
  which makes information timing auditable for a bounded pilot.
- A pilot can start as a no-trade event study before any backtester feature work.

What is not solved:

- A complete official bulk archive was not identified in this audit.
- Public press-release search may have coverage gaps and parsing edge cases.
- Secondary GitHub data is useful for comparison, not authoritative enough by
  itself.
- Norgate looks stronger for historical constituents, but it is a paid/vendor
  path and may still need separate announcement-date handling.
- Daily bars cannot model rebalance-close auction pressure or intraday liquidity.

Minimum acceptable next pilot:

1. Select one fixed date range before looking at returns, such as 2021-2026.
2. Use official S&P Global press releases as the primary source.
3. Store one source URL and source-published date per event row.
4. Keep additions and deletions separate.
5. Run only no-trade diagnostics first.
6. Mark the dataset `viable_pilot`, not `available`, until completeness checks
   pass.

Do not:

- Scrape undocumented web tables without row-level provenance.
- Merge S&P 500, MidCap 400, and SmallCap 600 without separate cohort labels.
- Treat implementation/effective date as the first tradable information date
  when announcement timing is missing.

## Tax-Loss Selling Candidates

Status: `vendor_required`.

Best near-term path: do not build this dataset until the project has access to a
survivorship-aware equity universe. If a vendor/source is acquired, the first
slice should be a data quality audit, not a strategy.

Observed sources:

- CRSP/WRDS exposes identifying information, price/quote data, distribution
  history, and delisting fields such as delisting code, delisting price, and
  delisting return:
  `https://wrds-www.wharton.upenn.edu/demo/crsp/form/`.
- QuantConnect lists a US Equity Security Master with historical
  mapping/delisting and split/dividend/survivorship-bias-free equity
  backtesting; on-premise download is listed as paid:
  `https://www.quantconnect.com/data/quantconnect-us-equity-security-master`.
- Norgate documents US delisted stocks and historical index constituents under
  paid subscription tiers:
  `https://norgatedata.com/data-content-tables.php`.
- HistoricalData.net states that delisted companies keep full frozen history,
  ticker reuse is handled separately, and split/dividend-adjusted columns are
  carried alongside unadjusted data:
  `https://historicaldata.net/methodology.html`.
- A public GitHub pipeline at `https://github.com/tenicho/data-cleaning`
  describes a survivorship-clean US equity panel built from vendor data
  including delisted listings, stable identifiers, and point-in-time S&P 500
  membership. This is useful as a reference design, but it is not a substitute
  for validating local data rights and reproducibility.

What is good:

- The mechanism fits the project direction well: small-capacity, annoying data,
  tax-calendar behavior, and liquidity constraints.
- Several credible sources or reference designs show what an honest dataset
  should contain.

What is not solved:

- The current repo does not have a survivorship-aware equity universe.
- Current cached ETF/equity data is not enough because it misses delisted names
  and point-in-time universe membership.
- Free current-symbol data would likely bias the exact branch this mechanism
  depends on most.
- The project needs delisting classification, security identifiers, corporate
  action flags, and size/liquidity buckets before hypothesis testing.

Minimum acceptable next pilot:

1. Acquire or export a survivorship-aware source with delisted securities.
2. Validate identifiers, listing windows, delisting fields, adjusted/unadjusted
   bars, volume, and corporate actions.
3. Define tax-calendar windows and loser thresholds before inspecting rebound
   returns.
4. Run no-trade cohort diagnostics before any executable strategy.

Do not:

- Use current S&P 500, Russell, or Nasdaq constituents as the historical
  candidate universe.
- Use yfinance alone for this branch.
- Tune loser thresholds after seeing January or rebound-window returns.

## Decision For The Next Slice

Build a tiny `forced_index_membership_events` source-provenance pilot only if
the next slice can preserve source URLs, announcement dates, and effective dates
from official releases.

Keep `tax_loss_selling_candidates` as higher-upside but blocked on data access.
It should not consume implementation time until survivorship-aware source data
is available.

## Sources Checked

- S&P Global example release, August 13, 2026:
  `https://press.spglobal.com/2026-08-13-Reddit-Set-to-Join-S-P-500-and-Sun-Communities-to-Join-S-P-MidCap-400`
- S&P Global example release, October 13, 2023:
  `https://press.spglobal.com/2023-10-13-Lululemon-Athletica-Hubbell-Set-to-Join-S-P-500-Others-to-Join-S-P-MidCap-400-and-S-P-SmallCap-600`
- S&P 500 addition/removal history secondary repository:
  `https://github.com/shawnlinxl/snp-history`
- Norgate data content tables:
  `https://norgatedata.com/data-content-tables.php`
- QuantConnect US Equity Security Master:
  `https://www.quantconnect.com/data/quantconnect-us-equity-security-master`
- HistoricalData.net methodology:
  `https://historicaldata.net/methodology.html`
- CRSP/WRDS variable page:
  `https://wrds-www.wharton.upenn.edu/demo/crsp/form/`
- Survivorship-clean reference pipeline:
  `https://github.com/tenicho/data-cleaning`
