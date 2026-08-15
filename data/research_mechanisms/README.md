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
.\.venv-win\Scripts\python.exe -m quant_lab.cli mechanisms data-needs --engine-fit needs_data
```

Engine fit meanings:

- `ready`: the current engine can test a decent version.
- `proxy_only`: the current engine can test only a rough proxy.
- `needs_data`: the idea is interesting but needs additional data first.
- `blocked`: the current engine cannot test it honestly yet.
