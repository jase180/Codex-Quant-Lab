# Experiment Template Catalog

Experiment templates describe bounded research families before they become
campaign candidates. They are separate from executable strategy JSON.

A template should answer:

- what claim it tests,
- which strategy family it belongs to,
- what project capabilities it needs,
- how it maps to a campaign-safe executable template,
- which parameter neighborhood it may use,
- and whether it is executable today.

This catalog is intentionally small at first. The next milestone slices will use
it to generate candidate menus, then ask a provider to choose from candidate IDs
instead of inventing experiments.

Multiple templates may map to the same executable strategy JSON when they are
testing different opportunity theses. In that case, the candidate ID carries the
opportunity thesis, while the run title stays focused on the actual execution.
