# The End-of-Day Reversal After 2019: A Pre-Registered Test on S&P 500 Stocks Excluding Heavily Traded Names

Replication of the paper's pre-registered test of the end-of-day reversal in
S&P 500 stocks, comparing its magnitude in 2016-2019 against 2023-October
2026.

## What this repository implements

- **exp_1** - the main reversal test on the primary sample (a fixed set of
  heavily traded names excluded), with the reproduction-test gate on
  2016-2019 before any confirmatory statistic on 2023-2026 is read.
- **exp_2** - the proxy sample that drops, each day, the largest members by
  prior-month dollar volume, reproducible from public data.
- **exp_3** - the full S&P 500 index with no exclusions, plus the weight and
  outlier diagnostics (equal weights, square-root weights, winsorization,
  dropping the largest names, leave-one-out, effective number of stocks).
- **exp_4** - the four pre-registered mechanism tests (market/idiosyncratic
  split, weekday option-expiry difference-in-differences, leveraged-ETF
  launch difference-in-differences), Holm-corrected at alpha = 0.05.
- **exp_5** - the next-morning price-pressure test (kappa reversal give-back).
- **exp_6** - the sup-Wald change-point test for a structural break in the
  daily reversal series, with a block-bootstrap p-value and a power
  simulation.

## Data

Daily, 30-minute and 5-minute bars are loaded through the QuantX Dataloader
REST API (`data/data_loader.py`); point-in-time S&P 500 membership is loaded
from the public, community-maintained history named by the paper
(`src/universe.py`). See `results/RESULTS.md`, "Deviations from the paper",
for the universe size and sample-period details actually used.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in DATALOADER_API_KEY and MASSIVE_API_KEY
```

## Tests

```bash
python -m pytest -m "not market_data"   # unit tests on synthetic fixtures
python -m pytest                         # includes a reduced real-data slice
```

## Running the experiments

```bash
python -m exp.exp1   # main reversal test, primary sample
python -m exp.exp2   # proxy sample
python -m exp.exp3   # full index, no exclusions
python -m exp.exp4   # mechanism tests
python -m exp.exp5   # next-morning price pressure
python -m exp.exp6   # change-point test
```

Each command appends `--full` to run the paper's full point-in-time S&P 500
universe instead of the reduced universe used for this replication's run (see
`results/RESULTS.md` for the estimated download time of the full universe).

Results (JSON metrics, CSV series and PNG figures) are written directly to
`results/`, overwriting any earlier run.

## Reproduce everything

```bash
bash reproduce.sh
```
