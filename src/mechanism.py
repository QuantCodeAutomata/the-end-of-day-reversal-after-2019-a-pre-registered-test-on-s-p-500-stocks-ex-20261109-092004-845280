"""Mechanism tests: market/idiosyncratic split, weekday option DiD, ETF launches (Sec. 5).

Custom implementation of the paper's four pre-registered mechanism tests
(Sec. 5.1-5.2); statsmodels supplies the WLS/OLS and Newey-West (HAC)
machinery already used by ``src.reversal``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.linear_model import WLS
from statsmodels.stats.multitest import multipletests

from src import config, reversal


def rolling_beta(
    stock_returns: pd.DataFrame, market_returns: pd.Series, window: int = config.BETA_WINDOW,
    min_periods: int = config.BETA_MIN_SESSIONS,
) -> pd.DataFrame:
    """Rolling OLS slope of each stock's daily return on SPY's daily return (Sec. 5.1).

    ``stock_returns`` has one column per ticker indexed by date; the window
    looks only at the prior ``window`` sessions up to and including the
    current day's own daily return (consistent with the paper's "prior 252
    sessions"), requiring at least ``min_periods`` observations.
    """
    aligned = stock_returns.align(market_returns, axis=0, join="inner")
    stocks, market = aligned
    market_var = market.rolling(window, min_periods=min_periods).var()
    betas = {}
    for ticker in stocks.columns:
        cov = stocks[ticker].rolling(window, min_periods=min_periods).cov(market)
        betas[ticker] = cov / market_var
    return pd.DataFrame(betas, index=stocks.index)


def split_market_idiosyncratic(
    panel: pd.DataFrame, rod3_spy: pd.Series, betas: pd.DataFrame
) -> pd.DataFrame:
    """ROD3 split into a market component beta*ROD3_SPY and an idiosyncratic residual (Sec. 5.1)."""
    out = panel.copy()
    out["rod3_spy"] = out["date"].map(rod3_spy)
    out["beta"] = out.apply(lambda r: betas.at[r["date"], r["ticker"]] if r["ticker"] in betas.columns and r["date"] in betas.index else np.nan, axis=1)
    out = out.dropna(subset=["rod3_spy", "beta"])
    out["rod3_market"] = out["beta"] * out["rod3_spy"]
    out["rod3_idio"] = out["rod3"] - out["rod3_market"]
    return out


def daily_two_factor_wls(
    panel: pd.DataFrame,
    weight_col: str = "prior_month_dollar_volume",
    min_obs: int = 10,
) -> pd.DataFrame:
    """Daily WLS of LH on scaled ranks of the market and idiosyncratic ROD3 components (Sec. 5.1).

    Returns one row per date with slopes ``b_market``/``b_idio`` and their SEs;
    the reversal components are ``-b_market`` and ``-b_idio``.
    """
    ranked = reversal.scaled_rank(panel, value_col="rod3_market").rename(columns={"q": "q_market"})
    ranked = reversal.scaled_rank(ranked, value_col="rod3_idio").rename(columns={"q": "q_idio"})
    rows = []
    for date, group in ranked.groupby("date"):
        group = group.dropna(subset=["lh", "q_market", "q_idio", weight_col])
        group = group[group[weight_col] > 0]
        if len(group) < min_obs:
            continue
        X = sm.add_constant(group[["q_market", "q_idio"]].to_numpy())
        model = WLS(group["lh"].to_numpy(), X, weights=group[weight_col].to_numpy()).fit()
        rows.append(
            {
                "date": date,
                "b_market": model.params[1],
                "se_market": model.bse[1],
                "b_idio": model.params[2],
                "se_idio": model.bse[2],
                "n": len(group),
            }
        )
    return pd.DataFrame(rows).set_index("date").sort_index() if rows else pd.DataFrame(
        columns=["b_market", "se_market", "b_idio", "se_idio", "n"]
    )


def weekday_option_did(
    market_reversal: pd.Series, start: str, event_date: str = config.WEEKDAY_OPTION_EVENT_DATE
) -> dict:
    """Difference-in-differences of the market-component reversal by weekday (Sec. 5.1).

    Compares Tuesdays/Thursdays (weekdays that gained same-day S&P 500 index
    option expiries in 2022) against other weekdays, before and after
    ``event_date``, with Newey-West standard errors.
    """
    series = market_reversal[market_reversal.index >= pd.Timestamp(start)].dropna()
    frame = series.rename("r").to_frame()
    frame["treated_day"] = frame.index.day_name().isin(config.WEEKDAY_TREATED_DAYS).astype(float)
    frame["post"] = (frame.index >= pd.Timestamp(event_date)).astype(float)
    frame["interaction"] = frame["treated_day"] * frame["post"]
    X = sm.add_constant(frame[["treated_day", "post", "interaction"]].to_numpy())
    model = sm.OLS(frame["r"].to_numpy(), X).fit(
        cov_type="HAC", cov_kwds={"maxlags": config.NEWEY_WEST_LAGS}
    )
    return {
        "effect_bps": float(model.params[3]) * 1e4,
        "t": float(model.tvalues[3]),
        "n": len(frame),
    }


def stock_time_series_slope(
    stock_panel: pd.DataFrame, window_mask: pd.Series, min_obs: int = 30
) -> dict:
    """OLS slope of one stock's LH on its own daily cross-sectional rank q over a window (Sec. 5.2)."""
    window = stock_panel[window_mask].dropna(subset=["lh", "q"])
    if len(window) < min_obs:
        return {"b": np.nan, "se": np.nan, "n": len(window)}
    X = sm.add_constant(window["q"].to_numpy())
    model = sm.OLS(window["lh"].to_numpy(), X).fit()
    return {"b": float(model.params[1]), "se": float(model.bse[1]), "n": len(window)}


