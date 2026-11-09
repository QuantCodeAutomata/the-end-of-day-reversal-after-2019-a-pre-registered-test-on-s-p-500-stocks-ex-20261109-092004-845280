"""Sample construction: static heavily-traded exclusion, dynamic daily top-N
drop, and weighting diagnostics shared by experiments 1-3 (Sec. 3.1, 4.2-4.5).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import config


def rank_by_dollar_volume(panel: pd.DataFrame, start: str, end: str) -> pd.Series:
    """Mean ``prior_month_dollar_volume`` per ticker over ``[start, end]`` (Sec. 3.1).

    Used as the paper's own liquidity measure to rank candidates for both the
    static "heavily traded" exclusion list and the reduced run universe.
    """
    window = panel[(panel["date"] >= pd.Timestamp(start)) & (panel["date"] <= pd.Timestamp(end))]
    return window.groupby("ticker")["prior_month_dollar_volume"].mean().dropna()


def static_heavy_traded_list(
    panel: pd.DataFrame, exclude_count: int = config.EXCLUDE_COUNT_RUN, ranking_start: str | None = None,
    ranking_end: str | None = None,
) -> list[str]:
    """Fixed list of the ``exclude_count`` most heavily traded tickers (Sec. 3.1, step 1).

    The paper's own ~80-name exclusion list is unpublished (Sec. 3.1);
    this replication substitutes the most liquid names of the
    reduced run universe by mean prior-month dollar volume over period E, a
    fixed list applied for the whole 2016-2026 sample, matching the paper's
    description that the exclusion is by company, not a recomputed daily cut.
    """
    start = ranking_start or config.PERIOD_E[0]
    end = ranking_end or config.PERIOD_E[1]
    ranked = rank_by_dollar_volume(panel, start, end).sort_values(ascending=False)
    return list(ranked.index[:exclude_count])


def exclude_static(panel: pd.DataFrame, excluded_tickers: list[str]) -> pd.DataFrame:
    """Drop a fixed set of tickers for the whole sample (primary-sample proxy, Sec. 3.1)."""
    return panel[~panel["ticker"].isin(excluded_tickers)].reset_index(drop=True)


def exclude_dynamic_daily_top_n(
    panel: pd.DataFrame, n: int = config.EXCLUDE_COUNT_RUN, weight_col: str = "prior_month_dollar_volume"
) -> pd.DataFrame:
    """Each day, drop the ``n`` largest members present by prior-month dollar volume (Sec. 3.1, proxy sample)."""

    def _drop(group: pd.DataFrame) -> pd.DataFrame:
        ranked = group.dropna(subset=[weight_col]).sort_values(weight_col, ascending=False)
        drop_tickers = set(ranked["ticker"].iloc[:n])
        return group[~group["ticker"].isin(drop_tickers)]

    return panel.groupby("date", group_keys=False).apply(_drop).reset_index(drop=True)


def keep_dynamic_daily_top_n(
    panel: pd.DataFrame, n: int = config.EXCLUDE_COUNT_RUN, weight_col: str = "prior_month_dollar_volume"
) -> pd.DataFrame:
    """Each day, keep only the ``n`` largest members by prior-month dollar volume (Sec. 4.2, "among the N largest")."""

    def _keep(group: pd.DataFrame) -> pd.DataFrame:
        ranked = group.dropna(subset=[weight_col]).sort_values(weight_col, ascending=False)
        keep_tickers = set(ranked["ticker"].iloc[:n])
        return group[group["ticker"].isin(keep_tickers)]

    return panel.groupby("date", group_keys=False).apply(_keep).reset_index(drop=True)


def effective_n_series(panel: pd.DataFrame, weight_col: str = "prior_month_dollar_volume") -> pd.Series:
    """Daily effective number of stocks, 1 / sum(w_i^2) with weights normalized to sum 1 (Sec. 4.5)."""

    def _eff(group: pd.DataFrame) -> float:
        w = group[weight_col].dropna()
        w = w[w > 0]
        if w.empty:
            return np.nan
        w = w / w.sum()
        return float(1.0 / np.square(w).sum())

    return panel.groupby("date").apply(_eff).sort_index()


def leave_one_out_range(
    panel: pd.DataFrame, period: tuple[str, str], weight_col: str = "prior_month_dollar_volume"
) -> dict:
    """Range of the period-mean reversal when dropping one stock at a time (Sec. 4.5, "leave-one-out").

    Reports the minimum and maximum period reversal across single-ticker
    deletions, over the tickers that appear on at least one day of the window.
    """
    from src import reversal

    window = panel[(panel["date"] >= pd.Timestamp(period[0])) & (panel["date"] <= pd.Timestamp(period[1]))]
    tickers = window["ticker"].unique()
    estimates = []
    for ticker in tickers:
        reduced = window[window["ticker"] != ticker]
        ranked = reversal.scaled_rank(reduced, value_col="rod3")
        wls = reversal.daily_wls_slope(ranked, weight_col=weight_col)
        r_t = reversal.daily_reversal_series(wls)
        stat = reversal.newey_west_mean(r_t)
        if np.isfinite(stat["mean"]):
            estimates.append(stat["mean"])
    if not estimates:
        return {"min_bps": np.nan, "max_bps": np.nan, "n_tickers": 0}
    estimates = np.array(estimates) * 1e4
    return {"min_bps": float(estimates.min()), "max_bps": float(estimates.max()), "n_tickers": len(estimates)}
