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
