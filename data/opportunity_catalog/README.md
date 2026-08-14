# Opportunity Catalog

This folder stores conceptual `opportunity_thesis.v1` records. These are not
executable strategies. They describe market niches and structural reasons an
edge might exist before Quant Lab converts any one idea into strategy JSON.

Each thesis should answer:

- which `research_mechanism.v1` record inspired it,
- what market niche or phenomenon is being investigated,
- who may be forced or incentivized to trade in a predictable way,
- why small capital might have an advantage,
- why larger institutions may ignore or under-arbitrage it,
- what evidence supports that capacity/friction claim,
- what would make the edge decay,
- what observable prediction follows,
- how the thesis could be falsified,
- which current strategy families could test it,
- and whether the current engine can test it now.

The catalog deliberately uses a gated rubric instead of a fake numeric score.
The allowed disposition is one of:

- `test_now`
- `investigate_data`
- `watchlist`
- `reject`

Use this catalog to inspire agent-generated research ideas. Do not require every
manual sanity-check experiment to have an opportunity thesis.

Treat this folder as a research vocabulary, not as a list of proven strategies.
A `test_now` thesis means the current engine can run a bounded falsification
attempt; it does not mean the opportunity is supported.

Every thesis has a `mechanism_id` that must resolve to a file in
`data/research_mechanisms/`. The intended hierarchy is:

```text
research mechanism -> opportunity thesis -> experiment template -> campaign candidate
```

That keeps external research raw material separate from the narrower claim that
the current engine can actually falsify.
