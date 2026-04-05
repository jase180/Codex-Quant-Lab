# Codex-Quant-Lab

## Strategy schema

This repo now includes a strict v1 strategy representation for simple rule-based trading ideas:

- Parser and validation: [src/quant_lab/strategy_schema.py](/C:/Users/jase1/repos/Codex-Quant-Lab/src/quant_lab/strategy_schema.py)
- Example strategies: [data/strategies/rsi_reversion.json](/C:/Users/jase1/repos/Codex-Quant-Lab/data/strategies/rsi_reversion.json)
- Schema notes: [docs/strategy-schema.md](/C:/Users/jase1/repos/Codex-Quant-Lab/docs/strategy-schema.md)

Run the tests with:

```powershell
python -m unittest discover -s tests
```

## Backtester Core v1

The default backtester flow is intentionally simple and uses daily OHLCV input for a single instrument.

- A strategy sees one daily bar at a time and can return `buy` or `sell` market orders.
- Orders generated from bar `t` are queued and filled on bar `t+1` at the next bar open.
- End-of-day portfolio history is recorded at each bar close after any queued fill for that day.
- Signals generated on the final bar are not filled because there is no next bar open available.
