"""Shared end-of-day reversal pipeline (Sec. 3.3-3.4).

One implementation of the stock-day panel, the cross-sectional rank
transform, the weighted-least-squares reversal estimator, and the
Newey-West period statistics used by every experiment (exp_1-exp_6).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.linear_model import WLS

from data import data_loader as dl
from src import calendar_filters, config

THIRTY_MIN_TIMES = [config.THIRTY_PM, config.THIRTY_THIRTY_PM]
FIVE_MIN_TIMES = [config.CLOSE_TIME]


def load_stock_day_panel(
    tickers: list[str], start: str, end: str, use_cache: bool = True
) -> tuple[pd.DataFrame, dict]:
    """Daily/30-minute/5-minute anchors needed for ROD3 and LH (Eq. 1).

    Returns one row per (ticker, date) with ``prior_close``, ``open``,
    ``p1500`` (price at 3:00 p.m., the open of the 15:00 30-minute bar),
    ``p1530`` (price at 3:30 p.m., the open of the 15:30 30-minute bar),
    ``p1600m`` (last trade before 4:00 p.m., the close of the 15:55 5-minute
    bar), and ``dollar_volume`` (same-day price times volume), plus a
    metadata dict merging the three Dataloader loads for provenance.
    """
    # Market data: QuantX Dataloader — https://quantx.limex.pro/
    #
    # Price history in this project is loaded through the QuantX Dataloader, a
    # research-ready market-data service available through a REST API and as an
    # MCP server for AI agents. It is built on market data from Massive
    # (https://massive.com/) and prepares every stock history for backtesting:
    #   - prices adjusted for dividends, ready for total-return research;
    #   - one continuous history when a company changes its ticker;
    #   - clean separation when a ticker has belonged to different companies;
    #   - careful corporate-action handling and fine-grained data polishing.
    #
    # Get your DATALOADER_API_KEY at https://quantx.limex.pro/ and your
    # MASSIVE_API_KEY at https://massive.com/.
    daily, daily_meta = dl.load_ohlcv(tickers, start, end, timeframe="1d", use_cache=use_cache)
    thirty, thirty_meta = dl.load_ohlcv(
        tickers, start, end, timeframe="30m", use_cache=use_cache, keep_times=THIRTY_MIN_TIMES
    )
    five, five_meta = dl.load_ohlcv(
        tickers, start, end, timeframe="5m", use_cache=use_cache, keep_times=FIVE_MIN_TIMES
    )

    daily = daily.sort_values(["ticker", "date"])
    daily["prior_close"] = daily.groupby("ticker")["close"].shift(1)
    daily["dollar_volume"] = daily["close"] * daily["volume"]
    base = daily[["ticker", "date", "prior_close", "open", "close", "dollar_volume"]]

    p1500 = thirty[thirty["time"] == config.THIRTY_PM][["ticker", "date", "open"]]
    p1500 = p1500.rename(columns={"open": "p1500"})
    p1530 = thirty[thirty["time"] == config.THIRTY_THIRTY_PM][["ticker", "date", "open"]]
    p1530 = p1530.rename(columns={"open": "p1530"})
    p1600m = five[five["time"] == config.CLOSE_TIME][["ticker", "date", "close"]]
    p1600m = p1600m.rename(columns={"close": "p1600m"})

    panel = base.merge(p1500, on=["ticker", "date"], how="inner")
    panel = panel.merge(p1530, on=["ticker", "date"], how="inner")
    panel = panel.merge(p1600m, on=["ticker", "date"], how="inner")
    panel = panel.dropna(subset=["prior_close", "open", "p1500", "p1530", "p1600m"])

    panel["rod3"] = panel["p1500"] / panel["prior_close"] - 1.0  # Eq. 1
    panel["overnight_return"] = panel["open"] / panel["prior_close"] - 1.0
    panel["lh"] = panel["p1600m"] / panel["p1530"] - 1.0  # Eq. 1
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    meta = {"daily": daily_meta, "thirty_min": thirty_meta, "five_min": five_meta}
    return panel, meta


def add_prior_month_weight(panel: pd.DataFrame) -> pd.DataFrame:
    """Mean daily dollar volume over the prior calendar month (Sec. 3.3), per ticker.

    Approximated by a trailing window of ``config.DOLLAR_VOLUME_LOOKBACK_DAYS``
    trading days, shifted by one day so that the weight used on day t never
    includes day t's own volume (no look-ahead).
    """
    panel = panel.sort_values(["ticker", "date"]).copy()
    lagged_dv = panel.groupby("ticker")["dollar_volume"].shift(1)
    panel["prior_month_dollar_volume"] = lagged_dv.groupby(panel["ticker"]).transform(
        lambda s: s.rolling(config.DOLLAR_VOLUME_LOOKBACK_DAYS, min_periods=config.DOLLAR_VOLUME_LOOKBACK_DAYS).mean()
    )
    return panel


def apply_stock_day_filters(panel: pd.DataFrame) -> pd.DataFrame:
    """Price, overnight-move and prior-month-volume filters (Sec. 3.1, step 3)."""
    out = panel.copy()
    out = out[out["prior_close"] >= config.MIN_PRICE]
    out = out[out["overnight_return"].abs() <= config.MAX_ABS_OVERNIGHT_MOVE]
    out = out[out["prior_month_dollar_volume"].notna()]
    return out.reset_index(drop=True)


def session_coverage(panel: pd.DataFrame, membership_by_day: dict[pd.Timestamp, set[str]]) -> pd.Series:
    """Fraction of point-in-time members with a usable bar, by date (Sec. 3.1, step 2)."""
    counts = panel.groupby("date")["ticker"].nunique()
    coverage = {}
    for date, present in counts.items():
        members = membership_by_day.get(pd.Timestamp(date))
        coverage[date] = present / len(members) if members else np.nan
    return pd.Series(coverage).sort_index()


def apply_session_filters(
    panel: pd.DataFrame,
    membership_by_day: dict[pd.Timestamp, set[str]],
    start: str,
    end: str,
) -> tuple[pd.DataFrame, dict]:
    """Drop early-close sessions and sessions with low member coverage (Sec. 3.1, step 2)."""
    early_closes = calendar_filters.nyse_early_close_dates(start, end)
    coverage = session_coverage(panel, membership_by_day)
    low_coverage = set(coverage[coverage < config.MIN_MEMBER_COVERAGE].index)
    dropped_dates = early_closes | {pd.Timestamp(d) for d in low_coverage}
    kept = panel[~panel["date"].isin(dropped_dates)].reset_index(drop=True)
    info = {
        "early_closes_dropped": len(early_closes),
        "low_coverage_sessions_dropped": len(low_coverage),
        "sessions_kept": kept["date"].nunique(),
    }
    return kept, info


def scaled_rank(panel: pd.DataFrame, value_col: str = "rod3") -> pd.DataFrame:
    """Cross-sectional rank of ``value_col`` each day, scaled to [-0.5, 0.5] (Sec. 3.3)."""
    out = panel.copy()

    def _scale(group: pd.Series) -> pd.Series:
        n = len(group)
        if n < 2:
            return pd.Series(np.nan, index=group.index)
        rank = group.rank(method="average")
        return (rank - 1.0) / (n - 1.0) * (
            config.RANK_SCALE_HIGH - config.RANK_SCALE_LOW
        ) + config.RANK_SCALE_LOW

    out["q"] = out.groupby("date")[value_col].transform(_scale)
    return out


def daily_wls_slope(
    panel: pd.DataFrame,
    y_col: str = "lh",
    x_col: str = "q",
    weight_col: str = "prior_month_dollar_volume",
    min_obs: int = 10,
) -> pd.DataFrame:
    """Daily WLS slope b_t of ``y_col`` on ``x_col`` with ``weight_col`` weights (Sec. 3.3).

    Returns one row per date with ``b`` (the slope), ``se`` and ``n``. The
    reversal of the day is ``R_t = -b_t`` (Sec. 3.3): a negative slope of the
    closing return on the ROD3 rank means low-ROD3 "losers" (q near -0.5)
    outperform high-ROD3 "winners" into the close, i.e. a positive reversal.
    """
    rows = []
    for date, group in panel.groupby("date"):
        group = group.dropna(subset=[y_col, x_col, weight_col])
        group = group[group[weight_col] > 0]
        if len(group) < min_obs:
            continue
        X = sm.add_constant(group[x_col].to_numpy())
        model = WLS(group[y_col].to_numpy(), X, weights=group[weight_col].to_numpy()).fit()
        rows.append({"date": date, "b": model.params[1], "se": model.bse[1], "n": len(group)})
    return pd.DataFrame(rows).set_index("date").sort_index() if rows else pd.DataFrame(
        columns=["b", "se", "n"]
    )


def daily_reversal_series(wls_result: pd.DataFrame) -> pd.Series:
    """R_t = -b_t, the daily end-of-day reversal in return units (Sec. 3.3)."""
    return -wls_result["b"]


def newey_west_mean(series: pd.Series, lags: int = config.NEWEY_WEST_LAGS) -> dict:
    """Mean of ``series`` with a Newey-West (1987) HAC standard error (Sec. 3.3)."""
    series = series.dropna()
    n = len(series)
    if n == 0:
        return {"mean": np.nan, "se": np.nan, "t": np.nan, "n": 0}
    X = np.ones(n)
    model = sm.OLS(series.to_numpy(), X).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {
        "mean": float(model.params[0]),
        "se": float(model.bse[0]),
        "t": float(model.tvalues[0]),
        "n": n,
    }


def period_reversal(R_t: pd.Series, start: str, end: str) -> dict:
    """Period-mean daily reversal with Newey-West SE over ``[start, end]`` (Sec. 3.3)."""
    window = R_t[(R_t.index >= pd.Timestamp(start)) & (R_t.index <= pd.Timestamp(end))]
    return newey_west_mean(window)


def quintile_spread_series(panel: pd.DataFrame, n_quintiles: int = config.QUINTILES) -> pd.Series:
    """Daily dollar-volume-weighted return of the bottom ROD3 quintile minus the top (Sec. 3.3).

    No winsorization is applied, matching the paper's main specification
    (unlike BDS, who winsorize LH at 1%/99% in their own panel regressions).
    """
    rows = {}
    for date, group in panel.groupby("date"):
        group = group.dropna(subset=["rod3", "lh", "prior_month_dollar_volume"])
        group = group[group["prior_month_dollar_volume"] > 0]
        if len(group) < n_quintiles * 2:
            continue
        try:
            quintile = pd.qcut(group["rod3"], n_quintiles, labels=False, duplicates="drop")
        except ValueError:
            continue
        group = group.assign(quintile=quintile)
        n_q = group["quintile"].nunique()
        if n_q < n_quintiles:
            continue

        def _wavg(sub: pd.DataFrame) -> float:
            return float(np.average(sub["lh"], weights=sub["prior_month_dollar_volume"]))

        bottom = _wavg(group[group["quintile"] == 0])
        top = _wavg(group[group["quintile"] == n_quintiles - 1])
        rows[date] = bottom - top
    return pd.Series(rows).sort_index()


def change_test(mean_e: float, se_e: float, mean_l: float, se_l: float) -> dict:
    """Delta = mean_L - mean_E with SE = sqrt(se_E^2 + se_L^2) (Sec. 3.4)."""
    delta = mean_l - mean_e
    se = float(np.sqrt(se_e**2 + se_l**2))
    t = delta / se if se > 0 else np.nan
    return {"delta": delta, "se": se, "t": t}


def one_sided_decline_bound(
    mean_e: float, se_e: float, mean_l: float, se_l: float, confidence: float = config.ONE_SIDED_CI_LEVEL
) -> dict:
    """One-sided confidence bound on the decline mean_E - mean_L (Sec. 4.2).

    ``bound_bps`` is the upper bound of the decline at the given one-sided
    confidence level; ``fraction_of_e`` expresses it as a share of the
    2016-2019 effect.
    """
    from scipy.stats import norm

    decline = mean_e - mean_l
    se = float(np.sqrt(se_e**2 + se_l**2))
    z = norm.ppf(confidence)
    bound = decline + z * se
    fraction = bound / mean_e if mean_e else np.nan
    return {"decline": decline, "se": se, "bound_bps": bound, "fraction_of_e": fraction}


def reproduction_test(mean_e: float, t_e: float) -> bool:
    """Reproduction-test gate: R_E > 0 with t >= 2 (Sec. 3.4), required before period L is read."""
    return bool(mean_e > 0 and t_e >= config.REPRODUCTION_T_MIN)


def verdict(mean_l: float, t_l: float, change: dict) -> str:
    """Pre-registered verdict rules (Sec. 3.4): 'weakened', 'no weakening', or 'inconclusive'."""
    if change["delta"] < 0 and change["t"] <= -config.WEAKENED_T_BAR:
        return "weakened"
    if change["delta"] >= 0 or (mean_l > 0 and t_l >= config.NO_WEAKENING_T_MIN):
        return "no weakening"
    return "inconclusive"
