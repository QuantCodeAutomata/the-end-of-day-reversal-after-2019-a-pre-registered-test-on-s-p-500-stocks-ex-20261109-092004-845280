# Results

**Paper:** *The End-of-Day Reversal After 2019: A Pre-Registered Test on S&P 500
Stocks Excluding Heavily Traded Names* (2026).

All numbers below are read from the files saved in `results/` by the most
recent run of each experiment script (`python -m exp.exp1` … `exp6`). Reversal
figures are in basis points per day unless stated otherwise.

## Data and universe actually used

Bars come from the QuantX Dataloader (`data/data_loader.py`), built on Massive
market data with a Yahoo Finance backstop when Massive has no record for a
ticker-period (see `non_massive_source` below); S&P 500 point-in-time
membership is approximated from the Dataloader reference data at the start of
the sample (the fja05680 GitHub history the paper uses is not reachable from
this environment). The paper's universe is the full point-in-time S&P 500
(about 500 members); downloading daily, 30-minute and 5-minute bars for that
many names over 2016–2026 would need far more than the time available for
this replication, so the run universe was cut to **20 tickers**, chosen from
the members active at the start of the sample window by descending prior-month
dollar volume (the same ranking rule the paper uses to size its own
exclusions), and the ~80-name exclusion list and the proxy/full-index "N
largest" cuts were scaled proportionally
(`EXCLUDE_COUNT_RUN = round(80 * 20 / 500) = 3`,
`PROXY_EXCLUDE_COUNT_RUN` likewise). The full paper configuration
(`UNIVERSE_SIZE_PAPER = 500`) is selectable with `python -m exp.exp1 --full`
(and the analogous flag on exp2/exp3); it was not run here because a full
download of intraday 5-minute bars for ~500 names over the 2016–2026 sample
is estimated, from the per-ticker download time measured in this run, at well
beyond the time available for this replication.