def leveraged_etf_stacked_did(
    ranked_panel: pd.DataFrame,
    launch_dates: dict[str, pd.Timestamp],
    control_map: dict[str, list[str]],
    window: int = config.LEVERAGED_ETF_WINDOW,
) -> dict:
    """Stacked DiD of the stock-level LH-on-q slope around each ETF launch (Sec. 5.2).

    For each treated stock, compares the pre- vs post-launch own-slope change
    with the average change of its matched control stocks (similar
    prior-month dollar volume); ``n_treated`` reports how many treated stocks
    had enough sessions on both sides to enter the test.
    """
    treated_changes, control_changes = [], []
    for ticker, launch in launch_dates.items():
        stock = ranked_panel[ranked_panel["ticker"] == ticker].sort_values("date")
        if stock.empty:
            continue
        dates = stock["date"].reset_index(drop=True)
        launch_idx = dates.searchsorted(pd.Timestamp(launch))
        pre = stock.iloc[max(0, launch_idx - window) : launch_idx]
        post = stock.iloc[launch_idx : launch_idx + window]
        pre_slope = stock_time_series_slope(stock, stock.index.isin(pre.index))
        post_slope = stock_time_series_slope(stock, stock.index.isin(post.index))
        if np.isnan(pre_slope["b"]) or np.isnan(post_slope["b"]):
            continue
        treated_changes.append(-(post_slope["b"] - pre_slope["b"]))  # change in reversal (R=-b)

        for control in control_map.get(ticker, []):
            c_stock = ranked_panel[ranked_panel["ticker"] == control].sort_values("date")
            if c_stock.empty:
                continue
            c_dates = c_stock["date"].reset_index(drop=True)
            c_idx = c_dates.searchsorted(pd.Timestamp(launch))
            c_pre = c_stock.iloc[max(0, c_idx - window) : c_idx]
            c_post = c_stock.iloc[c_idx : c_idx + window]
            c_pre_slope = stock_time_series_slope(c_stock, c_stock.index.isin(c_pre.index))
            c_post_slope = stock_time_series_slope(c_stock, c_stock.index.isin(c_post.index))
            if np.isnan(c_pre_slope["b"]) or np.isnan(c_post_slope["b"]):
                continue
            control_changes.append(-(c_post_slope["b"] - c_pre_slope["b"]))

    n_treated = len(treated_changes)
    if n_treated == 0 or not control_changes:
        return {"effect_bps": np.nan, "t": np.nan, "n_treated": n_treated}
    treated_mean = float(np.mean(treated_changes))
    control_mean = float(np.mean(control_changes))
    treated_se = float(np.std(treated_changes, ddof=1) / np.sqrt(n_treated)) if n_treated > 1 else np.nan
    control_se = (
        float(np.std(control_changes, ddof=1) / np.sqrt(len(control_changes)))
        if len(control_changes) > 1
        else np.nan
    )
    diff = treated_mean - control_mean
    se = float(np.sqrt(treated_se**2 + control_se**2)) if treated_se and control_se else np.nan
    t = diff / se if se else np.nan
    return {
        "effect_bps": diff * 1e4,
        "t": t,
        "n_treated": n_treated,
        "n_control": len(control_changes),
        "meets_min_treated": n_treated >= config.LEVERAGED_ETF_MIN_TREATED,
    }


def holm_family(p_values: list[float], alpha: float = config.HOLM_ALPHA) -> dict:
    """Holm (1979) step-down correction across the mechanism-test family (Sec. 5.1)."""
    reject, adj_p, _, _ = multipletests(p_values, alpha=alpha, method="holm")
    return {"reject": list(map(bool, reject)), "adjusted_p": list(map(float, adj_p))}
