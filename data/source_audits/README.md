# Source Audits

This folder stores source-availability audits for planned research datasets.

Source audits happen before data construction and before strategy work. Their
job is to answer whether a proposed niche dataset can be built honestly from
auditable, legally usable, point-in-time inputs.

Status meanings:

- `viable_pilot`: enough source material exists for a small bounded diagnostic,
  but not necessarily a full production dataset.
- `viable`: enough source material appears available for the planned dataset,
  subject to normal parsing and validation work.
- `blocked`: current accessible sources are not good enough for honest research.
- `vendor_required`: honest research likely requires a paid or institutionally
  licensed dataset.

Do not downgrade source requirements just to create another backtest. A biased
or unauditable dataset should stop the research branch.
