"""Next-morning price-pressure test: kappa reversal give-back (Sec. 4.6).

Custom implementation of the paper's overnight give-back check; reuses the
scaled-rank transform and the Newey-West/WLS machinery from ``src.reversal``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.linear_model import WLS

from src import config, reversal


def add_next_morning_return(panel: pd.DataFrame, daily_bars: pd.DataFrame) -> pd.DataFrame:
    """Return from the last trade before 4 p.m. to the next session's open (Sec. 4.6).

    ``daily_bars`` must carry adjusted (split/dividend) prices, because the
    next-morning window crosses a session boundary: an overnight split or
    dividend changes the raw price level between the two prints.
    """
    out = panel.sort_values(["ticker", "date"]).copy()
    next_open = daily_bars.sort_values(["ticker", "date"]).copy()
    next_open["next_open"] = next_open.groupby("ticker")["open"].shift(-1)
    next_open["next_date"] = next_open.groupby("ticker")["date"].shift(-1)
    next_open = next_open[["ticker", "date", "next_open", "next_date"]]
    out = out.merge(next_open, on=["ticker", "date"], how="left")
    out["next_morning_return"] = out["next_open"] / out["p1600m"] - 1.0
    return out.dropna(subset=["next_morning_return"])


def daily_next_morning_slope(
    ranked_panel: pd.DataFrame, weight_col: str = "prior_month_dollar_volume", min_obs: int = 10
) -> pd.DataFrame:
    """Daily WLS slope of the next-morning return on the same scaled ROD3 rank q (Sec. 4.6)."""
    rows = []
    for date, group in ranked_panel.groupby("date"):
        group = group.dropna(subset=["next_morning_return", "q", weight_col])
        group = group[group[weight_col] > 0]
        if len(group) < min_obs:
            continue
        X = sm.add_constant(group["q"].to_numpy())
        model = WLS(group["next_morning_return"].to_numpy(), X, weights=group[weight_col].to_numpy()).fit()
        rows.append({"date": date, "b": model.params[1], "se": model.bse[1], "n": len(group)})
    if rows:
        return pd.DataFrame(rows).set_index("date").sort_index()
    # Mirrors the daily_wls_slope empty-fallback fix (src/reversal.py): keep a
    # proper DatetimeIndex so date-range comparisons on an empty result do not
    # raise, e.g. a diagnostic subsample too small for this run's universe.
    return pd.DataFrame({"b": [], "se": [], "n": []}, index=pd.DatetimeIndex([], name="date"))


def kappa(
    closing_slope_mean: float, next_morning_slope_mean: float
) -> float:
    """kappa = mean next-morning slope / mean closing slope (Sec. 4.6).

    kappa near -1 means the next morning fully gives back the closing move
    (transitory price pressure); kappa near 0 means the closing move persists.
    """
    return next_morning_slope_mean / closing_slope_mean if closing_slope_mean else np.nan


def kappa_interval(
    closing_slopes: pd.Series, next_morning_slopes: pd.Series, level: float = config.KAPPA_CI_LEVEL,
    n_boot: int = 2000, seed: int = config.RANDOM_SEED,
) -> dict:
    """Block-bootstrap interval for kappa, matching dates between the two daily slope series."""
    aligned = pd.concat(
        [closing_slopes.rename("b_close"), next_morning_slopes.rename("b_next")], axis=1
    ).dropna()
    point = kappa(aligned["b_close"].mean(), aligned["b_next"].mean())
    rng = np.random.default_rng(seed)
    n = len(aligned)
    if n == 0:
        return {"kappa": point, "lower": np.nan, "upper": np.nan, "n": 0}
    block = config.CHANGEPOINT_BLOCK_DAYS
    draws = []
    for _ in range(n_boot):
        n_blocks = int(np.ceil(n / block))
        starts = rng.integers(0, max(n - block, 1), size=n_blocks)
        idx = np.concatenate([np.arange(s, min(s + block, n)) for s in starts])[:n]
        sample = aligned.iloc[idx]
        k = kappa(sample["b_close"].mean(), sample["b_next"].mean())
        if np.isfinite(k):
            draws.append(k)
    draws = np.array(draws)
    lower_q, upper_q = (1 - level) / 2, 1 - (1 - level) / 2
    return {
        "kappa": point,
        "lower": float(np.quantile(draws, lower_q)) if len(draws) else np.nan,
        "upper": float(np.quantile(draws, upper_q)) if len(draws) else np.nan,
        "n": n,
    }


def combined_reversal(
    closing_slopes: pd.Series, next_morning_slopes: pd.Series, lags: int = config.NEWEY_WEST_LAGS
) -> dict:
    """Combined closing + next-morning reversal, compounded daily and tested with Newey-West SE (Sec. 4.6)."""
    aligned = pd.concat(
        [closing_slopes.rename("b_close"), next_morning_slopes.rename("b_next")], axis=1
    ).dropna()
    combined = -aligned["b_close"] - aligned["b_next"]  # -b_close - b_next = R_close + R_next
    return reversal.newey_west_mean(combined, lags=lags)
