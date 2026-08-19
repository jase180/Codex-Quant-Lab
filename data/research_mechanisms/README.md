# Research Mechanism Library

This folder stores `research_mechanism.v1` records.

Mechanisms are not executable strategies. They are structured raw material for
future opportunity theses. A good mechanism answers:

- what market behavior might be imperfect,
- who is forced or incentivized to trade,
- why the behavior might persist,
- why large capital may ignore or under-arbitrage it,
- what data would be needed,
- what prediction follows,
- and how the idea could be falsified.

Use this folder to feed the lab better research material. Do not treat these
records as proven alpha or as strategy JSON.

Useful commands:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli mechanisms list
.\.venv-win\Scripts\python.exe -m quant_lab.cli mechanisms show --id forced_index_flows
.\.venv-win\Scripts\python.exe -m quant_lab.cli mechanisms map
.\.venv-win\Scripts\python.exe -m quant_lab.cli mechanisms data-needs --engine-fit needs_data
.\.venv-win\Scripts\python.exe -m quant_lab.cli mechanisms data-plan --id calendar_rebalance_effects
```

Use `mechanisms map` before asking the lab to run a campaign from a broad idea.
It joins mechanism records, opportunity theses, dataset plans, and executable
experiment-template coverage. Rows marked `needs_data` or `blocked` should feed
dataset planning, not strategy generation.

Engine fit meanings:

- `ready`: the current engine can test a decent version.
- `proxy_only`: the current engine can test only a rough proxy.
- `needs_data`: the idea is interesting but needs additional data first.
- `blocked`: the current engine cannot test it honestly yet.

Discovery-map disposition meanings:

- `testable_now`: raw material and at least one thesis/template pair are ready
  for a bounded test.
- `proxy_testable`: the lab can run a rough proxy, but the result should not be
  treated as full evidence for the underlying mechanism.
- `needs_data`: gather or define raw data before running a strategy.
- `blocked`: current data or engine assumptions cannot measure the idea
  honestly.
