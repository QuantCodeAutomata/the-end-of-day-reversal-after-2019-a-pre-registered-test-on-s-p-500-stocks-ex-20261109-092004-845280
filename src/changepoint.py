"""Sup-Wald structural-break test for the daily reversal series (Sec. 4.4).

Custom implementation of Andrews' (1993) sup-Wald test for a single shift in
the mean of a time series, with 15% trimming and a block-bootstrap p-value,
as no bundled library implements this specific test with inferential
p-values (ruptures provides segmentation/detection, not this hypothesis
test). statsmodels supplies the Wald test used for the descriptive
three-period comparison.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src import config


def _wald_at(y: np.ndarray, tau: int) -> float:
    left, right = y[:tau], y[tau:]
    n1, n2 = len(left), len(right)
    if n1 < 2 or n2 < 2:
        return -np.inf
    var_pooled = (left.var(ddof=1) * (n1 - 1) + right.var(ddof=1) * (n2 - 1)) / (n1 + n2 - 2)
    if var_pooled <= 0:
        return -np.inf
    se = np.sqrt(var_pooled * (1.0 / n1 + 1.0 / n2))
    return float(((right.mean() - left.mean()) / se) ** 2)


def sup_wald_test(series: pd.Series, trim: float = config.CHANGEPOINT_TRIM) -> dict:
    """Andrews (1993) sup-Wald statistic for a single mean shift, 15% trimmed."""
    series = series.dropna()
    y = series.to_numpy()
    n = len(y)
    lo = int(np.ceil(trim * n))
    hi = n - lo
    stats = {tau: _wald_at(y, tau) for tau in range(lo, hi)}
    best_tau = max(stats, key=stats.get)
    return {
        "stat": stats[best_tau],
        "tau": best_tau,
        "break_date": series.index[best_tau],
        "stats_by_tau": stats,
        "n": n,
        "index": series.index,
    }


def linear_detrend(series: pd.Series) -> pd.Series:
    """Residuals of ``series`` on a linear time trend (Sec. 4.4, "detrended version")."""
    series = series.dropna()
    t = np.arange(len(series))
    X = sm.add_constant(t)
    model = sm.OLS(series.to_numpy(), X).fit()
    return pd.Series(model.resid, index=series.index)


def _block_bootstrap_sample(y: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    n = len(y)
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, max(n - block, 1), size=n_blocks)
    idx = np.concatenate([np.arange(s, min(s + block, n)) for s in starts])[:n]
    return y[idx]


def block_bootstrap_pvalue(
    series: pd.Series,
    observed_stat: float,
    n_draws: int = config.CHANGEPOINT_BOOTSTRAP_DRAWS_RUN,
    block: int = config.CHANGEPOINT_BLOCK_DAYS,
    trim: float = config.CHANGEPOINT_TRIM,
    seed: int = config.RANDOM_SEED,
) -> float:
    """Block-bootstrap p-value for the sup-Wald statistic under the no-break null (Sec. 4.4).

    Resamples 21-day blocks of the demeaned series (the null of a constant
    mean), so each draw has no true break, and counts how often the
    bootstrap sup-Wald statistic equals or exceeds the one observed in the
    real series.
    """
    series = series.dropna()
    y_demeaned = (series - series.mean()).to_numpy()
    rng = np.random.default_rng(seed)
    n = len(y_demeaned)
    lo, hi = int(np.ceil(trim * n)), n - int(np.ceil(trim * n))
    exceed = 0
    for _ in range(n_draws):
        sample = _block_bootstrap_sample(y_demeaned, block, rng)
        stat = max(_wald_at(sample, tau) for tau in range(lo, hi))
        if stat >= observed_stat:
            exceed += 1
    return (1 + exceed) / (1 + n_draws)


def break_date_interval(
    series: pd.Series,
    n_draws: int = config.CHANGEPOINT_BOOTSTRAP_DRAWS_RUN,
    block: int = config.CHANGEPOINT_BLOCK_DAYS,
    trim: float = config.CHANGEPOINT_TRIM,
    level: float = config.CHANGEPOINT_CI_LEVEL,
    seed: int = config.RANDOM_SEED,
) -> dict:
    """Interval for the estimated break date from a block bootstrap of the series itself (Sec. 4.4)."""
    series = series.dropna()
    y = series.to_numpy()
    rng = np.random.default_rng(seed + 1)
    n = len(y)
    lo, hi = int(np.ceil(trim * n)), n - int(np.ceil(trim * n))
    taus = []
    for _ in range(n_draws):
        sample = _block_bootstrap_sample(y, block, rng)
        stats = {tau: _wald_at(sample, tau) for tau in range(lo, hi)}
        taus.append(max(stats, key=stats.get))
    taus = np.array(taus)
    lower_q, upper_q = (1 - level) / 2, 1 - (1 - level) / 2
    lower_idx = int(np.clip(np.quantile(taus, lower_q), 0, n - 1))
    upper_idx = int(np.clip(np.quantile(taus, upper_q), 0, n - 1))
    return {"lower_date": series.index[lower_idx], "upper_date": series.index[upper_idx]}


def three_period_chi2_test(
    R_t: pd.Series,
    period_e: tuple[str, str],
    period_t: tuple[str, str],
    period_l: tuple[str, str],
    lags: int = config.NEWEY_WEST_LAGS,
) -> dict:
    """Descriptive Wald test of equal means across periods E, T, L (Sec. 4.4, chi-squared(2))."""
    series = R_t.dropna()
    frame = series.rename("r").to_frame()
    frame["dummy_t"] = (
        (frame.index >= pd.Timestamp(period_t[0])) & (frame.index <= pd.Timestamp(period_t[1]))
    ).astype(float)
    frame["dummy_l"] = (
        (frame.index >= pd.Timestamp(period_l[0])) & (frame.index <= pd.Timestamp(period_l[1]))
    ).astype(float)
    in_sample = (
        (frame.index >= pd.Timestamp(period_e[0])) & (frame.index <= pd.Timestamp(period_l[1]))
    )
    frame = frame[in_sample]
    X = sm.add_constant(frame[["dummy_t", "dummy_l"]].to_numpy())
    model = sm.OLS(frame["r"].to_numpy(), X).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    wald = model.wald_test(np.eye(3)[1:], scalar=True)
    return {"stat": float(wald.statistic), "p": float(wald.pvalue), "df": 2}


def power_simulation(
    period_means: dict[str, float],
    residual_pool: np.ndarray,
    period_lengths: dict[str, int],
    n_draws: int = config.POWER_SIM_DRAWS_RUN,
    block: int = config.CHANGEPOINT_BLOCK_DAYS,
    trim: float = config.CHANGEPOINT_TRIM,
    break_window: tuple[str, str] = config.CHANGEPOINT_BREAK_WINDOW,
    p_bar: float = config.CHANGEPOINT_BREAK_P_BAR,
    seed: int = config.RANDOM_SEED,
) -> dict:
    """Monte Carlo power of the sup-Wald test and the full registered rule against a dip that reverses (Sec. 4.4).

    Simulated series = period_means[E, T, L] concatenated in order, plus
    block-resampled residuals drawn from ``residual_pool`` (the observed
    daily reversal series net of its own period means), dated with a daily
    index so the registered rule's break-date and detrended-test clauses can
    be evaluated on each draw.
    """
    rng = np.random.default_rng(seed + 2)
    n_e, n_t, n_l = period_lengths["E"], period_lengths["T"], period_lengths["L"]
    mean_path = np.concatenate(
        [np.full(n_e, period_means["E"]), np.full(n_t, period_means["T"]), np.full(n_l, period_means["L"])]
    )
    n = len(mean_path)
    dates = pd.bdate_range(config.SAMPLE_START, periods=n)
    reject_5pct = reject_1pct = full_rule_fires = 0
    for _ in range(n_draws):
        resid = _block_bootstrap_sample(residual_pool, block, rng)[:n]
        series = pd.Series(mean_path + resid, index=dates)
        result = sup_wald_test(series, trim=trim)
        p = block_bootstrap_pvalue(series, result["stat"], n_draws=99, block=block, trim=trim, seed=rng.integers(1_000_000))
        if p < 0.05:
            reject_5pct += 1
        if p < 0.01:
            reject_1pct += 1
            detrended = linear_detrend(series)
            detrended_result = sup_wald_test(detrended, trim=trim)
            p_detrended = block_bootstrap_pvalue(
                detrended, detrended_result["stat"], n_draws=99, block=block, trim=trim, seed=rng.integers(1_000_000)
            )
            break_in_window = (
                pd.Timestamp(break_window[0]) <= result["break_date"] <= pd.Timestamp(break_window[1])
            )
            if p < p_bar and break_in_window and p_detrended < p_bar:
                full_rule_fires += 1
    return {
        "reject_rate_5pct": reject_5pct / n_draws,
        "reject_rate_1pct": reject_1pct / n_draws,
        "full_rule_fire_rate": full_rule_fires / n_draws,
        "n_draws": n_draws,
    }