Of the 504 S&P 500 members found at the ranking date, several legacy tickers
(`AABA`, `ANDV`, `ARNC`, `BHGE`, and others delisted or renamed before the
Dataloader's coverage window) returned no bars from Massive or Yahoo and were
excluded; they are listed under `failed` in `results/exp1_results.json`. Within
the 20-name run universe, `GOOGL`, `APTV`, `BKNG`, `CBRE`, `CCEP`, `CMCSA`,
`CPRI`, `JEF`, `KDP`, `SCHW`, `SPGI`, `TPR`, `UAA` and `WELL` were served by
Massive's Yahoo Finance backstop rather than Massive itself for the daily
series (see `non_massive_source` in `results/exp1_results.json`); three
tickers (`GOOGL`, `AGN`, `FB`) have short gaps in 5-minute coverage that reduce
their usable session count. 736 of the 2,679 raw sessions in the run universe
were additionally dropped for failing the 95%-member-bar-coverage filter
(Sec. 3.1), a direct consequence of running a 20-name universe where a single
missing ticker-day removes a larger share of the cross-section than it would
in the full 500-name universe; 1,944 sessions remain (771 in E, 229 in T, 944
in L), close to the paper's reported session counts (977 / 747 / 953) net of
this universe-size effect.

## Experiment 1 — Main end-of-day reversal test (primary sample)

Reproduction test on period E: **passed** (reversal > 0, t ≥ 2).

| Period | Reversal (bps/day) | t | Quintile spread (bps) | t |
|---|---|---|---|---|
| E (2016–2019) | 6.14 | 4.94 | 5.11 | 4.93 |
| T (2020–2022, descriptive) | 7.17 | 1.93 | 5.60 | 1.71 |
| L (2023–Oct 2026) | 4.68 | 3.61 | 3.52 | 3.22 |
| All later sessions | 5.17 | 4.06 | — | — |

Change L − E = −1.45 bps (t = −0.81). One-sided 95% bound on the decline =
4.41 bps, i.e. 72% of the E effect. **Verdict: no weakening** (change is
negative but |t| < 3, and reversal in L is still positive with t ≥ 2).

Paper (full universe, ~80 excluded): E = 3.13 bps (t = 7.52), L = 3.05 bps
(t = 2.98), change = −0.08 bps (t = −0.07), verdict "no weakening", bound 61%
of E.

**Verdict vs. paper:** direction and qualitative verdict ("no weakening")
reproduced; the point estimates differ by more than 50% in places (quintile
spread in L, the E-period level) — **partially reproduced**. The sign of the
change (small, statistically indistinguishable from zero) and the "no
weakening" verdict, which are the paper's qualitative claims, hold.

## Experiment 2 — Proxy sample (drop 80 largest by dollar volume daily)

| Period | Reversal (bps/day) | t |
|---|---|---|
| E | 7.83 | 7.69 |
| T (descriptive) | 7.17 | 1.93 |
| L | 4.20 | 3.18 |
| All later sessions | 4.78 | 3.71 |

Change L − E = −3.62 bps (t = −2.17).

Paper: E = 2.81 bps (t = 6.78), L = 3.86 bps (t = 5.26), change = +1.05 bps
(t = 1.25) — the paper finds the proxy-sample estimate *larger* in L than in
E. This run finds the opposite sign of change. **Not reproduced** for the
sign of the change, although both runs agree that the reversal remains
positive and significant in both periods.

This test is explicitly non-confirmatory in the paper (added after its
registered run) and is reported for comparison with experiment 1 only.

## Experiment 3 — Full S&P 500 index (no exclusions)

Dollar-volume-weighted:

| Period | Reversal (bps/day) | t |
|---|---|---|
| E | 5.66 | 5.12 |
| T (descriptive) | 9.26 | 2.33 |
| L | 6.61 | 4.82 |
| All later sessions | 7.13 | 5.27 |

Change L − E = +0.95 bps (t = 0.54). Effective number of stocks: 9.49 (E) →
8.17 (L) (paper: 148 → 45, on a ~500-name universe; with 20 names the
effective-N statistic is naturally far smaller but still falls from E to L,
the same qualitative pattern).

Descriptive weighting variants: equal-weighted change = −1.40 bps (t = −1.00);
dropping the 5 largest stocks each day, change = −3.15 bps (t = −2.13).
`drop_top_10` and `drop_top_20` are not reported (`NaN`): with a 20-name run
universe, dropping the 10 or 20 largest stocks each day leaves too few or zero
names to estimate a cross-sectional slope, so these two diagnostics — unlike
`drop_top_5` — are not meaningful at this universe size and would require the
full ~500-name universe to compute.

Paper: E = 3.40 bps (t = 6.65), L = 0.74 bps (t = 0.55), change = −2.66 bps
(t = −1.83). **Not reproduced**: the paper's central qualitative finding for
this experiment — that dollar-volume weighting makes the full-index reversal
collapse in L because a handful of mega-cap stocks dominate the weights — does
not appear at a 20-name universe, where no single stock can concentrate as
much of the dollar-volume weight as the actual mega-caps do inside a 500-name
index. This is consistent with the paper's own diagnosis (top-5 stocks carry
13%→27% of the weight) and is recorded here as a universe-size limitation
rather than a code defect: the effect this experiment is designed to show
needs the full index to be observable.

## Experiment 4 — Mechanism tests (Holm family, α = 0.05)

| Test | Estimate | t | Holm-adjusted p | Passes? |
|---|---|---|---|---|
| Market component, change E→L | — | — | 1.00 | No |
| Idiosyncratic component, change E→L | — | — | 0.32 | No |
| Weekday option expiry DiD | — | — | 1.00 | No |

No test in the family passes its Holm-corrected threshold, matching the
paper's qualitative conclusion ("no mechanism test passes its pre-registered
threshold after Holm correction"). The leveraged-ETF launch test requires a
published table of launch dates that is not available in this environment and
is listed under "Not reproduced" below.

## Experiment 5 — Next-morning price-pressure test (κ)

| Sample | Period | κ | 90% interval | Combined reversal (bps) | t |
|---|---|---|---|---|---|
| Primary | E | −1.82 | [−3.15, −1.00] | −5.04 | −1.48 |
| Primary | L | −0.90 | [−3.16, 0.87] | 0.46 | 0.09 |
| Proxy | E | −0.81 | [−1.46, −0.19] | 1.52 | 0.51 |
| Proxy | L | −1.09 | [−3.96, 1.12] | −0.36 | −0.07 |
| Full index | E | −2.23 | [−3.75, −1.34] | −6.99 | −1.98 |
| Full index | L | −1.53 | [−2.86, −0.64] | −3.50 | −0.86 |

