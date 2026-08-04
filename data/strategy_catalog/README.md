# Strategy Catalog

This folder is the conceptual strategy library. It is deliberately separate
from executable strategy JSON in `data/strategies/`.

Catalog entries answer:

- why the idea might work,
- what benefit it is supposed to provide,
- how it can fail,
- what project capabilities it needs,
- which canonical variants are worth considering,
- how the idea should be validated,
- what references or research traditions motivated it,
- and whether the current engine can execute it.

Each canonical variant also carries three small routing fields:

- `research_priority`: `core`, `secondary`, or `later`.
- `capability_status`: whether the idea is executable now or needs a schema,
  data, portfolio, or broader capability extension first.
- `next_action`: the intended next human/Codex action before the idea becomes
  an executable strategy file.

The catalog can grow faster than the executable strategy library because entries
are research ideas, not implementation promises. A variant should become
executable strategy JSON only after a human approves that specific hypothesis and
success criteria.

Current intended use:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli ideas suggest
```

The command reads this catalog and prior
`artifacts/research/**/experiment_conclusion.json` files, registry decisions in
`artifacts/experiments.jsonl`, and tracked experiment handoffs in
`docs/experiments/`. It excludes ideas that match `do_not_repeat` or rejected
decision guidance, ranks compatible families, and prints one proposed hypothesis
plus a draft experiment config.

As of this catalog expansion, the library contains at least 30 canonical
variants across trend, mean-reversion, breakout, volatility, calendar,
cross-asset, portfolio, factor, breadth, and event/gap research themes. Only
variants explicitly marked `engine_can_currently_execute: true` should be
converted into runnable project files without first adding engine capability.
For future research cycles, prefer `research_priority: core` ideas when they
are not blocked by prior `do_not_repeat` findings.
