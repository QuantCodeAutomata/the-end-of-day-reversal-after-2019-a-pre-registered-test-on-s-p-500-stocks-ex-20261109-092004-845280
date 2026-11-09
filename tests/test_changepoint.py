"""Unit tests for src.changepoint: sup-Wald break detection and bootstrap inference."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import changepoint


def test_sup_wald_detects_injected_break() -> None:
    rng = np.random.default_rng(7)
    n = 300
    dates = pd.bdate_range("2016-01-04", periods=n)
    series = pd.Series(np.concatenate([rng.normal(0.0003, 0.0005, 150), rng.normal(-0.0002, 0.0005, 150)]), index=dates)
    result = changepoint.sup_wald_test(series)
    assert 100 < result["tau"] < 200  # near the true break at index 150


def test_sup_wald_trimming_excludes_tails() -> None:
    rng = np.random.default_rng(8)
    series = pd.Series(rng.normal(0, 1, 100))
    result = changepoint.sup_wald_test(series, trim=0.15)
    assert result["tau"] >= 15
    assert result["tau"] <= 85


def test_block_bootstrap_pvalue_is_high_under_null() -> None:
    rng = np.random.default_rng(9)
    series = pd.Series(rng.normal(0, 1, 200))
    result = changepoint.sup_wald_test(series)
    p = changepoint.block_bootstrap_pvalue(series, result["stat"], n_draws=199, block=21)
    assert 0.0 < p <= 1.0
    assert p > 0.05  # no true break: should not reject often


def test_linear_detrend_removes_trend() -> None:
    t = np.arange(100)
    series = pd.Series(0.01 * t + np.random.default_rng(1).normal(0, 0.01, 100))
    resid = changepoint.linear_detrend(series)
    slope = np.polyfit(t, resid.to_numpy(), 1)[0]
    assert abs(slope) < 1e-6


def test_three_period_chi2_test_degrees_of_freedom() -> None:
    dates = pd.bdate_range("2016-01-04", periods=300)
    values = pd.Series(np.random.default_rng(2).normal(0.0002, 0.0005, 300), index=dates)
    result = changepoint.three_period_chi2_test(
        values,
        period_e=("2016-01-04", str(dates[99].date())),
        period_t=(str(dates[100].date()), str(dates[199].date())),
        period_l=(str(dates[200].date()), str(dates[-1].date())),
    )
    assert result["df"] == 2
    assert result["p"] >= 0.0