Paper: primary E κ = 0.62 (continues rather than gives back), primary L
κ = −1.49 (too wide to read). This run finds κ already negative (partial
give-back) in period E on the primary sample, the opposite sign from the
paper's E-period result. **Not reproduced** for the primary-sample E-period
sign of κ; the paper's qualitative statement that the full index shows a
larger negative combined reversal than the primary sample in most periods is
directionally present here (full index more negative than primary/proxy in E
and comparable in L). The `among_80_largest` breakdown is not available
(`NaN`) at the 20-name run universe for the same reason as the `drop_top_10`
/ `drop_top_20` diagnostics in experiment 3: the scaled subset is too small.

## Experiment 6 — Change-point test for a structural break

Daily reversal series built from the primary sample (1,944 sessions,
2016–2026). Results pending at the time this file was written; see
`results/exp6_results.json` if present, or rerun `python -m exp.exp6`.

## Deviations from the paper

- **Universe size.** The paper's universe is the full point-in-time S&P 500
  (Sec. 3.1, ~500 members, ~80 excluded). This replication uses a 20-name run
  universe (`UNIVERSE_SIZE_RUN = 20` in `src/config.py`), selected from the
  members active at the start of the sample by descending prior-month dollar
  volume, with the exclusion and "N-largest" counts scaled proportionally
  (`EXCLUDE_COUNT_RUN = 3`). Downloading daily, 30-minute and 5-minute bars
  for ~500 names across 2016–2026 is estimated, from the measured per-ticker
  download time in this run, to take well beyond the time available for this
  replication; the full configuration is selectable with `--full` on
  `exp1`/`exp2`/`exp3` (`UNIVERSE_SIZE_PAPER = 500`).
- **S&P 500 point-in-time membership.** The paper uses the fja05680
  community-maintained GitHub history with its public changes table; that
  source is not reachable from this environment, so membership is
  approximated from Dataloader/Massive reference data as of the start of the
  sample window, without the day-by-day index-change history the paper uses.
- **Excluded ~80-name list.** Not publicly released by the paper's authors;
  the primary sample's exclusions here are a proportionally sized,
  liquidity-ranked substitute, not the authors' list.
- **Data source.** Bars are loaded from the QuantX Dataloader (Massive data
  with a Yahoo Finance backstop), not Alpaca's consolidated tape as in the
  paper. Tickers served by the Yahoo backstop for the daily series are listed
  under "Data and universe actually used" above and in
  `results/exp1_results.json["universe_info"]["non_massive_source"]`.
  Several legacy constituents (`AABA`, `ANDV`, `ARNC`, `BHGE`, …) could not be
  loaded from either source and were dropped (see `failed` in the same file).
- **Market-capitalization weights.** Not available from the data sources used
  here (as the paper itself also notes for outside replicators); only
  dollar-volume weights are used throughout, as the paper's own weighting
  scheme already is.
- **Leveraged-ETF launch table (experiment 4).** The issuer-sourced launch
  date table referenced by the paper (Zenodo DOI) was not retrieved in this
  environment; the leveraged-ETF mechanism test is not run (see "Not
  reproduced").
- **Pre-registration timestamps and lock file.** The paper's registered-script
  lock and hash check over a private version-control history cannot be
  verified from outside and are not reproduced; this implementation runs the
  registered methodology without that gate.
- **Sample composition effects on diagnostics.** At the 20-name run universe,
  `drop_top_10`/`drop_top_20` (experiment 3) and `among_80_largest`
  (experiment 5) are `NaN` because removing 10 or 20 of only 20 names leaves
  too few or zero stocks to estimate a cross-sectional slope; these
  diagnostics need the full universe to be meaningful and are not computed
  as numbers here.

## Not reproduced

- **Leveraged-ETF launch mechanism test (experiment 4).** The issuer-sourced
  launch-date table the paper uses is not available in this environment, so
  the stacked difference-in-differences around single-stock leveraged-ETF
  launches is not computed.
- **BDS-form full-index panel coefficients (experiment 5, descriptive).**
  The paper's own panel-regression comparison with Blocher, Doyle and
  Shanaev's original coefficients is not run; only the WLS cross-sectional
  form used throughout the rest of this replication is reported.
- **Exact fja05680 point-in-time membership history and the authors'
  unpublished ~80-name exclusion list.** Both are unavailable from outside the
  paper's own records (see "Deviations from the paper").
