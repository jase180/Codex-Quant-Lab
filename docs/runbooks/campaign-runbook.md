# Campaign Runbook

Use this runbook when you want the lab to run a bounded sequence of experiments
without giving an agent permission to edit code or invent unsupported strategy
features.

## Current Boundary

`quant-lab campaign run` currently supports a deterministic campaign provider.
It runs one campaign cycle per command invocation:

1. Read `campaign_config.json` and `campaign_state.json`.
2. Propose one bounded experiment.
3. Validate the proposal against allowed templates, data, budgets, and
   `do_not_repeat` memory.
4. Convert the proposal into the existing `experiment run-default` workflow.
5. Execute that workflow.
6. Read `experiment_conclusion.json`.
7. Update `campaign_state.json` and `campaign_state.md`.

When the deterministic sequence is exhausted, it writes `final_report.md` and
`final_report.json`.

The campaign runner must not modify source code, add indicators, change success
criteria after seeing results, or silently expand parameter grids.

## First SPY Campaign

The checked-in sample config is:

```text
data/campaigns/spy_drawdown_control_campaign.json
```

It intentionally allows only:

- symbol: `SPY`
- templates: `sma-long-cash`, `ema-trend-follow`
- benchmark: `buy-and-hold`
- cost preset: `retail-liquid`
- max cycles: `3`
- max total runs: `33`

The `33` run budget matters because each current default workflow cycle projects
`11` backtests. A smaller budget can make later valid proposals impossible.

## Run The Campaign

Start a fresh campaign:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --config data\campaigns\spy_drawdown_control_campaign.json `
  --out artifacts\campaigns\spy_research_001 `
  --force
```

Resume for the next cycle:

```powershell
.\.venv-win\Scripts\python.exe -m quant_lab.cli campaign run `
  --out artifacts\campaigns\spy_research_001 `
  --resume
```

Run the resume command until it writes:

```text
final_report: artifacts\campaigns\spy_research_001\final_report.md
```

## Current Deterministic Sequence

The deterministic provider currently proposes:

1. `SPY SMA 200 long/cash campaign baseline`
2. `SPY EMA 50 RSI trend-follow campaign follow-up`
3. `stop_campaign`

It stops after those known proposals instead of inventing a third strategy.

## What To Read

During a running campaign, read:

```text
artifacts/campaigns/<campaign>/campaign_state.md
```

For one cycle's proposal gate, read:

```text
artifacts/campaigns/<campaign>/cycles/cycle_001/proposal_validation.md
```

For one cycle's main research conclusion, read:

```text
artifacts/campaigns/<campaign>/cycles/cycle_001/experiment/experiment_conclusion.md
```

After the campaign stops, read:

```text
artifacts/campaigns/<campaign>/final_report.md
```

Treat `final_report.md` as the campaign front door. Use the JSON version for
future automation:

```text
artifacts/campaigns/<campaign>/final_report.json
```

## How To Interpret Results

The campaign keeps two separate outcomes:

- `Research-system status`: whether the repo measured the experiment honestly
  and reproducibly.
- `Strategy-hypothesis status`: whether the strategy met its prespecified
  investment criteria.

A result can be:

```text
Research-system status: valid
Strategy-hypothesis status: rejected
```

That means the lab worked and the strategy failed. Do not treat that as a repo
failure.

The final report may name a best remaining candidate. That is not a trading
recommendation. It means the candidate is the least-bad branch from this bounded
campaign and still needs review against unresolved risks.

## Stop Conditions

The current campaign stops when:

- the deterministic provider has no materially different proposal left,
- the run budget is too small for the next projected workflow,
- cycle budget is exhausted,
- proposal validation fails,
- or the provider returns `stop_campaign`.

Future Ollama and Codex providers should keep the same boundary: providers
return strict proposal JSON, while the controller owns validation, execution,
state, and stopping.
