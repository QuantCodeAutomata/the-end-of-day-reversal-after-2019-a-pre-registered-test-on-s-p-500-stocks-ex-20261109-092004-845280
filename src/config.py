"""Parameters for the end-of-day reversal replication (Sections 3-5).

All experiment parameters live here as module-level constants, grouped by the
section of the paper that defines them. Every variable carries a one-line
source note (section/equation, or "not specified in the paper").
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Section 3.1 Universe and sample period
# ---------------------------------------------------------------------------
SAMPLE_START = "2016-01-04"  # first session of period E, Sec. 3.1
SAMPLE_END = "2026-10-30"  # last session of period L, Sec. 3.1 ("2026 runs to October 30")

PERIOD_E = ("2016-01-04", "2019-12-31")  # reproduction-test period, Sec. 3.4
PERIOD_T = ("2020-01-01", "2022-12-31")  # descriptive-only period, Sec. 3.4
PERIOD_L = ("2023-01-01", "2026-10-30")  # registered confirmatory period, Sec. 3.4

SP500_MEMBERSHIP_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
)  # point-in-time S&P 500 membership, Sec. 3.1 (fja05680 community repository, updated table)

SP500_UNIVERSE_SIZE_PAPER = 500  # approximate S&P 500 size, Sec. 3.1
SP500_EXCLUDE_COUNT_PAPER = 80  # heavily traded names excluded from the primary sample, Sec. 3.1 / abstract

# The paper's exact ~80-name exclusion list is not released (Sec. 3.1,
# uncertainties), so the primary sample cannot be rebuilt outside the
# authors' environment. This replication instead downloads a reduced,
# liquidity-ranked subset of point-in-time S&P 500 members (see
# UNIVERSE_SIZE_RUN below) so that the full 2016-2026 daily, 30-minute and
# 5-minute history fits the time available for this replication; the
# ~80-name exclusion is scaled proportionally (EXCLUDE_COUNT_RUN below).
UNIVERSE_SIZE_PAPER = SP500_UNIVERSE_SIZE_PAPER  # full point-in-time S&P 500, Sec. 3.1
UNIVERSE_SIZE_RUN = 60  # reduced universe actually downloaded (see results/RESULTS.md)
EXCLUDE_COUNT_RUN = round(
    SP500_EXCLUDE_COUNT_PAPER * UNIVERSE_SIZE_RUN / SP500_UNIVERSE_SIZE_PAPER
)  # proportional scaling of the ~80-name exclusion to UNIVERSE_SIZE_RUN

UNIVERSE_RANKING_DATE = "2016-01-04"  # date used to rank candidates by prior-month dollar volume when reducing the universe (not specified in the paper)

MIN_PRICE = 5.0  # drop stocks priced under $5 at prior close, Sec. 3.1 (methodology step 3)
MAX_ABS_OVERNIGHT_MOVE = 0.40  # drop stock-days with overnight moves > 40% absolute, Sec. 3.1
MIN_MEMBER_COVERAGE = 0.95  # drop sessions with < 95% member bar coverage, Sec. 3.1

CLOSE_TIME = "15:55"  # 5-minute bar whose close approximates "last trade before 4:00 p.m.", Sec. 3.3 (16:00-)
THIRTY_PM = "15:00"  # P(15:00) anchor of ROD3, Eq. 1
THIRTY_THIRTY_PM = "15:30"  # P(15:30) anchor of LH, Eq. 1

# ---------------------------------------------------------------------------
# Section 3.3 Variables and estimator
# ---------------------------------------------------------------------------
RANK_SCALE_LOW = -0.5  # scaled-rank lower bound, Sec. 3.3 (q in [-0.5, 0.5])
RANK_SCALE_HIGH = 0.5  # scaled-rank upper bound, Sec. 3.3
NEWEY_WEST_LAGS = 5  # Newey-West (1987) lags for period means, Sec. 3.3
QUINTILES = 5  # quintile sort for the secondary spread statistic, Sec. 3.3
WINSORIZE = False  # the paper does not winsorize LH (unlike BDS at 1%/99%), Sec. 3.3

# ---------------------------------------------------------------------------
# Section 3.4 Periods, order of runs and verdicts
# ---------------------------------------------------------------------------
REPRODUCTION_T_MIN = 2.0  # reproduction-test bar: R_E > 0 with t >= 2, Sec. 3.4
WEAKENED_T_BAR = 3.0  # "weakened" verdict bar: Delta < 0 with t <= -3, Sec. 3.4 (Harvey-Liu-Zhu, 2016)
NO_WEAKENING_T_MIN = 2.0  # no-weakening clause: R_L > 0 with t >= 2, Sec. 3.4
ONE_SIDED_CI_LEVEL = 0.95  # one-sided confidence bound on the decline, Sec. 4.2
ONE_SIDED_TEST_ALPHA = 0.05  # secondary one-sided 5% test reported alongside the t=3 bar, Sec. 3.4

# ---------------------------------------------------------------------------
# Section 3.1 / 4.3 Proxy sample (experiment 2) and full index (experiment 3)
# ---------------------------------------------------------------------------
PROXY_EXCLUDE_COUNT_PAPER = 80  # largest stocks by prior-month dollar volume dropped daily, Sec. 3.1
DOLLAR_VOLUME_LOOKBACK_DAYS = 21  # "prior calendar month" approximated by 21 trading days (not specified exactly in the paper)

DROP_LARGEST_N_PAPER = (5, 10, 20)  # descriptive drop-N-largest robustness checks, Sec. 4.2/4.5
WINSORIZE_PCT = 0.01  # 1%/99% winsorization used only in descriptive robustness tables, Sec. 3.3/4.5 (Table 7)

# ---------------------------------------------------------------------------
# Section 5 Mechanism tests (experiment 4)
# ---------------------------------------------------------------------------
BETA_WINDOW = 252  # rolling window (sessions) for stock-on-SPY beta, Eq. 4
BETA_MIN_SESSIONS = 200  # minimum sessions required inside the window, Sec. 5.1
MECHANISM_START = "2016-11-01"  # market/idiosyncratic split starts once beta has ~1 year of history, Sec. 5.1
WEEKDAY_DID_START = "2017-01-01"  # weekday option-expiry DiD sample start, Sec. 5.1
WEEKDAY_OPTION_EVENT_DATE = "2022-05-01"  # same-day SPX Tuesday/Thursday expiries introduced April-May 2022, Sec. 5.1
WEEKDAY_TREATED_DAYS = ("Tuesday", "Thursday")  # weekdays that gained same-day index-option expiries, Sec. 5.1
HOLM_ALPHA = 0.05  # family-wise alpha for the Holm (1979) correction across the four mechanism tests, Sec. 5.1
LEVERAGED_ETF_MIN_TREATED = 20  # pre-registered minimum treated stocks required to judge the test, Sec. 5.1/5.2
LEVERAGED_ETF_WINDOW = 250  # sessions before/after launch used in the stacked DiD slope comparison, Sec. 5.2
LEVERAGED_ETF_CONTROLS_PER_TREATED = 3  # untreated stocks of similar dollar volume matched per treated stock, Sec. 5.2
LEVERAGED_ETF_LAUNCH_TABLE_URL = "https://doi.org/10.5281/zenodo.24003093"  # authors' launch-date table, Sec. 5.2
LEVERAGED_ETF_REGISTERED_CUTOFF = "2025-12-31"  # registered launch cutoff, Sec. 5.2

# The authors' own launch table (Sec. 5.2) is not reachable from this
# environment; the paper warns that an aggregator source placed nine launch
# dates up to ten months too early (Sec. 5.2), so this substitute table is
# built only from issuer product pages/fact sheets for single-stock
# leveraged-long ETFs on large, liquid S&P 500 names likely to fall inside a
# liquidity-ranked run universe. It is an assumption, not a value confirmed
# by the paper (see results/RESULTS.md, "Deviations from the paper").
LEVERAGED_ETF_LAUNCHES = {
    "TSLA": "2022-04-28",  # Direxion Daily TSLA Bull 1.5x Shares (TSLL)
    "NVDA": "2022-12-15",  # GraniteShares 1.5x Long NVDA Daily ETF (NVDL)
    "AAPL": "2022-08-23",  # GraniteShares 1.5x Long AAPL Daily ETF (AAPU)
    "AMZN": "2022-08-23",  # GraniteShares 1.5x Long AMZN Daily ETF (AMZU)
    "MSFT": "2022-08-23",  # GraniteShares 1.5x Long MSFT Daily ETF (MSFU)
    "GOOGL": "2022-08-23",  # GraniteShares 1.5x Long GOOGL Daily ETF (GGLL)
    "META": "2022-08-23",  # GraniteShares 1.5x Long META Daily ETF (FBL)
    "AMD": "2023-03-08",  # GraniteShares 1.5x Long AMD Daily ETF (AMDL)
    "COIN": "2023-04-26",  # GraniteShares 1.5x Long COIN Daily ETF (CONL)
    "NFLX": "2023-06-28",  # GraniteShares 1.5x Long NFLX Daily ETF (NFXL)
    "BA": "2023-08-16",  # GraniteShares 1.5x Long BA Daily ETF (BOEU)
    "DIS": "2023-08-16",  # GraniteShares 1.5x Long DIS Daily ETF (DISX)
}

# ---------------------------------------------------------------------------
# Section 4.6 Next-morning price pressure (experiment 5)
# ---------------------------------------------------------------------------
KAPPA_RANGE = (-1.2, -0.3)  # pre-registered range for kappa = next-morning slope / closing slope, Sec. 4.6
KAPPA_CI_LEVEL = 0.90  # 90% interval reported for kappa, Sec. 4.6

# ---------------------------------------------------------------------------
# Section 4.4 Change-point tests (experiment 6)
# ---------------------------------------------------------------------------
CHANGEPOINT_TRIM = 0.15  # Andrews (1993) sup-Wald trimming fraction, Sec. 4.4
CHANGEPOINT_BLOCK_DAYS = 21  # block-bootstrap block length, Sec. 3.4/4.4
CHANGEPOINT_BOOTSTRAP_DRAWS_PAPER = 999  # paper's bootstrap draw count, Sec. 3.4/4.4
CHANGEPOINT_BOOTSTRAP_DRAWS_RUN = 999  # draws actually used (feasible at this series length)
CHANGEPOINT_BREAK_P_BAR = 0.01  # pre-registered break threshold, Sec. 4.4
CHANGEPOINT_BREAK_WINDOW = ("2020-01-01", "2024-12-31")  # pre-registered date window for a declared break, Sec. 4.4
CHANGEPOINT_CI_LEVEL = 0.90  # 90% interval for the most likely break date, Sec. 4.4
POWER_SIM_DRAWS_PAPER = 1000  # Monte Carlo draws for the power simulation (not specified exactly; matches bootstrap scale)
POWER_SIM_DRAWS_RUN = 200  # reduced draw count used in this replication's run (see results/RESULTS.md)

# ---------------------------------------------------------------------------
# Random seed
# ---------------------------------------------------------------------------
RANDOM_SEED = 20190813  # the paper reports a fixed pre-registered seed without giving its value; a fixed seed is used here for reproducibility (not specified in the paper)
