# Repository guide

This repository replicates "The End-of-Day Reversal After 2019: A
Pre-Registered Test on S&P 500 Stocks Excluding Heavily Traded Names". It
implements the paper's six pre-registered and descriptive experiments on the
end-of-day reversal (`exp_1`-`exp_6`): the main test on the primary sample,
the public proxy sample, the full S&P 500 index, the four mechanism tests,
the next-morning give-back test, and the sup-Wald change-point test.

## Layout

- `src/` - flat library modules shared by every experiment: `config.py`
  (all paper-derived parameters, grouped by experiment, each with its source),
  `universe.py` (point-in-time S&P 500 membership and sample construction),
  `samples.py` (primary/proxy/full-index filtering), `calendar_filters.py`
  (session exclusions: early closes, low coverage, no prior-month volume),
  `data_pipeline.py` (ROD3/LH construction from loaded bars),
  `reversal.py` (rank transform, WLS, Newey-West, period reversal, quintile
  spread, reproduction test, verdict rules), `mechanism.py` (market/
  idiosyncratic split, weekday option-expiry and leveraged-ETF
  difference-in-differences, Holm correction), `nextmorning.py` (kappa
  give-back test), `changepoint.py` (Andrews sup-Wald test, block bootstrap,
  power simulation).
- `exp/` - one script per experiment (`python -m exp.exp1` ... `exp.exp6`),
  calling only the `src/` functions by their documented signatures.
- `data/` - `data_loader.py` loads OHLCV bars from the QuantX Dataloader REST
  API; downloaded bars are never committed (`data/cache/` is gitignored).
- `tests/` - unit tests on synthetic fixtures for every `src/` component, plus
  `@pytest.mark.market_data` tests that load a reduced real slice through
  `data/data_loader.py` (skipped automatically when `DATALOADER_API_KEY` is
  unset).
- `results/` - every metric, table, series and figure an experiment run
  writes, plus `results/RESULTS.md` with the comparison to the paper.

## Conventions

- All experiment parameters live in `src/config.py` as module-level
  `UPPER_CASE` variables with a comment on their meaning, unit and source
  (a paper section, or "not specified in the paper"). No parameters are
  hardcoded elsewhere.
- Market data is loaded only through `data/data_loader.py`; no other module
  calls an external price API. API keys (`DATALOADER_API_KEY`,
  `MASSIVE_API_KEY`) are read from the environment through `.env` (see
  `.env.example`) and never appear in code, logs or results.
- Each experiment script's `--full` flag selects the paper's full
  point-in-time universe and sample period instead of the reduced
  configuration used for the run committed in `results/`; see
  `results/RESULTS.md`, "Deviations from the paper", for the sizes and the
  estimated download time of the full run.

## Commands

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in DATALOADER_API_KEY and MASSIVE_API_KEY

python -m pytest -m "not market_data"   # unit tests, no network
python -m pytest                        # also runs the market-data slice tests

python -m exp.exp1   # ... through exp.exp6
python -m exp.exp1 --full   # paper's full universe and sample period
```

`bash reproduce.sh` runs the test suite and every experiment with the
commands above.

## After a rerun

Every experiment script overwrites its files in `results/` on each run. The
numbers, tables and verdicts in `results/RESULTS.md` are not regenerated
automatically: after a rerun, check them against the new files in `results/`
and update `results/RESULTS.md` by hand.
